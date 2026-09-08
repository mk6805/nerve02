import requests
from datetime import datetime, timedelta
from extension import db
from models import MonitoringStation, HydrologicalObservation
from geoalchemy2 import WKTElement
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text


NWDP_API = "https://nwdp.nwic.in/api/3/action"

STATES = {"Assam", "Manipur", "Meghalaya", "Mizoram"}

DATASETS = {
    "water_level": "River Water Level (Telemetry - Hourly)",
    "discharge": "River Discharge (Telemetry - Hourly)"
}

BATCH_SIZE = 1000
UPDATE_FETCH_SIZE = 1000
OVERLAP_MINUTES = 120
REQUEST_TIMEOUT = 60


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if value in (None, "", "-", "NA", "N/A", "null"):
        return None
    return str(value).strip()


def parse_float(value):
    if value in (None, "", "-", "NA", "N/A", "null"):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_datetime(value):
    if not value:
        return None

    for fmt in ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            pass

    return None


# ============================================================
# NWDP API
# ============================================================

def nwdp_get(endpoint, params=None):
    response = requests.get(
        f"{NWDP_API}/{endpoint}",
        params=params or {},
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise Exception(data.get("error", "NWDP API request failed"))

    return data["result"]


# ============================================================
# FIND DATASETS
# ============================================================

def find_river_datasets():
    datasets = {}

    for parameter, dataset_name in DATASETS.items():

        result = nwdp_get(
            "package_search",
            {"q": dataset_name, "rows": 100}
        )

        for dataset in result.get("results", []):

            title = dataset.get("title", "")

            if title.lower() == dataset_name.lower():
                datasets[parameter] = dataset
                break

    return datasets


# ============================================================
# GET TELEMETRY RESOURCES
# ============================================================

def get_telemetry_resources(dataset):

    resources = []

    for resource in dataset.get("resources", []):

        name = resource.get("name", "")
        resource_id = resource.get("id")

        if not resource_id:
            continue

        if "telemetry" in name.lower() and "hourly" in name.lower():

            resources.append({
                "id": resource_id,
                "name": name
            })

    return resources


# ============================================================
# GET RECORDS
# ============================================================

def get_resource_records(resource_id, limit=5000, offset=0):

    result = nwdp_get(
        "datastore_search",
        {
            "resource_id": resource_id,
            "limit": limit,
            "offset": offset
        }
    )

    return result.get("records", [])


# ============================================================
# GET LATEST RECORDS
# ============================================================

def get_latest_records(resource_id, limit=UPDATE_FETCH_SIZE):

    sql = f'''
        SELECT *
        FROM "{resource_id}"
        ORDER BY "Data Acquisition Time" DESC
        LIMIT {int(limit)}
    '''

    try:

        result = nwdp_get(
            "datastore_search_sql",
            {"sql": sql}
        )

        return result.get("records", [])

    except Exception as e:

        print(
            f"SQL fetch failed for {resource_id}: {e}"
        )

        return get_resource_records(
            resource_id,
            limit,
            0
        )


# ============================================================
# FIND MEASUREMENT VALUE
# ============================================================

def get_measurement(record, parameter):

    if parameter == "water_level":

        return parse_float(
            record.get(
                "River Water Level Telemetry Hourly (meter)"
            )
        )

    if parameter == "discharge":

        possible_fields = [
            "River Discharge Telemetry Hourly (cumecs)",
            "River Discharge Telemetry Hourly (m3/s)",
            "River Discharge Telemetry Hourly (cumec)",
            "River Discharge Telemetry Hourly"
        ]

        for field in possible_fields:

            if field in record:
                value = parse_float(record[field])

                if value is not None:
                    return value

    return None


# ============================================================
# MONITORING STATION
# ============================================================

def get_or_create_station(record):

    station_name = clean_text(record.get("Station"))
    agency = clean_text(record.get("Agency"))
    state = clean_text(record.get("State"))
    district = clean_text(record.get("District"))

    latitude = parse_float(record.get("Latitude"))
    longitude = parse_float(record.get("Longitude"))

    if not station_name:
        return None

    if state not in STATES:
        return None

    if latitude is None or longitude is None:
        return None

    station = MonitoringStation.query.filter_by(
        station_name=station_name,
        agency=agency,
        state=state,
        district=district
    ).first()

    if station:
        return station

    station = MonitoringStation(
        station_name=station_name,
        agency=agency,
        state=state,
        district=district,
        station_type="hydrological",
        location=WKTElement(
            f"POINT({longitude} {latitude})",
            srid=4326
        ),
        river=clean_text(record.get("River")),
        basin=clean_text(record.get("Basin")),
        tributary=clean_text(record.get("Tributary")),
        subtributary=clean_text(record.get("Subtributary")),
        local_river=clean_text(record.get("Local River"))
    )

    db.session.add(station)
    db.session.flush()

    return station


# ============================================================
# SAVE OBSERVATION
# ============================================================

def save_hydrological_observation(record, parameter):

    state = clean_text(record.get("State"))

    if state not in STATES:
        return False

    observed_at = parse_datetime(
        record.get("Data Acquisition Time")
    )

    if not observed_at:
        return False

    value = get_measurement(
        record,
        parameter
    )

    if value is None:
        return False

    station = get_or_create_station(record)

    if not station:
        return False

    observation = HydrologicalObservation.query.filter_by(
        station_id=station.id,
        observed_at=observed_at
    ).first()

    if not observation:

        observation = HydrologicalObservation(
            station_id=station.id,
            observed_at=observed_at,
            source="CWC/NWDP"
        )

        db.session.add(observation)

    if parameter == "water_level":
        observation.water_level_m = value

    elif parameter == "discharge":
        observation.discharge_m3s = value

    return True


# ============================================================
# INITIAL RESOURCE IMPORT
# ============================================================

def import_river_resource(
    resource_id,
    parameter,
    batch_size=BATCH_SIZE
):

    offset = 0
    processed = 0
    saved = 0
    skipped = 0

    while True:

        records = get_resource_records(
            resource_id,
            batch_size,
            offset
        )

        if not records:
            break

        for record in records:

            processed += 1

            try:

                if save_hydrological_observation(
                    record,
                    parameter
                ):
                    saved += 1
                else:
                    skipped += 1

            except Exception as e:

                print(
                    f"Observation error: {e}"
                )

                db.session.rollback()
                skipped += 1

        try:
            db.session.commit()

        except Exception as e:

            db.session.rollback()

            print(
                f"Batch commit error: {e}"
            )

        print(
            f"{parameter}: "
            f"{processed} processed | "
            f"{saved} saved | "
            f"{skipped} skipped"
        )

        if len(records) < batch_size:
            break

        offset += batch_size

    return {
        "resource_id": resource_id,
        "parameter": parameter,
        "processed": processed,
        "saved": saved,
        "skipped": skipped
    }


# ============================================================
# INITIAL IMPORT ALL RIVER DATA
# ============================================================

def import_river_data():

    print("\n==========================================")
    print("STARTING CWC/NWDP RIVER DATA IMPORT")
    print("==========================================")

    results = {}

    try:

        datasets = find_river_datasets()

        print(
            f"River datasets found: {len(datasets)}"
        )

        for parameter in DATASETS:

            dataset = datasets.get(parameter)

            if not dataset:

                print(
                    f"WARNING: {parameter} dataset not found"
                )

                results[parameter] = {
                    "status": "dataset_not_found"
                }

                continue

            resources = get_telemetry_resources(
                dataset
            )

            print(
                f"{parameter}: "
                f"{len(resources)} telemetry resources"
            )

            parameter_results = []

            for resource in resources:

                print(
                    f"Importing: {resource['name']}"
                )

                try:

                    result = import_river_resource(
                        resource["id"],
                        parameter
                    )

                    parameter_results.append(result)

                except Exception as e:

                    db.session.rollback()

                    print(
                        f"Resource import error: {e}"
                    )

                    parameter_results.append({
                        "resource_id": resource["id"],
                        "status": "error",
                        "error": str(e)
                    })

            results[parameter] = parameter_results

        print("\n==========================================")
        print("RIVER DATA IMPORT COMPLETED")
        print("==========================================")

        return {
            "success": True,
            "results": results
        }

    except Exception as e:

        db.session.rollback()

        print(
            "RIVER DATA IMPORT ERROR:",
            e
        )

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# GET LATEST DATABASE TIME
# ============================================================

def get_latest_db_time(parameter):

    if parameter == "water_level":

        return db.session.query(
            db.func.max(
                HydrologicalObservation.observed_at
            )
        ).filter(
            HydrologicalObservation.water_level_m.isnot(None)
        ).scalar()

    if parameter == "discharge":

        return db.session.query(
            db.func.max(
                HydrologicalObservation.observed_at
            )
        ).filter(
            HydrologicalObservation.discharge_m3s.isnot(None)
        ).scalar()

    return None


# ============================================================
# UPDATE ONE RESOURCE
# ============================================================

def update_river_resource(
    resource_id,
    parameter
):

    latest_db_time = get_latest_db_time(
        parameter
    )

    if latest_db_time:

        cutoff = (
            latest_db_time
            - timedelta(minutes=OVERLAP_MINUTES)
        )

    else:

        cutoff = None

    records = get_latest_records(
        resource_id,
        UPDATE_FETCH_SIZE
    )

    if not records:

        return {
            "resource_id": resource_id,
            "parameter": parameter,
            "processed": 0,
            "new": 0,
            "skipped": 0
        }

    records.sort(
        key=lambda x: (
            parse_datetime(
                x.get("Data Acquisition Time")
            )
            or datetime.min
        )
    )

    processed = 0
    new_rows = 0
    skipped = 0

    for record in records:

        processed += 1

        try:

            observed_at = parse_datetime(
                record.get("Data Acquisition Time")
            )

            if not observed_at:
                skipped += 1
                continue

            if cutoff and observed_at < cutoff:
                skipped += 1
                continue

            state = clean_text(
                record.get("State")
            )

            if state not in STATES:
                skipped += 1
                continue

            value = get_measurement(
                record,
                parameter
            )

            if value is None:
                skipped += 1
                continue

            station = get_or_create_station(
                record
            )

            if not station:
                skipped += 1
                continue

            existing = HydrologicalObservation.query.filter_by(
                station_id=station.id,
                observed_at=observed_at
            ).first()

            if existing:

                if parameter == "water_level":
                    existing.water_level_m = value

                elif parameter == "discharge":
                    existing.discharge_m3s = value

            else:

                observation = HydrologicalObservation(
                    station_id=station.id,
                    observed_at=observed_at,
                    source="CWC/NWDP"
                )

                if parameter == "water_level":
                    observation.water_level_m = value

                elif parameter == "discharge":
                    observation.discharge_m3s = value

                db.session.add(observation)
                new_rows += 1

        except Exception as e:

            print(
                f"Update observation error: {e}"
            )

            db.session.rollback()
            skipped += 1

    try:

        db.session.commit()

    except Exception as e:

        db.session.rollback()

        print(
            f"Update commit error: {e}"
        )

        return {
            "resource_id": resource_id,
            "parameter": parameter,
            "processed": processed,
            "new": new_rows,
            "skipped": skipped,
            "status": "commit_error",
            "error": str(e)
        }

    print(
        f"UPDATE {parameter}: "
        f"{processed} checked | "
        f"{new_rows} new | "
        f"{skipped} skipped"
    )

    return {
        "resource_id": resource_id,
        "parameter": parameter,
        "processed": processed,
        "new": new_rows,
        "skipped": skipped
    }


# ============================================================
# AUTO UPDATE ONLY NEW DATA
# ============================================================

def update_river_data():

    print("\n==========================================")
    print("CWC/NWDP INCREMENTAL RIVER UPDATE")
    print("==========================================")

    results = {}

    try:

        datasets = find_river_datasets()

        for parameter in DATASETS:

            dataset = datasets.get(parameter)

            if not dataset:

                results[parameter] = {
                    "status": "dataset_not_found"
                }

                continue

            resources = get_telemetry_resources(
                dataset
            )

            parameter_results = []

            for resource in resources:

                try:

                    result = update_river_resource(
                        resource["id"],
                        parameter
                    )

                    parameter_results.append(
                        result
                    )

                except Exception as e:

                    db.session.rollback()

                    print(
                        f"Update error for "
                        f"{resource['id']}: {e}"
                    )

                    parameter_results.append({
                        "resource_id": resource["id"],
                        "parameter": parameter,
                        "status": "error",
                        "error": str(e)
                    })

            results[parameter] = parameter_results

        return {
            "success": True,
            "results": results
        }

    except Exception as e:

        db.session.rollback()

        print(
            "RIVER INCREMENTAL UPDATE ERROR:",
            e
        )

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# SCHEDULED UPDATE
# ============================================================

def scheduled_river_update(app):

    with app.app_context():

        try:

            print(
                "\nChecking CWC/NWDP for new river observations..."
            )

            result = update_river_data()

            print(
                "RIVER UPDATE RESULT:",
                result
            )

            return result

        except Exception as e:

            db.session.rollback()

            print(
                "SCHEDULED RIVER UPDATE ERROR:",
                e
            )

            return {
                "success": False,
                "error": str(e)
            }


# ============================================================
# NEARBY RIVER DATA
# ============================================================

def get_nearby_river_data(
    latitude,
    longitude,
    radius_km=50,
    limit=100
):

    query = text("""
        SELECT
            ho.id,
            ho.observed_at,
            ho.water_level_m,
            ho.discharge_m3s,
            ho.river_velocity_ms,
            ho.source,

            ms.station_name,
            ms.agency,
            ms.state,
            ms.district,
            ms.river,
            ms.basin,
            ms.tributary

        FROM hydrological_observation ho

        JOIN monitoring_station ms
            ON ms.id = ho.station_id

        WHERE ST_DWithin(
            ms.location,
            ST_SetSRID(
                ST_MakePoint(
                    :longitude,
                    :latitude
                ),
                4326
            )::geography,
            :radius
        )

        ORDER BY ho.observed_at DESC

        LIMIT :limit
    """)

    rows = db.session.execute(
        query,
        {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_km * 1000,
            "limit": limit
        }
    )

    return [
        dict(row._mapping)
        for row in rows
    ]