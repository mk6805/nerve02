import pandas as pd
from sqlalchemy import text
from extension import db
from models import Disaster, Flood
from geoalchemy2 import WKTElement
from location_service import reverse_geocode
from datetime import datetime


FLOOD_FILE = "India_Flood_inventory_v3.csv"


def import_floods():
    try:
        df = pd.read_csv(FLOOD_FILE)

        inserted = 0
        skipped = 0

        for _, row in df.iterrows():

            latitude = row.get("latitude")
            longitude = row.get("longitude")

            if pd.isna(latitude) or pd.isna(longitude):
                skipped += 1
                continue

            source_event_id = str(row.get("uei") or row.get("id") or inserted)

            existing = Disaster.query.filter_by(
                source="India Flood Inventory",
                source_event_id=source_event_id
            ).first()

            if existing:
                skipped += 1
                continue

            location = WKTElement(
                f"POINT({longitude} {latitude})",
                srid=4326
            )

            disaster = Disaster(
                disaster_type="flood",
                event_name=str(row.get("event_name") or "Flood"),
                start_time=pd.to_datetime(row.get("event_date"), errors="coerce"),
                location=location,
                severity=str(row.get("severity")) if not pd.isna(row.get("severity")) else None,
                source="India Flood Inventory",
                source_event_id=source_event_id,
                description=str(row.get("description")) if not pd.isna(row.get("description")) else None,
                place_name=str(row.get("place_name")) if not pd.isna(row.get("place_name")) else None,
                district=str(row.get("district")) if not pd.isna(row.get("district")) else None,
                state=str(row.get("state")) if not pd.isna(row.get("state")) else None,
                country="India"
            )

            db.session.add(disaster)
            db.session.flush()

            flood = Flood(
                disaster_id=disaster.id,
                uei=str(row.get("uei")) if not pd.isna(row.get("uei")) else None,
                main_cause=str(row.get("main_cause")) if not pd.isna(row.get("main_cause")) else None,
                location_description=str(row.get("location_description")) if not pd.isna(row.get("location_description")) else None,
                area_affected_value=float(row.get("area_affected_value")) if not pd.isna(row.get("area_affected_value")) else None,
                area_affected_unit=str(row.get("area_affected_unit")) if not pd.isna(row.get("area_affected_unit")) else None,
                human_fatality=int(row.get("human_fatality")) if not pd.isna(row.get("human_fatality")) else None,
                injured=int(row.get("injured")) if not pd.isna(row.get("injured")) else None,
                displaced=int(row.get("displaced")) if not pd.isna(row.get("displaced")) else None,
                animal_fatality=int(row.get("animal_fatality")) if not pd.isna(row.get("animal_fatality")) else None,
                casualty_description=str(row.get("casualty_description")) if not pd.isna(row.get("casualty_description")) else None,
                extent_of_damage=str(row.get("extent_of_damage")) if not pd.isna(row.get("extent_of_damage")) else None,
                district_lgd_codes=str(row.get("district_lgd_codes")) if not pd.isna(row.get("district_lgd_codes")) else None,
                state_code=str(row.get("state_code")) if not pd.isna(row.get("state_code")) else None
            )

            db.session.add(flood)
            inserted += 1

        db.session.commit()

        return {
            "success": True,
            "inserted": inserted,
            "skipped": skipped
        }

    except Exception as e:
        db.session.rollback()
        return {
            "success": False,
            "error": str(e)
        }


def update_flood_records():
    try:
        df = pd.read_csv(FLOOD_FILE)

        updated = 0

        for _, row in df.iterrows():

            source_event_id = str(row.get("uei") or row.get("id") or "")

            if not source_event_id:
                continue

            disaster = Disaster.query.filter_by(
                source="India Flood Inventory",
                source_event_id=source_event_id
            ).first()

            if not disaster:
                continue

            flood = Flood.query.filter_by(
                disaster_id=disaster.id
            ).first()

            if not flood:
                continue

            flood.main_cause = str(row.get("main_cause")) if not pd.isna(row.get("main_cause")) else None
            flood.location_description = str(row.get("location_description")) if not pd.isna(row.get("location_description")) else None
            flood.area_affected_value = float(row.get("area_affected_value")) if not pd.isna(row.get("area_affected_value")) else None
            flood.area_affected_unit = str(row.get("area_affected_unit")) if not pd.isna(row.get("area_affected_unit")) else None
            flood.human_fatality = int(row.get("human_fatality")) if not pd.isna(row.get("human_fatality")) else None
            flood.injured = int(row.get("injured")) if not pd.isna(row.get("injured")) else None
            flood.displaced = int(row.get("displaced")) if not pd.isna(row.get("displaced")) else None
            flood.animal_fatality = int(row.get("animal_fatality")) if not pd.isna(row.get("animal_fatality")) else None
            flood.casualty_description = str(row.get("casualty_description")) if not pd.isna(row.get("casualty_description")) else None
            flood.extent_of_damage = str(row.get("extent_of_damage")) if not pd.isna(row.get("extent_of_damage")) else None

            updated += 1

        db.session.commit()

        return {
            "success": True,
            "updated": updated
        }

    except Exception as e:
        db.session.rollback()
        return {
            "success": False,
            "error": str(e)
        }


def scheduled_flood_update():
    try:
        print("Checking flood records...")
        result = update_flood_records()
        print("FLOOD UPDATE RESULT:", result)
    except Exception as e:
        print("SCHEDULED FLOOD UPDATE ERROR:", e)


def get_nearby_floods(latitude, longitude, radius_km):

    radius_meters = radius_km * 1000

    query = text("""
        SELECT
            d.id AS disaster_id,
            d.event_name,
            d.start_time,
            d.end_time,
            d.severity,
            d.source,
            d.description,
            d.place_name,
            d.district,
            d.state,

            f.id AS flood_id,
            f.uei,
            f.main_cause,
            f.location_description,
            f.area_affected_value,
            f.area_affected_unit,
            f.human_fatality,
            f.injured,
            f.displaced,
            f.animal_fatality,
            f.casualty_description,
            f.extent_of_damage,
            f.district_lgd_codes,
            f.state_code,

            ST_Distance(
                d.location,
                ST_SetSRID(
                    ST_MakePoint(:longitude, :latitude),
                    4326
                )::geography
            ) AS distance_meters

        FROM disaster d

        JOIN flood f ON d.id = f.disaster_id

        WHERE d.disaster_type = 'flood'
        AND d.location IS NOT NULL

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

    result = db.session.execute(
        query,
        {
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius_meters
        }
    )

    floods = []

    for row in result:
        floods.append({
            "disaster_id": row.disaster_id,
            "flood_id": row.flood_id,
            "event_name": row.event_name,
            "start_time": row.start_time.isoformat() if row.start_time else None,
            "end_time": row.end_time.isoformat() if row.end_time else None,
            "severity": row.severity,
            "source": row.source,
            "description": row.description,
            "place_name": row.place_name,
            "district": row.district,
            "state": row.state,
            "uei": row.uei,
            "main_cause": row.main_cause,
            "location_description": row.location_description,
            "area_affected_value": row.area_affected_value,
            "area_affected_unit": row.area_affected_unit,
            "human_fatality": row.human_fatality,
            "injured": row.injured,
            "displaced": row.displaced,
            "animal_fatality": row.animal_fatality,
            "casualty_description": row.casualty_description,
            "extent_of_damage": row.extent_of_damage,
            "district_lgd_codes": row.district_lgd_codes,
            "state_code": row.state_code,
            "distance_km": round(row.distance_meters / 1000, 2)
        })

    return floods