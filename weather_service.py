# weather_service.py

import requests
from datetime import datetime, timedelta

from sqlalchemy import select, func
from geoalchemy2 import WKTElement

from extension import db
from models import MonitoringStation, WeatherObservation
from sqlalchemy.dialects.postgresql import insert


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://nwdp.nwic.gov.in/api/3/action"

REQUEST_TIMEOUT = (10, 45)

BATCH_SIZE = 500

OVERLAP_MINUTES = 120

HISTORICAL_START = datetime(2021, 1, 1)

HISTORICAL_END = datetime(2026, 1, 1)

CURRENT_START = datetime(2026, 1, 1)

SOURCE = "NWDP"


# ============================================================
# WEATHER RESOURCE INVENTORY
#
# Historical = 2021-2025
# Current    = 2026-2030
#
# 4 states x 6 parameters = 24 streams
# ============================================================

WEATHER_RESOURCES = {

    "Assam": {

        "temperature": {
            # "historical": "25dc2ac4-904c-4142-8ca7-c6de8c0b5631",
            "current": "676e0e2c-27bc-4f63-8d28-55b7c9d683c4"
        },

        "humidity": {
            # "historical": "873bf28e-f82c-4b71-8ea2-72de32c2ff1e",
            "current": "c592b2e4-858e-4a5d-b037-702441b162c8"
        },

        "solar": {
            # "historical": "3421a21f-ab75-4458-8915-3bea92335539",
            "current": "9b93f0d1-1c6a-4b7b-841f-de490a38f4fe"
        },

        "pressure": {
            # "historical": "1ef1bb74-c36a-4cfe-8a5b-4b4086e49083",
            "current": "684b5322-2ccd-4d76-b87d-6d2f6ba03d17"
        },

        "wind_direction": {
            # "historical": "6ec47e4b-c7e1-49b8-890e-8d272110aff9",
            "current": "ce0535a4-5869-40ef-971f-9d9f3a321c85"
        },

        "wind_speed": {
            # "historical": "ce07aa22-cac4-4a1f-ab98-dd215555e758",
            "current": "57d0b524-bf71-4b54-b67e-63b0434c31d2"
        }
    },


    "Manipur": {

        "temperature": {
            # "historical": "52fa4f23-c263-478f-a374-d5106b331cd5",
            "current": "c5ed40e9-76ad-4ba1-9ab5-70cab5b3e5c7"
        },

        "humidity": {
            # "historical": "12cc720f-48eb-47e3-a518-771a9e1f53f7",
            "current": "12f15c09-dc95-4c5c-b7c1-7c65e351e301"
        },

        "solar": {
            # "historical": "4ea880ff-8b82-46ac-bec6-5192a2a378f5",
            "current": "1ab5af3c-ab55-4bc2-add9-032a1384020e"
        },

        "pressure": {
            # "historical": "8bac605b-ec01-4e72-9185-a98ad460d139",
            "current": "44e98340-2707-470e-94ce-3b10958574c8"
        },

        "wind_direction": {
            # "historical": "8b2c07fc-511e-4d5e-a4e5-ea8b40bd54cf",
            "current": "19ae50f4-59dd-4613-86ab-65bae0548aa9"
        },

        "wind_speed": {
            # "historical": "09772763-9861-48ad-9838-c64716ced5eb",
            "current": "6ac863cb-fa5f-4d1a-9890-e83630dfab5"
        }
    },


    "Meghalaya": {

        "temperature": {
            # "historical": "bd4e2a73-62bc-45eb-9339-8e22e5dfb853",
            "current": "c792c032-e079-43e5-a313-eccac7275be7"
        },

        "humidity": {
            # "historical": "af1bcddf-252c-4cb9-b6c9-c180a6cda68b",
            "current": "09f4615c-9a9e-4efb-8383-13f961800d86"
        },

        "solar": {
            # "historical": "e79c9062-eb8b-4066-bcb1-cd8d04d9fe1f",
            "current": "7f3b7d5d-834a-4813-8cd6-2e1aa28b6ae2"
        },

        "pressure": {
            # "historical": "c5275faa-aa0a-4135-b98d-dccac23b5f89",
            "current": "183a5b21-89a3-487c-8bf1-3fb927354f11"
        },

        "wind_direction": {
            # "historical": "19c7fbdb-d081-4a3c-8834-6da9990f2392",
            "current": "c1898495-8a6c-453e-bfb3-eecc07081df2"
        },

        "wind_speed": {
            # "historical": "79486c59-900f-4e1e-9af3-b0ee9be1fb9a",
            "current": "1bb5bd4c-1cbe-4cbd-a390-e5234435bb99"
        }
    },


    "Mizoram": {

        "temperature": {
            # "historical": "941c3047-829a-4520-819e-7557dfe1a0d6",
            "current": "c2fbe015-e9e7-4b7d-9990-5965810865b2"
        },

        "humidity": {
            # "historical": "e6f60542-82e4-4b2a-a664-06c2d027d8ac",
            "current": "9cac5e37-32a5-435d-a7c1-92effe7fc9c1"
        },

        "solar": {
            # "historical": "924989e5-6fe5-4f7e-af93-1a7f111baa2c",
            "current": "aaab1039-bc59-49cd-a6f1-23077c20b40f"
        },

        "pressure": {
            # "historical": "38838d78-a80f-4493-8de6-76fb5fab5ceb",
            "current": "e8fde185-476f-46ee-88b9-9ed1390241d2"
        },

        "wind_direction": {
            # "historical": "726d4744-cda9-4c03-8ff3-e600e86bad06",
            "current": "30921efe-7bf8-4861-93fd-5a002e1794f1"
        },

        "wind_speed": {
            # "historical": "47345e5d-087c-427d-b7a1-7f9e07c38d7c",
            "current": "8f236160-fb5d-4ec2-8993-b538796042ad"
        }
    }

}


