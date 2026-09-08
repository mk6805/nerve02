from flask import (
    Blueprint,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session
)

from oauth_config import oauth
from extension import db
from models import Disaster, UserLocation,User
from geoalchemy2 import WKTElement
from location_service import reverse_geocode
from datetime import datetime
from disaster_service import (
    get_nearby_disasters,
    check_nearby_risk
)

from earthquake_service import (
    import_earthquakes,
    update_earthquake_records,
    get_nearby_earthquakes
)


from river_service import (
    import_river_data,
    update_river_data,
    get_nearby_river_data
)

from weather_service import (
    import_weather_data,
    import_current_weather_data,
    update_weather_data,
    get_nearby_weather
)

import requests


bp = Blueprint("main", __name__)


# ============================================================
# PAGES
# ============================================================

@bp.route("/")
def home():
    return render_template("index.html")


@bp.route("/location")
def location_page():
    return render_template("location.html")


@bp.route("/risk")
def risk_page():
    return render_template("risk.html")


# ============================================================
# LOCATION
# ============================================================

@bp.route("/api/location", methods=["POST"])
def location():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)

        if not -90 <= latitude <= 90:
            return jsonify({
                "error": "Invalid latitude"
            }), 400

        if not -180 <= longitude <= 180:
            return jsonify({
                "error": "Invalid longitude"
            }), 400

        geocode_result = reverse_geocode(
            latitude,
            longitude
        )

        # Your location_service may return either
        # {"address": {...}} or directly return address data.
        address = geocode_result.get(
            "address",
            geocode_result
        )

        place_name = (
            address.get("neighbourhood")
            or address.get("suburb")
            or address.get("quarter")
            or address.get("city_district")
        )

        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("village")
        )

        district = (
            address.get("state_district")
            or address.get("district")
        )

        state = address.get("state")
        country = address.get("country")

        user_location = UserLocation(
            user_id=session["user_id"], 
            latitude=latitude,
            longitude=longitude,
            location=WKTElement(
                f"POINT({longitude} {latitude})",
                srid=4326
            ),
            place_name=place_name,
            city=city,
            district=district,
            state=state,
            country=country
        )

        db.session.add(user_location)
        db.session.commit()

        return jsonify({
            "message": "Location stored successfully",
            "location_id": user_location.id,
            "latitude": latitude,
            "longitude": longitude,
            "place_name": place_name,
            "city": city,
            "district": district,
            "state": state,
            "country": country
        })

    except requests.RequestException as e:

        return jsonify({
            "error": "Reverse geocoding failed",
            "details": str(e)
        }), 502

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "error": "Failed to save location",
            "details": str(e)
        }), 500


# ============================================================
# TEST DISASTER
# ============================================================

@bp.route("/api/test-disaster", methods=["POST"])
def test_disaster():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    disaster_type = data.get("disaster_type")
    event_name = data.get("event_name", "Test Disaster")
    severity = data.get("severity")

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)

        disaster = Disaster(
            disaster_type=disaster_type,
            event_name=event_name,
            location=WKTElement(
                f"POINT({longitude} {latitude})",
                srid=4326
            ),
            severity=severity,
            source="manual-test"
        )

        db.session.add(disaster)
        db.session.commit()

        return jsonify({
            "message": "Disaster added successfully",
            "id": disaster.id
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "error": "Failed to add disaster",
            "details": str(e)
        }), 500


# ============================================================
# ALL NEARBY DISASTERS
# ============================================================

