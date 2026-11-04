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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import user_image_url
from .const import DOMAIN
from .coordinator import ZenkitDataUpdateCoordinator

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


def _user(coordinator: ZenkitDataUpdateCoordinator) -> dict:
    """The account data, empty before it is known."""
    return coordinator.user or {}


def _settings(coordinator: ZenkitDataUpdateCoordinator) -> dict:
    """The account settings, empty before they are known."""
    return _user(coordinator).get("settings") or {}


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
        icon="mdi:domain",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _organization(coordinator).get("name"),
        attributes_fn=_organization_attributes,
    ),
    ZenkitSensorEntityDescription(
        key="organization_plan",
        translation_key="organization_plan",
        icon="mdi:card-account-details-star",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _organization(coordinator).get("planId"),
    ),
    ZenkitSensorEntityDescription(
        key="organization_members",
        translation_key="organization_members",
        icon="mdi:account-group",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.organization_members,
    ),
    ZenkitSensorEntityDescription(
        key="organization_quotas_exceeded",
        translation_key="organization_quotas_exceeded",
        icon="mdi:gauge-full",
        device_class=SensorDeviceClass.ENUM,
        options=["yes", "no"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_flag(
            lambda coordinator: _organization(coordinator).get("quotasExceeded")
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Zenkit sensor platform config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        ZenkitSensor(coordinator, entry.entry_id, description)
        for description in SENSORS
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
        self._attr_device_info = coordinator.device_info
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