# ============================================================
# DATABASE FIELD MAPPING
# ============================================================

PARAMETER_FIELDS = {

    "temperature": "temperature_c",

    "humidity": "humidity_percent",

    "solar": "solar_radiation_wm2",

    "pressure": "pressure_mb",

    "wind_direction": "wind_direction_deg",

    "wind_speed": "wind_speed_kmh"
}


PARAMETER_NAMES = {

    "temperature": "temperature",

    "humidity": "humidity",

    "solar": "solar",

    "pressure": "pressure",

    "wind_direction": "wind_direction",

    "wind_speed": "wind_speed"
}


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "NERVE02/1.0"
})


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    return value


def parse_float(value):

    if value is None:
        return None

    try:

        if str(value).strip() == "":
            return None

        return float(value)

    except (ValueError, TypeError):

        return None


def parse_datetime(value):

    if value is None:
        return None

    value = str(value).strip()

    if value in ("", "-", "NA", "N/A", "null", "None"):
        return None

    formats = [

        "%d-%m-%Y %H:%M",

        "%d-%m-%Y %H:%M:%S",

        "%Y-%m-%d %H:%M:%S",

        "%Y-%m-%d %H:%M",

        "%Y-%m-%dT%H:%M:%S",

        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                value,
                fmt
            )

        except ValueError:

            continue

    try:

        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

    except ValueError:

        return None


def find_value(row, possible_names):

    for name in possible_names:

        if name in row:

            value = row.get(name)

            if (
                value is not None
                and str(value).strip() != ""
            ):

                return value

    return None


# ============================================================
# GET DATA FROM NWDP
# ============================================================

def datastore_search(
    resource_id,
    limit=1000,
    offset=0
):

    url = f"{BASE_URL}/datastore_search"

    params = {

        "resource_id": resource_id,

        "limit": limit,

        "offset": offset
    }

    response = session.get(

        url,

        params=params,

        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):

        raise RuntimeError(
            data.get(
                "error",
                "NWDP datastore request failed"
            )
        )

    return data["result"]


# ============================================================
# STATION FIND / CREATE
# ============================================================