@bp.route("/api/nearby", methods=["POST"])
def nearby_disasters():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius_km = data.get("radius_km", 20)
    disaster_type = data.get("disaster_type")

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)
        radius_km = float(radius_km)

        if not -90 <= latitude <= 90:
            return jsonify({
                "error": "Invalid latitude"
            }), 400

        if not -180 <= longitude <= 180:
            return jsonify({
                "error": "Invalid longitude"
            }), 400

        if radius_km <= 0:
            return jsonify({
                "error": "Radius must be greater than 0"
            }), 400

        disasters = get_nearby_disasters(
            latitude,
            longitude,
            radius_km,
            disaster_type
        )

        return jsonify({
            "user_location": {
                "latitude": latitude,
                "longitude": longitude
            },
            "radius_km": radius_km,
            "disaster_type": disaster_type or "all",
            "count": len(disasters),
            "disasters": disasters
        })

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid latitude, longitude or radius"
        }), 400

    except Exception as e:

        return jsonify({
            "error": "Failed to find nearby disasters",
            "details": str(e)
        }), 500


# ============================================================
# RISK
# ============================================================

@bp.route("/api/check-risk", methods=["POST"])
def check_risk():

    data = request.get_json() or {}

    radius_km = data.get("radius_km", 20)

    try:

        radius_km = float(radius_km)

        if radius_km <= 0:
            return jsonify({
                "error": "Radius must be greater than 0"
            }), 400

        result = check_nearby_risk(
            radius_km
        )

        if result is None:
            return jsonify({
                "error": "No user location found. Please set your location first."
            }), 404

        return jsonify(result)

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid radius"
        }), 400

    except Exception as e:

        return jsonify({
            "error": "Failed to check nearby risk",
            "details": str(e)
        }), 500


# ============================================================
# EARTHQUAKES
# ============================================================

@bp.route("/api/import-earthquakes", methods=["POST"])
def import_earthquakes_api():

    try:

        result = import_earthquakes()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to import earthquakes",
            "details": str(e)
        }), 500


@bp.route("/api/update-earthquakes", methods=["POST"])
def update_earthquakes():

    try:

        result = update_earthquake_records()

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to update earthquake records",
            "details": str(e)
        }), 500


@bp.route("/api/earthquakes/nearby", methods=["POST"])
def nearby_earthquakes():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius_km = data.get("radius_km", 100)

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)
        radius_km = float(radius_km)

        if radius_km <= 0:
            return jsonify({
                "error": "Radius must be greater than 0"
            }), 400

        earthquakes = get_nearby_earthquakes(
            latitude,
            longitude,
            radius_km
        )

        return jsonify({
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "count": len(earthquakes),
            "earthquakes": earthquakes
        })

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid latitude, longitude or radius"
        }), 400

    except Exception as e:

        return jsonify({
            "error": "Failed to find nearby earthquakes",
            "details": str(e)
        }), 500


# ============================================================
# WEATHER
# ============================================================

@bp.route("/api/import-weather", methods=["POST"])
def import_weather():

    try:

        result = import_weather_data()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to import weather data",
            "details": str(e)
        }), 500


@bp.route("/api/update-weather", methods=["POST"])
def update_weather():

    try:

        result = update_weather_data()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to update weather data",
            "details": str(e)
        }), 500


@bp.route("/api/weather/nearby", methods=["POST"])
def nearby_weather():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius_km = data.get("radius_km", 25)

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)
        radius_km = float(radius_km)

        if radius_km <= 0:
            return jsonify({
                "error": "Radius must be greater than 0"
            }), 400

        weather = get_nearby_weather(
            latitude,
            longitude,
            radius_km
        )

        return jsonify({
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "count": len(weather),
            "weather": weather
        })

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid latitude, longitude or radius"
        }), 400

    except Exception as e:

        return jsonify({
            "error": "Failed to find nearby weather",
            "details": str(e)
        }), 500


# ============================================================
# RIVER / HYDROLOGY
# ============================================================

@bp.route("/api/import-river", methods=["POST"])
def import_river():

    try:

        result = import_river_data()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to import river data",
            "details": str(e)
        }), 500


@bp.route("/api/update-river", methods=["POST"])
def update_river():

    try:

        result = update_river_data()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to update river data",
            "details": str(e)
        }), 500


