from flask import Flask,request,jsonify,Blueprint,render_template

bp=Blueprint("main",__name__)

@bp.route("/")
def home():
    return render_template("index.html")


@bp.route("/api/location", methods=["POST"])
def location():
    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    print("Latitude:", latitude)
    print("Longitude:", longitude)

    return jsonify({
        "message": "Location received",
        "latitude": latitude,
        "longitude": longitude
    })