def get_or_create_station(
    row,
    state
):

    station_name = find_value(

        row,

        [
            "Station Name",
            "Station",
            "station_name",
            "station",
            "Station_Name"
        ]
    )

    agency = find_value(

        row,

        [
            "Agency",
            "agency",
            "Agency Name"
        ]
    )

    district = find_value(

        row,

        [
            "District",
            "district"
        ]
    )

    latitude = find_value(

        row,

        [
            "Latitude",
            "latitude",
            "LATITUDE",
            "Lat",
            "lat"
        ]
    )

    longitude = find_value(

        row,

        [
            "Longitude",
            "longitude",
            "LONGITUDE",
            "Long",
            "lon",
            "lng"
        ]
    )

    station_name = clean_text(
        station_name
    )

    if not station_name:

        station_name = "Unknown Station"

    agency = clean_text(
        agency
    )

    district = clean_text(
        district
    )

    latitude = parse_float(
        latitude
    )

    longitude = parse_float(
        longitude
    )

    if (
        latitude is None
        or longitude is None
    ):

        return None

    station = MonitoringStation.query.filter_by(

        station_name=station_name,

        agency=agency,

        state=state,

        district=district

    ).first()

    if station:

        return station

    location = WKTElement(

        f"POINT({longitude} {latitude})",

        srid=4326
    )

    station = MonitoringStation(

        station_name=station_name,

        agency=agency,

        station_type="weather",

        location=location,

        state=state,

        district=district
    )

    db.session.add(station)

    db.session.flush()

    return station


# ============================================================
# BUILD WEATHER ROW
# ============================================================

def build_weather_row(
    record,
    state,
    parameter
):

    """
    Convert one NWDP weather record
    into our WeatherObservation format.
    """

    station_name = clean_text(

        find_value(

            record,

            [
                "Station",
                "station",
                "Station Name",
                "station_name"
            ]
        )
    )

    agency = clean_text(

        find_value(

            record,

            [
                "Agency",
                "agency"
            ]
        )
    )

    district = clean_text(

        find_value(

            record,

            [
                "District",
                "district"
            ]
        )
    )

    river = clean_text(

        find_value(

            record,

            [
                "River",
                "river"
            ]
        )
    )

    basin = clean_text(

        find_value(

            record,

            [
                "Basin",
                "basin"
            ]
        )
    )

    tributary = clean_text(

        find_value(

            record,

            [
                "Tributary",
                "tributary"
            ]
        )
    )

    subtributary = clean_text(

        find_value(

            record,

            [
                "Subtributary",
                "subtributary"
            ]
        )
    )

    local_river = clean_text(

        find_value(

            record,

            [
                "Local River",
                "local_river"
            ]
        )
    )

    latitude = parse_float(

        find_value(

            record,

            [
                "Latitude",
                "latitude",
                "Lat",
                "lat"
            ]
        )
    )

    longitude = parse_float(

        find_value(

            record,

            [
                "Longitude",
                "longitude",
                "Lon",
                "lon"
            ]
        )
    )

    observed_at = parse_datetime(

        find_value(

            record,

            [
                "Data Acquisition Time",
                "data_acquisition_time",
                "Date",
                "date",
                "Datetime",
                "datetime",
                "Timestamp",
                "timestamp"
            ]
        )
    )

    # Required fields

    if (

        not station_name

        or latitude is None

        or longitude is None

        or observed_at is None

    ):

        return None


    # ========================================================
    # EXACT NWDP PARAMETER COLUMN NAMES
    # ========================================================

    parameter_columns = {

        "temperature": [
            "Air Temperature Telemetry Hourly (AoC)"
        ],

        "humidity": [
            "Telemetry Hourly Relative Humidity (%)"
        ],

        "solar": [
            "Solar Radiation (Watt/m2)"
        ],

        "pressure": [
            "Telemetry_Hourly_Atmospheric Pressure (mb)"
        ],

        "wind_direction": [
            "Telemetry Hourly Wind Direction (Degree)"
        ],

        "wind_speed": [
            "Telemetry Hourly Wind Speed (Km/Hr)"
        ]
    }


    if parameter not in parameter_columns:

        print(
            f"UNKNOWN PARAMETER | "
            f"{state} | {parameter}"
        )

        return None


    value = parse_float(

        find_value(

            record,

            parameter_columns[parameter]
        )
    )


    if value is None:

        return None


    # ========================================================
    # GET / CREATE MONITORING STATION
    # ========================================================

    station = get_or_create_station(

        record,

        state
    )

    if not station:

        return None


    # ========================================================
    # BASE WEATHER ROW
    # ========================================================

    row = {

        "station_id": station.id,

        "observed_at": observed_at,

        "temperature_c": None,

        "humidity_percent": None,

        "rainfall_mm": None,

        "wind_speed_kmh": None,

        "wind_direction_deg": None,

        "pressure_mb": None,

        "solar_radiation_wm2": None,

        "source": SOURCE
    }


    # ========================================================
    # PUT VALUE INTO CORRECT DATABASE COLUMN
    # ========================================================

    if parameter == "temperature":

        row["temperature_c"] = value

    elif parameter == "humidity":

        row["humidity_percent"] = value

    elif parameter == "solar":

        row["solar_radiation_wm2"] = value

    elif parameter == "pressure":

        row["pressure_mb"] = value

    elif parameter == "wind_direction":

        row["wind_direction_deg"] = value

    elif parameter == "wind_speed":

        row["wind_speed_kmh"] = value


    return row