@bp.route("/api/river/nearby", methods=["POST"])
def nearby_river():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius_km = data.get("radius_km", 50)
    limit = data.get("limit", 100)

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)
        radius_km = float(radius_km)
        limit = int(limit)

        if radius_km <= 0:
            return jsonify({
                "error": "Radius must be greater than 0"
            }), 400

        if limit <= 0 or limit > 500:
            return jsonify({
                "error": "Limit must be between 1 and 500"
            }), 400

        river_data = get_nearby_river_data(
            latitude,
            longitude,
            radius_km,
            limit
        )

        return jsonify({
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "count": len(river_data),
            "river_data": river_data
        })

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid latitude, longitude, radius or limit"
        }), 400

    except Exception as e:

        return jsonify({
            "error": "Failed to find nearby river data",
            "details": str(e)
        }), 500


# ============================================================
# HISTORICAL FLOODS
# ============================================================

@bp.route("/api/import-floods", methods=["POST"])
def import_flood_data():

    try:

        result = import_floods()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to import flood data",
            "details": str(e)
        }), 500


@bp.route("/api/update-floods", methods=["POST"])
def update_flood_data():

    try:

        result = update_flood_records()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to update flood records",
            "details": str(e)
        }), 500


@bp.route("/api/floods/nearby", methods=["POST"])
def nearby_floods():

    data = request.get_json() or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")
    radius_km = data.get("radius_km", 50)

    if latitude is None or longitude is None:
        return jsonify({
            "error": "Latitude and longitude are required"
        }), 400

    try:

        latitude = float(latitude)
        longitude = float(longitude)
        radius_km = float(radius_km)

        if radius_km <= 0:
            return jsonify({
                "error": "Radius must be greater than 0"
            }), 400

        floods = get_nearby_floods(
            latitude,
            longitude,
            radius_km
        )

        return jsonify({
            "latitude": latitude,
            "longitude": longitude,
            "radius_km": radius_km,
            "count": len(floods),
            "floods": floods
        })

    except (TypeError, ValueError):

        return jsonify({
            "error": "Invalid latitude, longitude or radius"
        }), 400

    except Exception as e:

        return jsonify({
            "error": "Failed to find nearby floods",
            "details": str(e)
        }), 500

@bp.route("/api/import-current-weather", methods=["POST"])
def import_current_weather():

    try:

        result = import_current_weather_data()

        if not result.get("success"):
            return jsonify(result), 502

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "error": "Failed to import current weather data",
            "details": str(e)
        }), 500

@bp.route("/auth/callback")
def auth_callback():

    token = oauth.google.authorize_access_token()

    userinfo = token.get("userinfo")

    if not userinfo:
        return jsonify({
            "error": "Google user information not received"
        }), 400

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name")
    # picture = userinfo.get("picture")

    if not google_id or not email:
        return jsonify({
            "error": "Incomplete Google user information"
        }), 400

    # ==========================================
    # FIND USER BY GOOGLE ACCOUNT
    # ==========================================

    user = User.query.filter_by(
        oauth_provider="google",
        oauth_provider_id=google_id
    ).first()

    # ==========================================
    # IF USER DOES NOT EXIST
    # ==========================================

    if not user:

        # First check whether email already exists
        user = User.query.filter_by(
            email=email
        ).first()

        if user:

            # Existing local account
            # Link Google account to it

            user.oauth_provider = "google"
            user.oauth_provider_id = google_id
            user.name = name or user.name
            user.is_verified = True
            user.last_login_at = datetime.utcnow()

        else:

            # Create new Google user

            user = User(
                name=name or "Google User",
                email=email,
                oauth_provider="google",
                oauth_provider_id=google_id,
                role="user",
                is_active=True,
                is_verified=True,
                last_login_at=datetime.utcnow()
            )

            db.session.add(user)

    else:

        # ======================================
        # EXISTING GOOGLE USER
        # ======================================

        user.name = name or user.name
        user.is_verified = True
        user.last_login_at = datetime.utcnow()

    db.session.commit()

    # ==========================================
    # FLASK SESSION
    # ==========================================

    session.clear()

    session["user_id"] = user.id
    session["name"] = user.name
    session["email"] = user.email
    session["role"] = user.role
    session["oauth_provider"] = user.oauth_provider

    # If already an approved field officer
    if user.role == "field_officer":
        return redirect(url_for("main.field_officer_dashboard"))

    # If already waiting for approval
    if user.role == "field_officer_pending":
        return redirect(url_for("main.field_officer_waiting"))

    # New/normal user
    return redirect(url_for("main.choose_role"))


