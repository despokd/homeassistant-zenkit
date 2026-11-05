"""Tests for the Assist shopping list sentences."""

import pytest
from hassil import Intents, recognize_all
from hassil.intents import WildcardSlotList

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.zenkit.assist import (
    ADD,
    COMPLETE,
    SENTENCES,
    async_setup_shopping_list,
)
from custom_components.zenkit.const import CONF_SHOPPING_LIST, DOMAIN

LIST_UUID = "list-uuid"


def _recognize(language: str, text: str) -> tuple[str, str] | None:
    """First match as the default agent takes it: action and item."""
    intents = Intents.from_dict(
        {
            "language": language,
            "intents": {
                action: {"data": [{"sentences": sentences}]}
                for action, sentences in SENTENCES[language].items()
            },
        }
    )
    intents.slot_lists["item"] = WildcardSlotList("item")
    for result in recognize_all(text, intents):
        return result.intent.name, str(result.entities["item"].value).strip()
    return None


@pytest.mark.parametrize(
    ("language", "text", "expected"),
    [
        ("en", "add milk to my shopping list", (ADD, "milk")),
        ("en", "add milk to the list", (ADD, "milk")),
        ("en", "put oat milk on my list", (ADD, "oat milk")),
        ("en", "check off milk from my shopping list", (COMPLETE, "milk")),
        ("en", "remove milk from the list", (COMPLETE, "milk")),
        ("de", "füge Milch zur Einkaufsliste hinzu", (ADD, "Milch")),
        ("de", "füge Milch zur Liste hinzu", (ADD, "Milch")),
        ("de", "füge Hafer Milch zu meiner Einkaufsliste hinzu", (ADD, "Hafer Milch")),
        ("de", "füge zur Einkaufsliste Milch hinzu", (ADD, "Milch")),
        ("de", "setze Milch auf die Einkaufsliste", (ADD, "Milch")),
        ("de", "Milch auf die Liste", (ADD, "Milch")),
        ("de", "Milch zum Einkauf hinzufügen", (ADD, "Milch")),
        ("de", "streiche Milch von meiner Einkaufsliste", (COMPLETE, "Milch")),
        ("de", "nimm Milch aus der Einkaufsliste raus", (COMPLETE, "Milch")),
        ("de", "hake Milch auf der Liste ab", (COMPLETE, "Milch")),
    ],
)
def test_shopping_list_sentences(language, text, expected):
    assert _recognize(language, text) == expected


@pytest.mark.parametrize(
    ("language", "text"),
    [
        # Sentences of HassListAddItem and co. with a list name stay with them
        ("en", "add apples to my trader joes list"),
        ("en", "add milk to my checklist"),
        ("en", "remove take out the trash from my chores list"),
        ("en", "check off take out the trash from my chores list"),
        ("de", "füge Putzen zur Haushaltsliste hinzu"),
        ("de", "füge Putzen zur Liste Haushalt hinzu"),
        ("de", "packe Putzen auf die Haushaltsliste"),
        ("de", "Putzen zur Haushaltsliste hinzufügen"),
        ("de", "streiche Putzen von meiner Haushaltsliste"),
        ("de", "hake Putzen von meiner Liste Haushalt ab"),
        ("de", "nimm Putzen aus meiner Haushaltsliste raus"),
        ("de", "Putzen aus der Haushaltsliste nehmen"),
        ("de", "füge Milch zum Wocheneinkauf hinzu"),
    ],
)
def test_sentences_with_list_name_do_not_match(language, text):
    assert _recognize(language, text) is None


@pytest.fixture
async def todo(hass: HomeAssistant):
    """A Zenkit todo entity in the registry, with recorded todo actions."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, options={CONF_SHOPPING_LIST: LIST_UUID}
    )
    entry.add_to_hass(hass)
    er.async_get(hass).async_get_or_create(
        "todo",
        DOMAIN,
        f"{entry.entry_id}_{LIST_UUID}",
        suggested_object_id="groceries",
        config_entry=entry,
    )
    items = [{"uid": "1", "summary": "Bread", "status": "needs_action"}]
    calls: list[ServiceCall] = []

    async def get_items(call: ServiceCall):
        calls.append(call)
        return {"todo.groceries": {"items": items}}

    async def record(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register(
        "todo", "get_items", get_items, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register("todo", "add_item", record)
    hass.services.async_register("todo", "update_item", record)
    async_setup_shopping_list(hass, entry)
    return calls


async def _say(hass: HomeAssistant, text: str) -> str:
    result = await conversation.async_converse(
        hass, text, None, Context(), language="en"
    )
    return result.response.speech["plain"]["speech"]


async def test_adds_item(hass, todo):
    assert await _say(hass, "add milk to my shopping list") == "Added milk"

    added = [call for call in todo if call.service == "add_item"]
    assert len(added) == 1
    assert added[0].data == {"item": "milk", "entity_id": "todo.groceries"}


async def test_open_item_is_not_added_twice(hass, todo):
    assert await _say(hass, "add bread to my shopping list") == "Added bread"

    assert not [call for call in todo if call.service == "add_item"]


async def test_completes_item(hass, todo):
    assert await _say(hass, "check off bread from my list") == "Checked off bread"

    (updated,) = [call for call in todo if call.service == "update_item"]
    assert updated.data["item"] == "1"
    assert updated.data["status"] == "completed"


async def test_complete_unknown_item(hass, todo):
    assert await _say(hass, "remove milk from my list") == "milk is not on the list"

    assert not [call for call in todo if call.service == "update_item"]


async def test_removed_entity_answers_with_error(hass, todo):
    registry = er.async_get(hass)
    registry.async_remove("todo.groceries")

    assert (
        await _say(hass, "add milk to my shopping list")
        == "Could not change the Zenkit list"
    )


async def test_no_sentences_without_option(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    entry = MockConfigEntry(domain=DOMAIN, version=2)
    entry.add_to_hass(hass)

    async_setup_shopping_list(hass, entry)

    manager = conversation.agent_manager.get_agent_manager(hass)
    assert manager.trigger_sentences == []


async def test_sentences_removed_on_unload(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, version=2, options={CONF_SHOPPING_LIST: LIST_UUID}
    )
    entry.add_to_hass(hass)
    async_setup_shopping_list(hass, entry)
    manager = conversation.agent_manager.get_agent_manager(hass)
    assert manager.trigger_sentences

    await entry._async_process_on_unload(hass)

    assert manager.trigger_sentences == []