# ============================================================
# SAVE WEATHER BATCH
# ============================================================

def save_weather_batch(
    rows,
    parameter
):

    if not rows:

        return 0


    stmt = insert(
        WeatherObservation
    )


    update_values = {

        "source":
            stmt.excluded.source
    }


    if parameter == "temperature":

        update_values[
            "temperature_c"
        ] = stmt.excluded.temperature_c


    elif parameter == "humidity":

        update_values[
            "humidity_percent"
        ] = stmt.excluded.humidity_percent


    elif parameter == "solar":

        update_values[
            "solar_radiation_wm2"
        ] = stmt.excluded.solar_radiation_wm2


    elif parameter == "pressure":

        update_values[
            "pressure_mb"
        ] = stmt.excluded.pressure_mb


    elif parameter == "wind_direction":

        update_values[
            "wind_direction_deg"
        ] = stmt.excluded.wind_direction_deg


    elif parameter == "wind_speed":

        update_values[
            "wind_speed_kmh"
        ] = stmt.excluded.wind_speed_kmh


    stmt = stmt.on_conflict_do_update(

        constraint="uq_weather_station_time",

        set_=update_values
    )


    db.session.execute(
        stmt,
        rows
    )

    db.session.commit()


    return len(rows)


# ============================================================
# FULL RESOURCE IMPORT
#
# Used for manual bulk import.
# Example:
# /api/import-current-weather
#
# This reads the complete available resource.
# ============================================================

def import_weather_resource(
    resource_id,
    state,
    parameter
):

    processed = 0

    saved = 0

    skipped = 0

    offset = 0


    while True:

        result = datastore_search(

            resource_id,

            limit=1000,

            offset=offset
        )


        records = result.get(
            "records",
            []
        )


        if not records:

            break


        rows = []


        for record in records:

            processed += 1


            try:

                weather_row = build_weather_row(

                    record,

                    state,

                    parameter
                )


                if weather_row is None:

                    skipped += 1

                    continue


                rows.append(
                    weather_row
                )


            except Exception as e:

                skipped += 1

                print(

                    f"SKIPPED | "
                    f"{state} | "
                    f"{parameter} | "
                    f"{e}"
                )


        # Save records in batches

        for i in range(
            0,
            len(rows),
            BATCH_SIZE
        ):

            batch = rows[
                i:i + BATCH_SIZE
            ]


            try:

                count = save_weather_batch(

                    batch,

                    parameter
                )


                saved += count


            except Exception as e:

                db.session.rollback()


                print(

                    f"BATCH ERROR | "
                    f"{state} | "
                    f"{parameter} | "
                    f"{e}"
                )


        print(

            f"{state} | "
            f"{parameter} | "

            f"processed={processed} | "

            f"saved={saved} | "

            f"skipped={skipped}"
        )


        if len(records) < 1000:

            break


        offset += 1000


    print(

        f"COMPLETED | "
        f"{state} | "
        f"{parameter} | "

        f"INSERTED/UPDATED: {saved}"
    )


    return {

        "state": state,

        "parameter": parameter,

        "processed": processed,

        "saved": saved,

        "skipped": skipped
    }


