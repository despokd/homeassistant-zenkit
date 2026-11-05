"""Tests for the Zenkit account sensors."""

import datetime
from unittest.mock import MagicMock

import pytest

from custom_components.zenkit.sensor import SENSORS, ZenkitSensor

USER = {
    "id": 906842,
    "username": "user",
    "timezone": "Europe/Berlin",
    "settings": {"language": "de"},
    "isTwoFactorAuthenticationEnabled": True,
    "registered_at": "2022-12-19T15:25:21.967Z",
    "last_login": "2026-11-01T08:00:00.000Z",
    "displayname": "Kilian",
    "fullname": "Kilian D",
    "initials": "KD",
    "isSuperAdmin": False,
    "imageLink": "10959895",
    "isImagePreferred": True,
    "emails": [
        {"email": "old@example.com", "isPrimary": False, "isVerified": False},
        {"email": "user@example.com", "isPrimary": True, "isVerified": True},
    ],
    "appInstances": [
        {"appType": "todos", "created_at": "2022-12-19T15:25:21.967Z"},
        {"appType": "base", "created_at": "2023-08-11T16:26:13.719Z"},
    ],
}
USER["settings"].update(
    dateFormat="DD.MM.YYYY", timeFormat="HH:mm", startOfTheWeek="Mon"
)
ORGANIZATION = {
    "id": 560986,
    "name": "Org",
    "description": None,
    "planId": "free",
    "quotasExceeded": False,
}


def _sensor(
    key,
    user=USER,
    unread=3,
    lists=({"shortId": "a"}, {"shortId": "b"}),
    organization=ORGANIZATION,
    members=2,
):
    coordinator = MagicMock(
        user=user,
        organization=organization,
        organization_members=members,
        unread_notifications=unread,
        lists=list(lists),
        last_update_success=True,
    )
    description = next(d for d in SENSORS if d.key == key)
    return ZenkitSensor(coordinator, "entry", description)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("unread_notifications", 3),
        ("lists", 2),
        ("username", "user"),
        ("display_name", "Kilian"),
        ("full_name", "Kilian D"),
        ("initials", "KD"),
        ("email", "user@example.com"),
        ("apps", 2),
        ("super_admin", "no"),
        ("date_format", "DD.MM.YYYY"),
        ("time_format", "HH:mm"),
        ("start_of_week", "Mon"),
        ("organization", "Org"),
        ("organization_plan", "free"),
        ("organization_members", 2),
        ("organization_quotas_exceeded", "no"),
        ("timezone", "Europe/Berlin"),
        ("language", "de"),
        ("two_factor_authentication", "enabled"),
        (
            "registered",
            datetime.datetime(
                2022, 12, 19, 15, 25, 21, 967000, tzinfo=datetime.timezone.utc
            ),
        ),
        (
            "last_login",
            datetime.datetime(2026, 11, 1, 8, tzinfo=datetime.timezone.utc),
        ),
    ],
)
def test_values(key, value):
    sensor = _sensor(key)

    assert sensor.native_value == value
    assert sensor.available
    assert sensor.unique_id == f"entry_{key}"
    assert sensor.entity_id == f"sensor.zenkit_{key}"


def test_two_factor_disabled():
    user = {**USER, "isTwoFactorAuthenticationEnabled": False}

    assert _sensor("two_factor_authentication", user=user).native_value == "disabled"


@pytest.mark.parametrize("key", [d.key for d in SENSORS if d.key != "lists"])
def test_unavailable_without_value(key):
    sensor = _sensor(key, user=None, unread=None, organization=None, members=None)

    assert not sensor.available


def test_zero_is_available():
    sensor = _sensor("unread_notifications", unread=0)

    assert sensor.available
    assert sensor.native_value == 0


def test_email_attributes():
    assert _sensor("email").extra_state_attributes == {
        "emails": [
            {"email": "old@example.com", "primary": False, "verified": False},
            {"email": "user@example.com", "primary": True, "verified": True},
        ]
    }


def test_email_without_primary_uses_first():
    user = {**USER, "emails": [{"email": "a@example.com"}, {"email": "b@example.com"}]}

    assert _sensor("email", user=user).native_value == "a@example.com"


def test_apps_attributes():
    assert _sensor("apps").extra_state_attributes == {
        "apps": [
            {"app_type": "todos", "created_at": "2022-12-19T15:25:21.967Z"},
            {"app_type": "base", "created_at": "2023-08-11T16:26:13.719Z"},
        ]
    }


def test_organization_attributes():
    assert _sensor("organization").extra_state_attributes == {
        "id": 560986,
        "description": None,
    }


def test_display_name_has_profile_image():
    assert _sensor("display_name").entity_picture == (
        "https://zenkit.com/api/v1/files/10959895/convert?w=150&h=150"
    )
    assert _sensor("username").entity_picture is None


def test_no_profile_image_when_initials_are_preferred():
    user = {**USER, "isImagePreferred": False}

    assert _sensor("display_name", user=user).entity_picture is None


def test_super_admin_yes():
    user = {**USER, "isSuperAdmin": True}

    assert _sensor("super_admin", user=user).native_value == "yes"


ORGANIZATION_KEYS = {
    "organization",
    "organization_plan",
    "organization_members",
    "organization_quotas_exceeded",
}


@pytest.mark.parametrize("key", [d.key for d in SENSORS])
def test_device(key):
    sensor = _sensor(key)
    coordinator = sensor.coordinator

    if key in ORGANIZATION_KEYS:
        assert sensor.device_info is coordinator.organization_device_info
    else:
        assert sensor.device_info is coordinator.device_info


def test_organization_sensor_on_account_device_without_organization():
    coordinator = MagicMock(organization_device_info=None)
    description = next(d for d in SENSORS if d.key == "organization_plan")

    sensor = ZenkitSensor(coordinator, "entry", description)

    assert sensor.device_info is coordinator.device_info
