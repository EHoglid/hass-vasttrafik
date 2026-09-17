"""Constants for the Västtrafik Timetable integration."""

from datetime import timedelta

DOMAIN = "vasttrafik_timetable"
PLATFORMS = ["sensor"]

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_STOP_GID = "stop_gid"
CONF_STOP_NAME = "stop_name"
CONF_START_DATE_TIME = "start_date_time"
CONF_PLATFORMS = "platforms"
CONF_TIME_SPAN = "time_span_in_minutes"
CONF_MAX_DEPARTURES_PER_LINE = "max_departures_per_line_and_direction"
CONF_API_LIMIT = "api_limit"
CONF_INCLUDE_OCCUPANCY = "include_occupancy"
CONF_DIRECTION_GID = "direction_gid"

DEFAULT_TIME_SPAN = 60
DEFAULT_MAX_DEPARTURES_PER_LINE = 2
DEFAULT_API_LIMIT = 10

UPDATE_INTERVAL = timedelta(minutes=1)