# ============================================================
# HISTORICAL WEATHER IMPORT
#
# Historical resources currently commented.
# Kept for future re-enable.
# ============================================================

def import_weather_data():

    print(
        "\n=========================================="
    )

    print(
        "STARTING HISTORICAL WEATHER IMPORT"
    )

    print(
        "PERIOD: 2021-2025"
    )

    print(
        "=========================================="
    )


    results = []


    for state, parameters in WEATHER_RESOURCES.items():

        for parameter, resources in parameters.items():

            resource_id = resources.get(
                "historical"
            )


            # Historical data currently disabled

            if not resource_id:

                print(

                    f"SKIPPED HISTORICAL | "
                    f"{state} | "
                    f"{parameter} | "
                    f"disabled"
                )

                continue


            result = import_weather_resource(

                resource_id,

                state,

                parameter
            )


            results.append(
                result
            )


    total_saved = sum(

        r.get(
            "saved",
            0
        )

        for r in results
    )


    total_skipped = sum(

        r.get(
            "skipped",
            0
        )

        for r in results
    )


    print(
        "\n=========================================="
    )

    print(
        "HISTORICAL WEATHER IMPORT COMPLETED"
    )

    print(
        f"TOTAL SAVED/UPDATED: "
        f"{total_saved}"
    )

    print(
        f"TOTAL SKIPPED: "
        f"{total_skipped}"
    )

    print(
        "=========================================="
    )


    return {

        "success": True,

        "results": results,

        "total_saved": total_saved,

        "total_skipped": total_skipped
    }


# ============================================================
# FULL CURRENT WEATHER IMPORT
#
# Used once through Thunder Client.
#
# Imports complete available 2026-2030
# data from all active current resources.
# ============================================================

def import_current_weather_data():

    results = []

    total_processed = 0

    total_saved = 0

    total_skipped = 0


    for state, parameters in WEATHER_RESOURCES.items():

        for parameter, resources in parameters.items():

            resource_id = resources.get(
                "current"
            )


            if not resource_id:

                print(

                    f"SKIPPED CURRENT | "
                    f"{state} | "
                    f"{parameter} | "
                    f"no resource id"
                )

                continue


            print(

                f"\nCURRENT IMPORT | "
                f"{state} | "
                f"{parameter}"
            )


            try:

                result = import_weather_resource(

                    resource_id,

                    state,

                    parameter
                )


                processed = result.get(
                    "processed",
                    0
                )

                saved = result.get(
                    "saved",
                    0
                )

                skipped = result.get(
                    "skipped",
                    0
                )


                total_processed += processed

                total_saved += saved

                total_skipped += skipped


                results.append({

                    "state":
                        state,

                    "parameter":
                        parameter,

                    "resource_id":
                        resource_id,

                    "processed":
                        processed,

                    "saved":
                        saved,

                    "skipped":
                        skipped,

                    "success":
                        True
                })


            except Exception as e:

                db.session.rollback()


                print(

                    f"ERROR CURRENT | "
                    f"{state} | "
                    f"{parameter} | "
                    f"{e}"
                )


                results.append({

                    "state":
                        state,

                    "parameter":
                        parameter,

                    "resource_id":
                        resource_id,

                    "success":
                        False,

                    "error":
                        str(e)
                })


                continue


    return {

        "success":
            True,

        "results":
            results,

        "total_processed":
            total_processed,

        "total_saved":
            total_saved,

        "total_skipped":
            total_skipped
    }


