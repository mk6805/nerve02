import requests

def reverse_geocode(latitude, longitude):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1}
    headers = {
    "User-Agent": f"NERVE02/1.0 ({os.getenv('NOMINATIM_EMAIL')})"}

    response = requests.get(url, params=params, headers=headers, timeout=10)
    response.raise_for_status()

    address = response.json().get("address", {})

    return {
        "place_name": address.get("neighbourhood") or address.get("suburb") or address.get("quarter") or address.get("city_district"),
        "city": address.get("city") or address.get("town") or address.get("municipality") or address.get("village"),
        "district": address.get("state_district") or address.get("district"),
        "state": address.get("state"),
        "country": address.get("country"),
        "postal_code": address.get("postcode")
    }