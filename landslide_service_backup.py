import re

from models import db, Disaster, Landslide


TARGET_STATES = {
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
}

LAT_MIN = 20.0
LAT_MAX = 30.0
LON_MIN = 88.0
LON_MAX = 98.0


def clean_text(value):
    if value is None:
        return ""

    value = re.sub(r"\s+", " ", value)
    return value.strip()


def valid_coordinates(latitude, longitude):
    return (
        LAT_MIN <= latitude <= LAT_MAX
        and LON_MIN <= longitude <= LON_MAX
    )


def find_coordinate_pairs(text):
    """
    Find valid latitude/longitude pairs.

    We do NOT use a simple regex such as:
        number number

    because that can incorrectly detect things like:
        NH-154 24.44 92.56

    Instead, numbers are checked as consecutive numeric tokens
    and validated against the geographic range of our four states.
    """

    numbers = re.findall(
        r"\d+(?:\.\d+)?",
        text
    )

    for i in range(len(numbers) - 1):

        latitude = float(numbers[i])
        longitude = float(numbers[i + 1])

        if valid_coordinates(latitude, longitude):
            return latitude, longitude

    return None, None

def extract_rows(text):
    """
    Extract GSI landslide records using the serial number as
    the primary record boundary.

    We do not assume that Slide_No is a single token because
    GSI PDF extraction sometimes contains spaces/newlines inside it.
    """

    # A valid record starts with:
    # serial number + slide number + target state
    #
    # Slide_No is allowed to contain spaces, /, -, _, etc.
    pattern = re.compile(
        r"(?m)^\s*"
        r"(?P<sl_no>\d+)\s+"
        r"(?P<slide_no>.*?)"
        r"\s+(?P<state>Assam|Manipur|Meghalaya|Mizoram)"
        r"(?=\s)",
        re.IGNORECASE,
    )

    matches = list(pattern.finditer(text))

    rows = []

    for index, match in enumerate(matches):

        state = match.group("state").title()

        if state not in TARGET_STATES:
            continue

        start = match.end()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        body = text[start:end]

        rows.append(
            {
                "sl_no": int(match.group("sl_no")),
                "slide_no": clean_text(match.group("slide_no")),
                "state": state,
                "body": body,
            }
        )

    return rows


def parse_landslide_rows(text):
    """
    Convert raw GSI rows into structured landslide records.
    """

    parsed = []

    rows = extract_rows(text)

    for row in rows:

        body = clean_text(row["body"])

        latitude, longitude = find_coordinate_pairs(body)

        # User decided to ignore records without recoverable coordinates.
        if latitude is None or longitude is None:
            continue

        # ---------------------------------------------------------
        # Find coordinate pair inside the original body
        # ---------------------------------------------------------

        coordinate_match = None

        for match in re.finditer(
            r"\d+(?:\.\d+)?\s+\d+(?:\.\d+)?",
            body,
        ):

            numbers = re.findall(
                r"\d+(?:\.\d+)?",
                match.group()
            )

            if len(numbers) != 2:
                continue

            lat = float(numbers[0])
            lon = float(numbers[1])

            if valid_coordinates(lat, lon):
                coordinate_match = match
                break

        if coordinate_match is None:
            continue

        before_coordinates = clean_text(
            body[:coordinate_match.start()]
        )

        after_coordinates = clean_text(
            body[coordinate_match.end():]
        )

        # ---------------------------------------------------------
        # District
        # ---------------------------------------------------------

        parts = before_coordinates.split(
            maxsplit=1
        )

        if parts:
            district = parts[0]
        else:
            district = None

        # Remaining text contains Slide_Name / NH_SH_Location.
        if len(parts) > 1:
            location_text = clean_text(parts[1])
        else:
            location_text = ""

        # ---------------------------------------------------------
        # Material / Movement / History
        # ---------------------------------------------------------

        material = None
        movement = None
        history = None

        material_match = re.match(
            r"^(Debris|Earth|Rock|Soil|Mud)"
            r"(?:\s+|$)",
            after_coordinates,
            re.IGNORECASE,
        )

        if material_match:

            material = material_match.group(1)

            remainder = clean_text(
                after_coordinates[
                    material_match.end():
                ]
            )

        else:
            remainder = after_coordinates

        movement_match = re.match(
            r"^(Slide|Flow|Fall|Topple|Avalanche|"
            r"Subsidence|Deep\s+translational|"
            r"Complex\s+movement)"
            r"(?:\s+|$)",
            remainder,
            re.IGNORECASE,
        )

        if movement_match:

            movement = clean_text(
                movement_match.group(1)
            )

            history = clean_text(
                remainder[movement_match.end():]
            )

        else:

            history = clean_text(
                remainder
            )

        # ---------------------------------------------------------
        # Prevent database VARCHAR(255) failure
        # ---------------------------------------------------------

        if history:
            history = history[:255]

        if district:
            district = district[:150]

        slide_name = location_text[:255]

        nh_sh_location = location_text

        parsed.append(
            {
                "sl_no": row["sl_no"],
                "slide_no": row["slide_no"],
                "state": row["state"],
                "district": district,
                "slide_name": slide_name,
                "nh_sh_location": nh_sh_location,
                "latitude": latitude,
                "longitude": longitude,
                "material_involved": material,
                "movement_type": movement,
                "history": history,
            }
        )

    return parsed


def import_landslides(
    text_file="landslide_text.txt"
):
    """
    Import GSI landslide inventory.

    Source:
        GSI Landslide Inventory

    States:
        Assam
        Manipur
        Meghalaya
        Mizoram

    Records without valid coordinates are ignored.
    """

    with open(
        text_file,
        "r",
        encoding="utf-8"
    ) as file:

        text = file.read()

    rows = parse_landslide_rows(text)

    inserted = 0
    skipped = 0

    for row in rows:

        slide_no = row["slide_no"]

        # GSI Slide_No is used as the source identifier.
        source_event_id = (
            f"GSI-{row['state']}-{slide_no}"
        )

        existing = Disaster.query.filter_by(
            source="GSI",
            source_event_id=source_event_id
        ).first()

        if existing:
            skipped += 1
            continue

        # ---------------------------------------------------------
        # Parent Disaster record
        # ---------------------------------------------------------

        disaster = Disaster(
            disaster_type="landslide",

            event_name=row["slide_name"],

            location=(
                f"SRID=4326;POINT("
                f"{row['longitude']} "
                f"{row['latitude']}"
                f")"
            ),

            severity=None,

            source="GSI",

            source_event_id=source_event_id,

            description=(
                row["nh_sh_location"]
                if row["nh_sh_location"]
                else None
            ),

            state=row["state"],

            district=row["district"],

            country="India",
        )

        db.session.add(disaster)

        db.session.flush()

        # ---------------------------------------------------------
        # Landslide-specific record
        # ---------------------------------------------------------

        landslide = Landslide(
            disaster_id=disaster.id,

            slide_no=row["slide_no"],

            slide_name=row["slide_name"],

            nh_sh_location=row["nh_sh_location"],

            material_involved=(
                row["material_involved"]
            ),

            movement_type=(
                row["movement_type"]
            ),

            history=row["history"],
        )

        db.session.add(landslide)

        inserted += 1

    db.session.commit()

    result = {
        "success": True,
        "parsed_records": len(rows),
        "inserted": inserted,
        "skipped_duplicates": skipped,
    }

    print(
        "LANDSLIDE IMPORT:",
        result
    )

    return result
