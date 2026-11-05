"""Every entity attribute needs a translated name in each language."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from custom_components.zenkit.api import _folder
from custom_components.zenkit.coordinator import LIST_MODELS
from custom_components.zenkit.sensor import SENSORS
from custom_components.zenkit.todo import ITEM_DETAILS, _list_attributes

COMPONENT = Path(__file__).parent.parent / "custom_components" / "zenkit"
FILES = ["strings.json", "translations/en.json", "translations/de.json"]


def _attribute_keys() -> dict[tuple[str, str], set[str]]:
    """Attribute names by (platform, translation key)."""
    workspace = {"id": 1, "name": "Home", "parentWorkspaceId": None}
    keys = {
        ("todo", "list"): set(_folder(workspace, [workspace]))
        | set(_list_attributes({}))
        | {ITEM_DETAILS}
    }
    coordinator = MagicMock(user={}, organization={})
    for description in SENSORS:
        if description.attributes_fn is not None:
            keys[("sensor", description.translation_key)] = set(
                description.attributes_fn(coordinator)
            )
    return keys


@pytest.mark.parametrize("file", FILES)
def test_attributes_have_translations(file):
    entity = json.loads((COMPONENT / file).read_text())["entity"]
    for (platform, key), attributes in _attribute_keys().items():
        translated = entity[platform][key].get("state_attributes", {})
        missing = attributes - {k for k, v in translated.items() if v.get("name")}
        assert not missing, f"{file}: {platform}.{key} lacks {sorted(missing)}"


@pytest.mark.parametrize("file", FILES)
def test_device_models_have_translations(file):
    device = json.loads((COMPONENT / file).read_text())["device"]
    keys = {"account", "organization", "list", *LIST_MODELS.values()}
    missing = {key for key in keys if not device.get(key, {}).get("name")}
    assert not missing, f"{file}: device lacks {sorted(missing)}"


@pytest.mark.parametrize("file", FILES)
def test_services_have_translations(file):
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text())
    translated = json.loads((COMPONENT / file).read_text()).get("services", {})
    for service, definition in services.items():
        assert translated.get(service, {}).get("name"), f"{file}: {service}"
        fields = translated[service].get("fields", {})
        for field in definition.get("fields", {}):
            assert fields.get(field, {}).get("name"), f"{file}: {service}.{field}"