# ============================================================
# GET LATEST DB TIME
# ============================================================

def get_latest_db_time(
    state,
    model_field
):

    query = (

        db.session.query(

            func.max(
                WeatherObservation.observed_at
            )
        )

        .join(

            MonitoringStation,

            WeatherObservation.station_id
            ==
            MonitoringStation.id
        )

        .filter(

            MonitoringStation.state
            ==
            state,

            getattr(

                WeatherObservation,

                model_field
            ).isnot(None)
        )
    )


    return query.scalar()


# ============================================================
# FILTER CURRENT RESOURCE RECORDS
#
# Current resources = 2026-2030
# ============================================================

def filter_new_records(
    records,
    latest_time
):

    if latest_time is None:

        cutoff = CURRENT_START

    else:

        cutoff = (
            latest_time
            -
            timedelta(
                minutes=OVERLAP_MINUTES
            )
        )


    filtered = []


    for record in records:

        observed_at = find_value(

            record,

            [
                "Data Acquisition Time",
                "Data acquisition time",
                "data_acquisition_time",
                "Acquisition Time",
                "Acquisition time",
                "acquisition_time",
                "Observed At",
                "observed_at",
                "DateTime",
                "datetime",
                "Timestamp",
                "timestamp"
            ]
        )


        observed_at = parse_datetime(
            observed_at
        )


        if observed_at is None:

            continue


        if observed_at < CURRENT_START:

            continue


        if observed_at < cutoff:

            continue


        filtered.append(
            record
        )


    return filtered


# ============================================================
# UPDATE ONE CURRENT RESOURCE
# ============================================================

def update_weather_resource(
    resource_id,
    state,
    parameter
):

    print(

        f"\nWEATHER UPDATE | "
        f"{state} | "
        f"{parameter} | "
        f"{resource_id}"
    )


    model_field = PARAMETER_FIELDS[
        parameter
    ]


    latest_time = get_latest_db_time(

        state,

        model_field
    )


    try:

        # ----------------------------------------------------
        # Fetch newest records first.
        #
        # This avoids downloading the entire 2026-2030
        # resource every scheduled run.
        # ----------------------------------------------------

        result = datastore_search(

            resource_id,

            limit=1000,

            offset=0
        )


        records = result.get(
            "records",
            []
        )


        if not records:

            print(

                f"NO DATA | "
                f"{state} | "
                f"{parameter}"
            )


            return {

                "success":
                    True,

                "state":
                    state,

                "parameter":
                    parameter,

                "updated":
                    0
            }


        records = filter_new_records(

            records,

            latest_time
        )


        if not records:

            print(

                f"NO NEW DATA | "
                f"{state} | "
                f"{parameter}"
            )


            return {

                "success":
                    True,

                "state":
                    state,

                "parameter":
                    parameter,

                "updated":
                    0
            }


        rows = []


        for record in records:

            try:

                weather_row = build_weather_row(

                    record,

                    state,

                    parameter
                )


                if weather_row:

                    rows.append(
                        weather_row
                    )

            except Exception as e:

                print(

                    f"UPDATE RECORD SKIPPED | "
                    f"{state} | "
                    f"{parameter} | "
                    f"{e}"
                )


        updated = 0


        for i in range(

            0,

            len(rows),

            BATCH_SIZE

        ):

            batch = rows[

                i:i + BATCH_SIZE

            ]


            try:

                updated += save_weather_batch(

                    batch,

                    parameter
                )


            except Exception as e:

                db.session.rollback()


                print(

                    f"UPDATE BATCH ERROR | "
                    f"{state} | "
                    f"{parameter} | "
                    f"{e}"
                )


        print(

            f"UPDATED | "
            f"{state} | "
            f"{parameter} | "
            f"{updated}"
        )


        return {

            "success":
                True,

            "state":
                state,

            "parameter":
                parameter,

            "updated":
                updated
        }


    except requests.exceptions.RequestException as e:

        db.session.rollback()


        print(

            f"SOURCE UNAVAILABLE | "
            f"{state} | "
            f"{parameter} | "
            f"{e}"
        )


        return {

            "success":
                False,

            "state":
                state,

            "parameter":
                parameter,

            "error":
                str(e)
        }


    except Exception as e:

        db.session.rollback()


        print(

            f"UPDATE ERROR | "
            f"{state} | "
            f"{parameter} | "
            f"{e}"
        )


        return {

            "success":
                False,

            "state":
                state,

            "parameter":
                parameter,

            "error":
                str(e)
        }


