"""A sensor platform for Zenkit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.todo import TodoItemStatus
from homeassistant.util import dt as dt_util, slugify

from .api import user_image_url
from .const import DOMAIN
from .coordinator import ZenkitConfigEntry, ZenkitDataUpdateCoordinator
from .elements import due_element
from .entity import async_add_list_entities
from .todo import _completion_status, _due_date

# Pixels of the profile image shown as entity picture
PICTURE_SIZE = 150


def _timestamp(value: str | None) -> datetime.datetime | None:
    """Parse a Zenkit timestamp, e.g. 2022-12-19T15:25:21.967Z."""
    return dt_util.parse_datetime(value) if value else None


@dataclass(frozen=True, kw_only=True)
class ZenkitSensorEntityDescription(SensorEntityDescription):
    """A Zenkit sensor, its value is read from the coordinator."""

    value_fn: Callable[
        [ZenkitDataUpdateCoordinator], str | int | datetime.datetime | None
    ]
    attributes_fn: Callable[[ZenkitDataUpdateCoordinator], dict[str, Any]] | None = None
    picture_fn: Callable[[ZenkitDataUpdateCoordinator], str | None] | None = None
    # The device, the account device if None
    device_fn: Callable[[ZenkitDataUpdateCoordinator], DeviceInfo | None] = (
        lambda coordinator: None
    )


def _user(coordinator: ZenkitDataUpdateCoordinator) -> dict:
    """The account data, empty before it is known."""
    return coordinator.user or {}


def _settings(coordinator: ZenkitDataUpdateCoordinator) -> dict:
    """The account settings, empty before they are known."""
    return _user(coordinator).get("settings") or {}


def _organization_device(coordinator: ZenkitDataUpdateCoordinator) -> DeviceInfo | None:
    """The organization device, None without organization."""
    return coordinator.organization_device_info


def _organization(coordinator: ZenkitDataUpdateCoordinator) -> dict:
    """The organization of the account, empty before it is known."""
    return coordinator.organization or {}


def _user_value(field: str) -> Callable[[ZenkitDataUpdateCoordinator], Any]:
    """Read a field of the account."""
    return lambda coordinator: _user(coordinator).get(field)


def _setting_value(field: str) -> Callable[[ZenkitDataUpdateCoordinator], Any]:
    """Read a setting of the account."""
    return lambda coordinator: _settings(coordinator).get(field)


def _flag(
    value_fn: Callable[[ZenkitDataUpdateCoordinator], bool | None],
    on: str = "yes",
    off: str = "no",
) -> Callable[[ZenkitDataUpdateCoordinator], str | None]:
    """Map a boolean field to enum states, None stays unknown."""

    def value(coordinator: ZenkitDataUpdateCoordinator) -> str | None:
        flag = value_fn(coordinator)
        if flag is None:
            return None
        return on if flag else off

    return value


def _primary_email(coordinator: ZenkitDataUpdateCoordinator) -> str | None:
    """The primary email address, else the first one."""
    emails = _user(coordinator).get("emails") or []
    email = next((email for email in emails if email.get("isPrimary")), None)
    if email is None and emails:
        email = emails[0]
    return email["email"] if email else None


def _emails(coordinator: ZenkitDataUpdateCoordinator) -> dict[str, Any]:
    """All email addresses of the account."""
    return {
        "emails": [
            {
                "email": email["email"],
                "primary": email.get("isPrimary", False),
                "verified": email.get("isVerified", False),
            }
            for email in _user(coordinator).get("emails") or []
        ]
    }


def _app_instances(coordinator: ZenkitDataUpdateCoordinator) -> int | None:
    """Number of Zenkit apps of the account, e.g. To Do and Base."""
    if "appInstances" not in _user(coordinator):
        return None
    return len(_user(coordinator)["appInstances"] or [])


def _app_types(coordinator: ZenkitDataUpdateCoordinator) -> dict[str, Any]:
    """The Zenkit apps of the account."""
    return {
        "apps": [
            {"app_type": app["appType"], "created_at": app.get("created_at")}
            for app in _user(coordinator).get("appInstances") or []
        ]
    }


def _organization_attributes(coordinator: ZenkitDataUpdateCoordinator) -> dict:
    """Id and description of the organization."""
    organization = _organization(coordinator)
    return {
        "id": organization.get("id"),
        "description": organization.get("description"),
    }


def _picture(coordinator: ZenkitDataUpdateCoordinator) -> str | None:
    """The profile image of the account."""
    return user_image_url(_user(coordinator), PICTURE_SIZE)


SENSORS: tuple[ZenkitSensorEntityDescription, ...] = (
    ZenkitSensorEntityDescription(
        key="unread_notifications",
        translation_key="unread_notifications",
        icon="mdi:bell",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.unread_notifications,
    ),
    ZenkitSensorEntityDescription(
        key="lists",
        translation_key="lists",
        icon="mdi:format-list-checks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: len(coordinator.lists),
    ),
    ZenkitSensorEntityDescription(
        key="username",
        translation_key="username",
        icon="mdi:account",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_user_value("username"),
    ),
    ZenkitSensorEntityDescription(
        key="display_name",
        translation_key="display_name",
        icon="mdi:account-circle",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_user_value("displayname"),
        picture_fn=_picture,
    ),
    ZenkitSensorEntityDescription(
        key="full_name",
        translation_key="full_name",
        icon="mdi:card-account-details",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_user_value("fullname"),
    ),
    ZenkitSensorEntityDescription(
        key="initials",
        translation_key="initials",
        icon="mdi:alphabetical-variant",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_user_value("initials"),
    ),
    ZenkitSensorEntityDescription(
        key="email",
        translation_key="email",
        icon="mdi:email",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_primary_email,
        attributes_fn=_emails,
    ),
    ZenkitSensorEntityDescription(
        key="apps",
        translation_key="apps",
        icon="mdi:apps",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_app_instances,
        attributes_fn=_app_types,
    ),
    ZenkitSensorEntityDescription(
        key="super_admin",
        translation_key="super_admin",
        icon="mdi:shield-crown",
        device_class=SensorDeviceClass.ENUM,
        options=["yes", "no"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag(_user_value("isSuperAdmin")),
    ),
    ZenkitSensorEntityDescription(
        key="two_factor_authentication",
        translation_key="two_factor_authentication",
        icon="mdi:two-factor-authentication",
        device_class=SensorDeviceClass.ENUM,
        options=["enabled", "disabled"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag(
            _user_value("isTwoFactorAuthenticationEnabled"), "enabled", "disabled"
        ),
    ),
    ZenkitSensorEntityDescription(
        key="timezone",
        translation_key="timezone",
        icon="mdi:map-clock",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_user_value("timezone"),
    ),
    ZenkitSensorEntityDescription(
        key="language",
        translation_key="language",
        icon="mdi:translate",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_setting_value("language"),
    ),
    ZenkitSensorEntityDescription(
        key="date_format",
        translation_key="date_format",
        icon="mdi:calendar",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_setting_value("dateFormat"),
    ),
    ZenkitSensorEntityDescription(
        key="time_format",
        translation_key="time_format",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_setting_value("timeFormat"),
    ),
    ZenkitSensorEntityDescription(
        key="start_of_week",
        translation_key="start_of_week",
        icon="mdi:calendar-week-begin",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_setting_value("startOfTheWeek"),
    ),
    ZenkitSensorEntityDescription(
        key="registered",
        translation_key="registered",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _timestamp(
            _user(coordinator).get("registered_at")
        ),
    ),
    ZenkitSensorEntityDescription(
        key="last_login",
        translation_key="last_login",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _timestamp(_user(coordinator).get("last_login")),
    ),
    ZenkitSensorEntityDescription(
        key="organization",
        translation_key="organization",
        device_fn=_organization_device,
        icon="mdi:domain",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _organization(coordinator).get("name"),
        attributes_fn=_organization_attributes,
    ),
    ZenkitSensorEntityDescription(
        key="organization_plan",
        translation_key="organization_plan",
        device_fn=_organization_device,
        icon="mdi:card-account-details-star",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _organization(coordinator).get("planId"),
    ),
    ZenkitSensorEntityDescription(
        key="organization_members",
        translation_key="organization_members",
        device_fn=_organization_device,
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.organization_members,
    ),
    ZenkitSensorEntityDescription(
        key="organization_quotas_exceeded",
        translation_key="organization_quotas_exceeded",
        device_fn=_organization_device,
        icon="mdi:gauge-full",
        device_class=SensorDeviceClass.ENUM,
        options=["yes", "no"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag(
            lambda coordinator: _organization(coordinator).get("quotasExceeded")
        ),
    ),
)


@dataclass(frozen=True)
class _Counts:
    """Open entries of a list by due date."""

    open: int = 0
    overdue: int = 0
    due_today: int = 0


def _count(entries: list[dict], elements: list[dict] | None) -> _Counts:
    """Count the open entries, with the status and due date as the todo entity."""
    now = dt_util.now()
    today = now.date()
    open = overdue = due_today = 0
    for entry in entries:
        if _completion_status(entry, elements) == TodoItemStatus.COMPLETED:
            continue
        open += 1
        due = _due_date(entry, elements)
        if isinstance(due, datetime.datetime):
            overdue += due < now
            due_today += due.date() == today
        elif isinstance(due, datetime.date):
            # A date without time is overdue once its day is over
            overdue += due < today
            due_today += due == today
    return _Counts(open, overdue, due_today)


def _has_due(coordinator: ZenkitDataUpdateCoordinator, list_short_id: str) -> bool:
    """Whether a list has a due date field, assumed until its fields are fetched."""
    elements = coordinator.zk.elements.get(list_short_id)
    return elements is None or due_element(elements) is not None


@dataclass(frozen=True, kw_only=True)
class ZenkitListSensorEntityDescription(SensorEntityDescription):
    """A count of the entries of a Zenkit list."""

    value_fn: Callable[[_Counts], int]
    # Only for lists with a due date field
    needs_due: bool = False


LIST_SENSORS: tuple[ZenkitListSensorEntityDescription, ...] = (
    ZenkitListSensorEntityDescription(
        key="open_entries",
        translation_key="open_entries",
        icon="mdi:checkbox-blank-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda counts: counts.open,
    ),
    ZenkitListSensorEntityDescription(
        key="overdue_entries",
        translation_key="overdue_entries",
        icon="mdi:calendar-alert",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda counts: counts.overdue,
        needs_due=True,
    ),
    ZenkitListSensorEntityDescription(
        key="entries_due_today",
        translation_key="entries_due_today",
        icon="mdi:calendar-today",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda counts: counts.due_today,
        needs_due=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZenkitConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zenkit sensor platform config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        ZenkitSensor(coordinator, entry.entry_id, description)
        for description in SENSORS
    )
    async_add_list_entities(
        coordinator,
        entry,
        async_add_entities,
        lambda list: (
            ZenkitListSensor(coordinator, list, description)
            for description in LIST_SENSORS
            if not description.needs_due or _has_due(coordinator, list["shortId"])
        ),
    )


class ZenkitSensor(CoordinatorEntity[ZenkitDataUpdateCoordinator], SensorEntity):
    """A sensor of the Zenkit account."""

    _attr_has_entity_name = True
    entity_description: ZenkitSensorEntityDescription

    def __init__(
        self,
        coordinator: ZenkitDataUpdateCoordinator,
        entry_id: str,
        description: ZenkitSensorEntityDescription,
    ) -> None:
        """Initialize ZenkitSensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = (
            description.device_fn(coordinator) or coordinator.device_info
        )
        # Suggested id, else it is derived from the name in the HA language
        self.entity_id = f"sensor.{DOMAIN}_{description.key}"

    @property
    def available(self) -> bool:
        """Unavailable while the value is unknown, e.g. a failed fetch."""
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> str | int | datetime.datetime | None:
        """Return the value from the coordinator."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return details of the value, e.g. all email addresses."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator)

    @property
    def entity_picture(self) -> str | None:
        """Return the profile image for the display name."""
        if self.entity_description.picture_fn is None:
            return None
        return self.entity_description.picture_fn(self.coordinator)


class ZenkitListSensor(CoordinatorEntity[ZenkitDataUpdateCoordinator], SensorEntity):
    """A count of the entries of a Zenkit list, see docs/user/configuration.md."""

    _attr_has_entity_name = True
    entity_description: ZenkitListSensorEntityDescription

    def __init__(
        self,
        coordinator: ZenkitDataUpdateCoordinator,
        list: dict[str, Any],
        description: ZenkitListSensorEntityDescription,
    ) -> None:
        """Initialize ZenkitListSensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self.list_short_id = list["shortId"]
        self._attr_unique_id = (
            f"{coordinator.entry_id}_{list['uuid']}_{description.key}"
        )
        self._attr_device_info = coordinator.list_device_info(list)
        # Suggested id, else it is derived from the name in the HA language
        self.entity_id = f"sensor.{DOMAIN}_{slugify(list['name'])}_{description.key}"

    @property
    def available(self) -> bool:
        """Unavailable while only this list fails to load, as its todo entity."""
        return (
            super().available
            and self.list_short_id not in self.coordinator.failed_lists
            and self.list_short_id in (self.coordinator.data or {})
        )

    @property
    def native_value(self) -> int | None:
        """Return the count from the entries of the coordinator."""
        entries = (self.coordinator.data or {}).get(self.list_short_id)
        if entries is None:
            return None
        elements = self.coordinator.zk.elements.get(self.list_short_id)
        return self.entity_description.value_fn(_count(entries, elements))
