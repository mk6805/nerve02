from extension import db
from geoalchemy2 import Geography
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import UniqueConstraint, CheckConstraint


# ============================================================
# USER
# ============================================================

class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    # Basic Information
    name = db.Column(db.String(150))
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20))

    # Authentication
    password_hash = db.Column(db.String(255))
    oauth_provider = db.Column(db.String(50))
    oauth_provider_id = db.Column(db.String(255))

    # Role
    role = db.Column(db.String(30), nullable=False, default="user")

    # Possible roles:
    # user
    # field_officer
    # admin

    # Account Status
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)

    # Emergency Contact
    emergency_name = db.Column(db.String(150))
    emergency_number = db.Column(db.String(20))
    emergency_email = db.Column(db.String(255))

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = db.Column(db.DateTime)

    # Constraints
    __table_args__ = (
        UniqueConstraint("oauth_provider", "oauth_provider_id", name="uq_user_oauth"),
    )

    # Relationships
    location = db.relationship("UserLocation", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sos_requests = db.relationship("SOSRequest", back_populates="user", cascade="all, delete-orphan")

    # Password Methods
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


# ============================================================
# USER LOCATION
# ============================================================

class UserLocation(db.Model):
    __tablename__ = "user_location"

    id = db.Column(db.Integer, primary_key=True)

    # User
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)

    # GPS Coordinates
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location = db.Column(Geography("POINT", srid=4326), nullable=False)

    # GPS Accuracy
    accuracy_m = db.Column(db.Float)
    altitude_m = db.Column(db.Float)

    # Reverse Geocoded Location
    place_name = db.Column(db.String(255))
    city = db.Column(db.String(150))
    district = db.Column(db.String(150))
    state = db.Column(db.String(150))
    country = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))

    # Timestamp
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_user_location_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_user_location_longitude"),
    )

    # Relationship
    user = db.relationship("User", back_populates="location")


# ============================================================
# COMMON DISASTER
# ============================================================

class Disaster(db.Model):
    __tablename__ = "disaster"

    id = db.Column(db.Integer, primary_key=True)

    # Basic Event Information
    disaster_type = db.Column(db.String(50), nullable=False)
    event_name = db.Column(db.String(255))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # Spatial Information
    location = db.Column(Geography("POINT", srid=4326))
    affected_area = db.Column(Geography("MULTIPOLYGON", srid=4326))

    # Event Information
    severity = db.Column(db.String(50))
    source = db.Column(db.String(100))
    source_event_id = db.Column(db.String(255))
    description = db.Column(db.Text)

    # Administrative Location
    state = db.Column(db.String(150))
    district = db.Column(db.String(150))
    country = db.Column(db.String(100))
    place_name = db.Column(db.String(255))
    city = db.Column(db.String(150))
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint("source", "source_event_id", name="uq_disaster_source_event"),
    )

    # Disaster-Specific Relationships
    earthquake = db.relationship("Earthquake", back_populates="disaster", uselist=False, cascade="all, delete-orphan")
    flood = db.relationship("Flood", back_populates="disaster", uselist=False, cascade="all, delete-orphan")
    landslide = db.relationship("Landslide", back_populates="disaster", uselist=False, cascade="all, delete-orphan")
    cyclone = db.relationship("Cyclone", back_populates="disaster", uselist=False, cascade="all, delete-orphan")
    observations = db.relationship("DisasterObservation", back_populates="disaster", cascade="all, delete-orphan")


# ============================================================
# EARTHQUAKE
# ============================================================

class Earthquake(db.Model):
    __tablename__ = "earthquake"

    id = db.Column(db.Integer, primary_key=True)
    disaster_id = db.Column(db.Integer, db.ForeignKey("disaster.id"), nullable=False, unique=True)
    magnitude = db.Column(db.Float)
    magnitude_type = db.Column(db.String(20))
    depth_km = db.Column(db.Float)

    disaster = db.relationship("Disaster", back_populates="earthquake")


# ============================================================
# FLOOD
# ============================================================

class Flood(db.Model):
    __tablename__ = "flood"

    id = db.Column(db.Integer, primary_key=True)
    disaster_id = db.Column(db.Integer, db.ForeignKey("disaster.id"), nullable=False, unique=True)

    # Historical Flood Inventory Fields
    uei = db.Column(db.String(100))
    main_cause = db.Column(db.String(255))
    location_description = db.Column(db.Text)
    area_affected_value = db.Column(db.Float)
    area_affected_unit = db.Column(db.String(30))

    # Human / Animal Impact
    human_fatality = db.Column(db.Integer)
    human_injured = db.Column(db.Integer)
    human_displaced = db.Column(db.Integer)
    animal_fatality = db.Column(db.Integer)
    casualty_description = db.Column(db.Text)

    # Damage
    extent_of_damage = db.Column(db.Text)

    # Administrative Source Codes
    district_lgd_codes = db.Column(db.Text)
    state_code = db.Column(db.String(50))

    disaster = db.relationship("Disaster", back_populates="flood")


# ============================================================
# LANDSLIDE
# ============================================================

class Landslide(db.Model):
    __tablename__ = "landslide"

    id = db.Column(db.Integer, primary_key=True)
    disaster_id = db.Column(db.Integer, db.ForeignKey("disaster.id"), nullable=False, unique=True)

    # GSI Landslide Inventory Fields
    slide_no = db.Column(db.String(100))
    slide_name = db.Column(db.String(255))
    nh_sh_location = db.Column(db.Text)
    material_involved = db.Column(db.String(100))
    movement_type = db.Column(db.String(100))
    history = db.Column(db.String(255))

    disaster = db.relationship("Disaster", back_populates="landslide")


