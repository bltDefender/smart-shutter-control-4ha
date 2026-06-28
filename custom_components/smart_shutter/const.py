"""Constants for Smart Shutter Control."""

DOMAIN = "smart_shutter"

# ── Config keys – global ──────────────────────────────────────────────────
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_TEMP_SENSORS = "temperature_sensors"
CONF_TEMP_THRESHOLD = "temperature_threshold"
CONF_SUNSET_TYPE = "sunset_type"

# ── Config keys – per window ──────────────────────────────────────────────
CONF_WINDOWS = "windows"
CONF_WINDOW_ID = "id"
CONF_WINDOW_NAME = "name"
CONF_WINDOW_ORIENTATION = "orientation"
CONF_COVER_ENTITY = "cover_entity"
CONF_POSITION_OPEN = "position_open"
CONF_POSITION_HALF = "position_half"
CONF_POSITION_CLOSED = "position_closed"
CONF_ANGLE_FULLY_CLOSED = "angle_fully_closed"
CONF_ANGLE_HALF_CLOSED = "angle_half_closed"

# ── Sunset types ──────────────────────────────────────────────────────────
SUNSET_CIVIL = "civil"
SUNSET_NAUTICAL = "nautical"
SUNSET_ASTRONOMICAL = "astronomical"

SUNSET_OPTIONS = [SUNSET_CIVIL, SUNSET_NAUTICAL, SUNSET_ASTRONOMICAL]

# Sun elevation threshold for each sunset type (degrees below horizon)
SUNSET_ELEVATION: dict[str, float] = {
    SUNSET_CIVIL: -6.0,
    SUNSET_NAUTICAL: -12.0,
    SUNSET_ASTRONOMICAL: -18.0,
}

# ── Shutter states ────────────────────────────────────────────────────────
SHUTTER_OPEN = "open"
SHUTTER_HALF = "half_closed"
SHUTTER_CLOSED = "closed"

# ── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_TEMP_THRESHOLD = 30.0
DEFAULT_ANGLE_FULLY_CLOSED = 30.0
DEFAULT_ANGLE_HALF_CLOSED = 60.0
DEFAULT_POSITION_OPEN = 100
DEFAULT_POSITION_HALF = 50
DEFAULT_POSITION_CLOSED = 0
DEFAULT_SUNSET_TYPE = SUNSET_CIVIL

# ── Update interval ───────────────────────────────────────────────────────
UPDATE_INTERVAL_MINUTES = 5

# ── Platforms ─────────────────────────────────────────────────────────────
PLATFORMS = ["sensor"]
