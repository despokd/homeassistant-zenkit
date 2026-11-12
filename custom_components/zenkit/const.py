"""Constants for the Zenkit integration."""

DOMAIN = "zenkit"
ZENKIT_URL = "https://zenkit.com"
API_URL = f"{ZENKIT_URL}/api/v1"
UPDATE_INTERVAL = 60
# Seconds between fetches of the account data, it rarely changes
USER_UPDATE_INTERVAL = 3600
ENTRIES_LIMIT = 100
# Seconds to wait before retrying a failed page of entries
RETRY_DELAYS = (1, 3)
# Seconds a request may take in total, so a stalled server fails it
REQUEST_TIMEOUT = 30
DUE_DATE_FORMAT = "%Y-%m-%d"
# Due date with time, stored in UTC
DUE_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.000Z"
# Color of Zenkit's default "done" status, used when a list has no element roles
COMPLETED_COLOR = "#3ba744"
# Option: uuid of the list that gets Assist's shopping list sentences
CONF_SHOPPING_LIST = "shopping_list"
# Option: list types (resourceType) synced besides to-do lists, all if unset
CONF_LIST_TYPES = "list_types"
OPTIONAL_LIST_TYPES = ["project", "database"]