@bp.route("/login")
def login():

    redirect_uri = url_for(
        "main.auth_callback",
        _external=True
    )

    return oauth.google.authorize_redirect(
        redirect_uri
    )

@bp.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(
            url_for("main.login")
        )

    return render_template(
        "dashboard.html"
    )

@bp.route("/choose-role")
def choose_role():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    return render_template("choose_role.html")

@bp.route("/select-role", methods=["POST"])
def select_role():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    selected_role = request.form.get("role")

    user = User.query.get(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("main.login"))

    # =========================
    # NORMAL USER
    # =========================

    if selected_role == "user":

        user.role = "user"

        db.session.commit()

        session["role"] = "user"

        return redirect(
            url_for("main.dashboard")
        )

    # =========================
    # FIELD OFFICER
    # =========================

    elif selected_role == "field_officer":

        user.role = "field_officer_pending"

        db.session.commit()

        session["role"] = "field_officer_pending"

        return redirect(
            url_for("main.field_officer_waiting")
        )

    return jsonify({
        "error": "Invalid role selected"
    }), 400

@bp.route("/field-officer/waiting")
def field_officer_waiting():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user = User.query.get(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("main.login"))

    if user.role == "field_officer":
        return redirect(
            url_for("main.field_officer_dashboard")
        )

    if user.role != "field_officer_pending":
        return redirect(
            url_for("main.dashboard")
        )

    return render_template(
        "field_officer_waiting.html"
    )

@bp.route("/field-officer/dashboard")
def field_officer_dashboard():

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    user = User.query.get(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("main.login"))

    if user.role != "field_officer":
        return redirect(
            url_for("main.field_officer_waiting")
        )

    return render_template(
        "field_officer_dashboard.html"
    )

# ============================================================
# ADMIN - FIELD OFFICER APPROVAL
# ============================================================

@bp.route("/admin/field-officers")
def admin_field_officers():

    # Must be logged in
    if "user_id" not in session:
        return redirect(url_for("main.login"))

    # Must be admin
    if session.get("role") != "admin":
        return jsonify({
            "error": "Admin access required"
        }), 403

    pending_officers = User.query.filter_by(
        role="field_officer_pending"
    ).all()

    return render_template(
        "admin_field_officers.html",
        pending_officers=pending_officers
    )


# ============================================================
# APPROVE FIELD OFFICER
# ============================================================

@bp.route(
    "/admin/field-officers/<int:user_id>/approve",
    methods=["POST"]
)
def approve_field_officer(user_id):

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if session.get("role") != "admin":
        return jsonify({
            "error": "Admin access required"
        }), 403

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    if user.role != "field_officer_pending":
        return jsonify({
            "error": "User is not a pending Field Officer"
        }), 400

    user.role = "field_officer"

    db.session.commit()

    return redirect(
        url_for("main.admin_field_officers")
    )


# ============================================================
# REJECT FIELD OFFICER
# ============================================================

@bp.route(
    "/admin/field-officers/<int:user_id>/reject",
    methods=["POST"]
)
def reject_field_officer(user_id):

    if "user_id" not in session:
        return redirect(url_for("main.login"))

    if session.get("role") != "admin":
        return jsonify({
            "error": "Admin access required"
        }), 403

    user = User.query.get(user_id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    if user.role != "field_officer_pending":
        return jsonify({
            "error": "User is not a pending Field Officer"
        }), 400

    # Revert to normal user
    user.role = "user"

    db.session.commit()

    return redirect(
        url_for("main.admin_field_officers")
    )