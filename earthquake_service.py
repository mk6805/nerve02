import requests
from datetime import datetime, timezone
from geoalchemy2 import WKTElement
from sqlalchemy import text
from extension import db
from models import Disaster, Earthquake
from location_service import reverse_geocode


def import_earthquakes():
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    latest_disaster = Disaster.query.filter_by(source="USGS").order_by(Disaster.start_time.desc()).first()

    if latest_disaster and latest_disaster.start_time:
        starttime = latest_disaster.start_time.strftime("%Y-%m-%dT%H:%M:%S")
    else:
        starttime = "2016-08-29T00:00:00"

    endtime = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "format": "geojson",
        "starttime": starttime,
        "endtime": endtime,
        "minlatitude": 6,
        "maxlatitude": 37,
        "minlongitude": 68,
        "maxlongitude": 98,
        "eventtype": "earthquake",
        "minmagnitude": 2.5,
        "limit": 20000
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print("USGS API ERROR:", e)
        return {"success": False, "error": str(e)}

    inserted = 0
    skipped = 0

    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])

        if len(coordinates) < 2:
            continue

        longitude = coordinates[0]
        latitude = coordinates[1]
        depth_km = coordinates[2] if len(coordinates) >= 3 else None

        source_event_id = feature.get("id")
        event_name = properties.get("title")
        magnitude = properties.get("mag")
        magnitude_type = properties.get("magType")
        description = properties.get("title")

        event_time = properties.get("time")
        start_time = datetime.fromtimestamp(event_time / 1000, timezone.utc) if event_time else None

        location = WKTElement(f"POINT({longitude} {latitude})", srid=4326)

        place_name = None
        city = None
        district = None
        state = None
        country = None

        try:
            location_data = reverse_geocode(latitude, longitude)
            address = location_data.get("address", {})

            place_name = address.get("neighbourhood") or address.get("suburb") or address.get("quarter") or address.get("city_district")
            city = address.get("city") or address.get("town") or address.get("municipality") or address.get("village")
            district = address.get("state_district") or address.get("district")
            state = address.get("state")
            country = address.get("country")
        except Exception as e:
            print("REVERSE GEOCODE ERROR:", e)

        if magnitude is None:
            severity = "UNKNOWN"
        elif magnitude >= 6:
            severity = "CRITICAL"
        elif magnitude >= 5:
            severity = "HIGH"
        elif magnitude >= 4:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        existing = Disaster.query.filter_by(source="USGS", source_event_id=source_event_id).first()

        if existing:
            skipped += 1
            continue

        disaster = Disaster(
            disaster_type="earthquake",
            event_name=event_name,
            start_time=start_time,
            location=location,
            severity=severity,
            source="USGS",
            source_event_id=source_event_id,
            description=description,
            place_name=place_name,
            city=city,
            district=district,
            state=state,
            country=country
        )

        db.session.add(disaster)
        db.session.flush()

        earthquake = Earthquake(
            disaster_id=disaster.id,
            magnitude=magnitude,
            magnitude_type=magnitude_type,
            depth_km=depth_km
        )

        db.session.add(earthquake)
        inserted += 1

    db.session.commit()

    result = {
        "success": True,
        "events_received": len(data.get("features", [])),
        "inserted": inserted,
        "skipped_duplicates": skipped
    }

    print("EARTHQUAKE IMPORT:", result)
    return result


def update_earthquake_records():
    url = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    params = {
        "format": "geojson",
        "starttime": "2016-08-29",
        "endtime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "minlatitude": 6,
        "maxlatitude": 37,
        "minlongitude": 68,
        "maxlongitude": 98,
        "eventtype": "earthquake",
        "minmagnitude": 2.5,
        "limit": 20000
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        raise Exception(f"USGS API request failed: {e}")

    updated = 0

    for feature in data.get("features", []):
        source_event_id = feature.get("id")

        disaster = Disaster.query.filter_by(source="USGS", source_event_id=source_event_id).first()

        if not disaster:
            continue

        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [])

        earthquake = Earthquake.query.filter_by(disaster_id=disaster.id).first()

        if not earthquake:
            continue

        magnitude = properties.get("mag")
        magnitude_type = properties.get("magType")

        event_time = properties.get("time")
        start_time = datetime.fromtimestamp(event_time / 1000, timezone.utc) if event_time else None

        earthquake.magnitude = magnitude
        earthquake.magnitude_type = magnitude_type

        if len(coordinates) >= 3:
            earthquake.depth_km = coordinates[2]

        disaster.event_name = properties.get("title")
        disaster.description = properties.get("title")
        disaster.start_time = start_time

        if magnitude is None:
            disaster.severity = "UNKNOWN"
        elif magnitude >= 6:
            disaster.severity = "CRITICAL"
        elif magnitude >= 5:
            disaster.severity = "HIGH"
        elif magnitude >= 4:
            disaster.severity = "MEDIUM"
        else:
            disaster.severity = "LOW"

        updated += 1

    db.session.commit()

    return {
        "success": True,
        "message": "Earthquake records updated",
        "updated": updated
    }


def get_nearby_earthquakes(latitude, longitude, radius_km):
    radius_meters = radius_km * 1000

    query = text("""
        SELECT
            d.id AS disaster_id,
            d.event_name,
            d.start_time,
            d.source,
            e.id AS earthquake_id,
            e.magnitude,
            e.magnitude_type,
            e.depth_km,
            ST_Distance(
                d.location,
                ST_SetSRID(
                    ST_MakePoint(:longitude, :latitude),
                    4326
                )::geography
            ) AS distance_meters
        FROM disaster d
        JOIN earthquake e ON d.id = e.disaster_id
        WHERE d.disaster_type = 'earthquake'
        AND ST_DWithin(
            d.location,
            ST_SetSRID(
                ST_MakePoint(:longitude, :latitude),
                4326
            )::geography,
            :radius
        )
        ORDER BY distance_meters ASC
    """)

    result = db.session.execute(query, {
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius_meters
    })

    earthquakes = []

    for row in result:
        earthquakes.append({
            "disaster_id": row.disaster_id,
            "earthquake_id": row.earthquake_id,
            "event_name": row.event_name,
            "start_time": row.start_time.isoformat() if row.start_time else None,
            "magnitude": row.magnitude,
            "magnitude_type": row.magnitude_type,
            "depth_km": row.depth_km,
            "source": row.source,
            "distance_km": round(row.distance_meters / 1000, 2)
        })

    return earthquakes

def scheduled_earthquake_update():
    try:
        result = update_earthquake_records()
        print("SCHEDULED EARTHQUAKE UPDATE:", result)
    except Exception as e:
        print("SCHEDULED EARTHQUAKE UPDATE ERROR:", e)