# ============================================================
# INCREMENTAL WEATHER UPDATE
#
# Uses 2026-2030 resources.
#
# Called automatically by APScheduler.
# ============================================================

def update_weather_data():

    print(
        "\n=========================================="
    )

    print(
        "STARTING INCREMENTAL WEATHER UPDATE"
    )

    print(
        "PERIOD: 2026+"
    )

    print(
        "=========================================="
    )


    results = []


    for state, parameters in WEATHER_RESOURCES.items():

        for parameter, resources in parameters.items():

            resource_id = resources.get(
                "current"
            )


            if not resource_id:

                print(

                    f"SKIPPED CURRENT | "
                    f"{state} | "
                    f"{parameter} | "
                    f"no resource id"
                )

                continue


            result = update_weather_resource(

                resource_id,

                state,

                parameter
            )


            results.append(
                result
            )


    total_updated = sum(

        r.get(
            "updated",
            0
        )

        for r in results
    )


    print(
        "\n=========================================="
    )

    print(
        "INCREMENTAL WEATHER UPDATE COMPLETED"
    )

    print(
        f"TOTAL UPDATED: "
        f"{total_updated}"
    )

    print(
        "=========================================="
    )


    return {

        "success":
            True,

        "results":
            results,

        "total_updated":
            total_updated
    }


# ============================================================
# APSCHEDULER WRAPPER
# ============================================================

def scheduled_weather_update(
    app
):

    try:

        with app.app_context():

            print(

                "\n[SCHEDULER] "
                "Checking weather data..."
            )


            result = update_weather_data()


            print(

                "[SCHEDULER] "
                "WEATHER RESULT:",
                result
            )


    except Exception as e:

        print(

            "[SCHEDULER] "
            "WEATHER UPDATE ERROR:",
            e
        )


# ============================================================
# NEARBY WEATHER
# ============================================================

def get_nearby_weather(
    latitude,
    longitude,
    radius_km=25
):

    try:

        point = WKTElement(

            f"POINT({longitude} {latitude})",

            srid=4326
        )


        distance_m = (
            radius_km * 1000
        )


        stations = (

            db.session.query(
                MonitoringStation
            )

            .filter(

                func.ST_DWithin(

                    MonitoringStation.location,

                    point,

                    distance_m
                )
            )

            .all()
        )


        results = []


        for station in stations:

            latest = (

                WeatherObservation.query

                .filter_by(

                    station_id=station.id
                )

                .order_by(

                    WeatherObservation.observed_at.desc()
                )

                .first()
            )


            if latest is None:

                continue


            results.append({

                "station_id":
                    station.id,

                "station_name":
                    station.station_name,

                "agency":
                    station.agency,

                "state":
                    station.state,

                "district":
                    station.district,

                "observed_at":
                    latest.observed_at.isoformat(),

                "temperature_c":
                    latest.temperature_c,

                "humidity_percent":
                    latest.humidity_percent,

                "rainfall_mm":
                    latest.rainfall_mm,

                "wind_speed_kmh":
                    latest.wind_speed_kmh,

                "wind_direction_deg":
                    latest.wind_direction_deg,

                "pressure_mb":
                    latest.pressure_mb,

                "solar_radiation_wm2":
                    latest.solar_radiation_wm2
            })


        return {

            "success":
                True,

            "count":
                len(results),

            "weather":
                results
        }


    except Exception as e:

        db.session.rollback()


        return {

            "success":
                False,

            "error":
                str(e)
        }