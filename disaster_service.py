from earthquake_service import get_nearby_earthquakes
from flood_service import get_nearby_floods
from models import UserLocation


def get_nearby_disasters(
    #general purpose function
    #"Given latitude, longitude, radius, and optionally a disaster type, find what disasters are nearby."
    latitude,
    longitude,
    radius_km,
    disaster_type=None
):

    disasters = []

    if (
        disaster_type is None
        or disaster_type == "earthquake"
    ):

        earthquakes = get_nearby_earthquakes(
            latitude,
            longitude,
            radius_km
        )

        disasters.extend(earthquakes)
    if (
        disaster_type is None
        or disaster_type == "flood"
    ):

        floods = get_nearby_floods(
            latitude,
            longitude,
            radius_km
        )

        disasters.extend(floods)
    return disasters

def check_nearby_risk(
    radius_km
):

    user_location = (
        UserLocation.query
        .order_by(UserLocation.id.desc())
        .first()
    )

    if not user_location:

        return None

    disasters = get_nearby_disasters(

        user_location.latitude,

        user_location.longitude,

        radius_km
    )

    return {
        "user_location": {

            "latitude":
                user_location.latitude,

            "longitude":
                user_location.longitude,

            "place_name":
                user_location.place_name,

            "city":
                user_location.city,

            "district":
                user_location.district,

            "state":
                user_location.state,

            "country":
                user_location.country
        },

        "radius_km": radius_km,

        "count": len(disasters),

        "disasters": disasters
    }