# ============================================================
# CYCLONE
# ============================================================

class Cyclone(db.Model):
    __tablename__ = "cyclone"

    id = db.Column(db.Integer, primary_key=True)
    disaster_id = db.Column(db.Integer, db.ForeignKey("disaster.id"), nullable=False, unique=True)
    intensity_stage = db.Column(db.String(100))

    disaster = db.relationship("Disaster", back_populates="cyclone")

    track_points = db.relationship("CycloneTrackPoint", back_populates="cyclone", cascade="all, delete-orphan")


# ============================================================
# CYCLONE TRACK POINT
# ============================================================

class CycloneTrackPoint(db.Model):
    __tablename__ = "cyclone_track_point"

    id = db.Column(db.Integer, primary_key=True)
    cyclone_id = db.Column(db.Integer, db.ForeignKey("cyclone.id"), nullable=False)
    observed_at = db.Column(db.DateTime, nullable=False)
    location = db.Column(Geography("POINT", srid=4326), nullable=False)

    # Cyclone Measurements
    intensity_stage = db.Column(db.String(100))
    t_ci_number = db.Column(db.Float)
    central_pressure_mb = db.Column(db.Float)
    pressure_drop_mb = db.Column(db.Float)
    max_sustained_wind_kmh = db.Column(db.Float)

    cyclone = db.relationship("Cyclone", back_populates="track_points")

    __table_args__ = (
        UniqueConstraint("cyclone_id", "observed_at", name="uq_cyclone_track_time"),
    )


# ============================================================
# DISASTER OBSERVATION
# ============================================================

class DisasterObservation(db.Model):
    __tablename__ = "disaster_observation"

    id = db.Column(db.Integer, primary_key=True)
    disaster_id = db.Column(db.Integer, db.ForeignKey("disaster.id"), nullable=False)
    observed_at = db.Column(db.DateTime)
    observation_type = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Float)
    unit = db.Column(db.String(50))
    observation_metadata = db.Column("metadata", db.Text)

    
    disaster = db.relationship("Disaster", back_populates="observations")


# ============================================================
# MONITORING STATION
# ============================================================

class MonitoringStation(db.Model):
    __tablename__ = "monitoring_station"

    id = db.Column(db.Integer, primary_key=True)

    # Station Information
    station_name = db.Column(db.String(255), nullable=False)
    agency = db.Column(db.String(150))
    station_type = db.Column(db.String(50))

    # Spatial Information
    location = db.Column(Geography("POINT", srid=4326), nullable=False)

    # Administrative Information
    state = db.Column(db.String(150))
    district = db.Column(db.String(150))

    # River Information
    river = db.Column(db.String(255))
    basin = db.Column(db.String(255))
    tributary = db.Column(db.String(255))
    subtributary = db.Column(db.String(255))
    local_river = db.Column(db.String(255))

    # Relationships
    weather_observations = db.relationship("WeatherObservation", back_populates="station", cascade="all, delete-orphan")
    hydrological_observations = db.relationship("HydrologicalObservation", back_populates="station", cascade="all, delete-orphan")


# ============================================================
# WEATHER OBSERVATION
# ============================================================

class WeatherObservation(db.Model):
    __tablename__ = "weather_observation"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey("monitoring_station.id"), nullable=False)
    observed_at = db.Column(db.DateTime, nullable=False)

    # Weather Measurements
    temperature_c = db.Column(db.Float)
    humidity_percent = db.Column(db.Float)
    rainfall_mm = db.Column(db.Float)
    wind_speed_kmh = db.Column(db.Float)
    wind_direction_deg = db.Column(db.Float)
    pressure_mb = db.Column(db.Float)
    solar_radiation_wm2 = db.Column(db.Float)

    # Source
    source = db.Column(db.String(100))

    station = db.relationship("MonitoringStation", back_populates="weather_observations")

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_weather_station_time"),
    )


# ============================================================
# HYDROLOGICAL OBSERVATION
# ============================================================

class HydrologicalObservation(db.Model):
    __tablename__ = "hydrological_observation"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey("monitoring_station.id"), nullable=False)
    observed_at = db.Column(db.DateTime, nullable=False)

    # Hydrological Measurements
    water_level_m = db.Column(db.Float)
    discharge_m3s = db.Column(db.Float)
    river_velocity_ms = db.Column(db.Float)

    # Source
    source = db.Column(db.String(100))

    station = db.relationship("MonitoringStation", back_populates="hydrological_observations")

    __table_args__ = (
        UniqueConstraint("station_id", "observed_at", name="uq_hydro_station_time"),
    )


# ============================================================
# SOS REQUEST
# ============================================================

class SOSRequest(db.Model):
    __tablename__ = "sos_request"

    id = db.Column(db.Integer, primary_key=True)

    # User
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # SOS Location Snapshot
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    location = db.Column(Geography("POINT", srid=4326), nullable=False)

    # SOS Information
    triggered_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(30), nullable=False, default="active")
    message = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)

    # Relationship
    user = db.relationship("User", back_populates="sos_requests")

    # GPS Constraints
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_sos_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_sos_longitude"),
    )