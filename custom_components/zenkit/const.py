"""Constants for the Zenkit integration."""

DOMAIN = "zenkit"
API_URL = "https://zenkit.com/api/v1"
UPDATE_INTERVAL = 60
ENTRIES_LIMIT = 100
# Seconds to wait before retrying a failed page of entries
RETRY_DELAYS = (1, 3)
DUE_DATE_FORMAT = "%Y-%m-%d"
# Due date with time, stored in UTC
DUE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000Z"
# Color of Zenkit's default "done" status, used when a list has no element roles
COMPLETED_COLOR = "#3ba744"
