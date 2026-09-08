from flask import Flask
from extension import db
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from oauth_config import init_oauth
from earthquake_service import scheduled_earthquake_update
from weather_service import scheduled_weather_update
from river_service import scheduled_river_update
from flood_service import scheduled_flood_update






# ============================================================
# DATABASE
# ============================================================

import os
from dotenv import load_dotenv
from sqlalchemy import URL
load_dotenv()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = URL.create(
    drivername="postgresql+psycopg2",
    username="postgres",
    password=os.getenv("POSTGRES_PASSWORD"),
    host="localhost",
    port=5432,
    database="disaster_db"
)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
google = init_oauth(app)
app.app_context().push()


# ============================================================
# CREATE TABLES
# ============================================================

with app.app_context():

    try:

        db.engine.connect()

        print("DATABASE CONNECTED!")

        print(
            "Registered tables:",
            db.metadata.tables.keys()
        )

        db.create_all()

        print("TABLES CREATED!")

    except Exception as e:

        print("DATABASE ERROR!")

        print(e)


# ============================================================
# BLUEPRINT
# ============================================================

from controllers import bp

app.register_blueprint(bp)


# ============================================================
# SCHEDULER
# ============================================================

def scheduled_flood_update_with_context(app):

    with app.app_context():

        scheduled_flood_update()


if __name__ == "__main__":

    scheduler = BackgroundScheduler()


    # ========================================================
    # EARTHQUAKE
    # Every 5 minutes
    # ========================================================

    scheduler.add_job(
        scheduled_earthquake_update,
        trigger="interval",
        minutes=5,
        id="usgs_earthquake_update",
        replace_existing=True,
        # next_run_time=datetime.now()
    )


    # ========================================================
    # WEATHER
    # Every 24 hours FOR NOW
    #
    # Deployment ke time interval change kar sakte hain.
    # ========================================================

    scheduler.add_job(
        lambda: scheduled_weather_update(app),
        trigger="interval",
        hours=24,
        id="nwdp_weather_update",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
        # next_run_time=datetime.now()
    )


    # ========================================================
    # RIVER
    # Every 5 minutes
    # ========================================================

    scheduler.add_job(
        lambda: scheduled_river_update(app),
        trigger="interval",
        minutes=5,
        id="cwc_river_update",
        replace_existing=True,
        # next_run_time=datetime.now()
    )


    # ========================================================
    # FLOOD
    # Every 30 minutes
    # ========================================================

    scheduler.add_job(
        lambda: scheduled_flood_update_with_context(app),
        trigger="interval",
        minutes=30,
        id="flood_update",
        replace_existing=True,
        # next_run_time=datetime.now()
    )


    # ========================================================
    # START SCHEDULER
    # ========================================================

    scheduler.start()


    print("\n==========================================")
    print("NERVE02 SCHEDULER STARTED")
    print("==========================================")
    print("Earthquake : Every 5 minutes")
    print("Weather    : Every 24 hours")
    print("River      : Every 5 minutes")
    print("Flood      : Every 30 minutes")
    print("==========================================\n")


    try:

        app.run(
            debug=True,
            use_reloader=False
        )

    finally:

        scheduler.shutdown()