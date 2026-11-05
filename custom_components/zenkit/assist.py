"""Assist shopping list sentences for a Zenkit list (#16).

Home Assistant's built-in sentences for "add milk to my shopping list" belong to
the Shopping List integration and need no list name, so they win over the todo
sentences of a Zenkit list, even when Shopping List is not set up. Sentence
triggers are matched before any intent, so the list chosen in the options gets
these sentences. See docs/technical/assist.md.
"""

from __future__ import annotations

import logging
from typing import Any

from hassil.recognize import RecognizeResult

from homeassistant.components.conversation import ConversationInput
from homeassistant.components.conversation.agent_manager import get_agent_manager
from homeassistant.components.todo import DOMAIN as TODO_DOMAIN, TodoItemStatus
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .const import CONF_SHOPPING_LIST, DOMAIN
from .coordinator import ZenkitConfigEntry

_LOGGER = logging.getLogger(__name__)

ADD = "add"
COMPLETE = "complete"

# The sentences of HassShoppingListAddItem and HassShoppingListCompleteItem from
# github.com/home-assistant/intents. Unlike there, a preposition is required
# right after {item}: triggers are matched before the todo sentences with a list
# name, and without it "füge Putzen zur Haushaltsliste hinzu" would add
# "Putzen zur Haushalts" here. tests/test_assist.py checks such sentences.
_LISTE = "[(meine|unsere|die) ][Einkaufs[ ]]Liste"
_LISTE_DAT = "[(meiner|unserer|der) ][Einkaufs[ ]]Liste"
_EINKAUF_DAT = "[(meinem|unserem|dem) ]Einkauf"
_VERB_AUF = "(setz[e]|schreib[e]|nehme|nimm|pack[e])"
SENTENCES: dict[str, dict[str, list[str]]] = {
    "en": {
        ADD: [
            "add {item} to [my|the] [shopping] list",
            "put {item} (on|in) [my|the] [shopping] list",
        ],
        COMPLETE: [
            "(check|complete|delete|remove) (off;{item}) (from|on|in) "
            "[my|the] [shopping] list",
            "(check|complete|delete|remove) {item} (off|from|on|in) "
            "[my|the] [shopping] list",
        ],
    },
    "de": {
        ADD: [
            f"füge {{item}} (zu|zur) {_LISTE_DAT} hinzu",
            f"füge {{item}} (zu|zum) {_EINKAUF_DAT} hinzu",
            f"füge[ (zu|zur)] {_LISTE_DAT} {{item}} hinzu",
            f"füge[ (zu|zum)] {_EINKAUF_DAT} {{item}} hinzu",
            f"{_VERB_AUF} {{item}} (auf|in) {_LISTE}",
            f"ergänze {{item}} (auf|in) {_LISTE_DAT}",
            f"{{item}} (auf|in) {_LISTE}[ (setzen|schreiben|nehmen|packen)]",
            f"{{item}} (auf|in) {_LISTE_DAT} ergänzen",
            f"{{item}} (zu|zur) {_LISTE_DAT} hinzufügen",
            f"{{item}} (zu|zum) {_EINKAUF_DAT} hinzufügen",
            f"{{item}} (auf|in) {_LISTE} hinzufügen",
        ],
        COMPLETE: [
            f"(entferne|lösch[e]|streich[e]) {{item}} (von|auf|aus) {_LISTE_DAT}",
            f"(nimm|nehm[e]|lösch[e]|streich[e]) {{item}} aus {_LISTE_DAT} raus",
            f"(nimm|nehm[e]|lösch[e]|streich[e]) {{item}} von {_LISTE_DAT} runter",
            f"(schließe|hake) {{item}} (von|auf|aus) {_LISTE_DAT} ab",
            f"{{item}} (von|auf|aus) {_LISTE_DAT} (entfernen|löschen|streichen)",
            f"{{item}} von {_LISTE_DAT} [runter[ ]]nehmen",
            f"{{item}} aus {_LISTE_DAT} [raus[ ]]nehmen",
            f"(entferne|lösch[e]|streich[e]) {{item}} (von|auf|aus) {_EINKAUF_DAT}",
            f"(nimm|nehm[e]|lösch[e]|streich[e]) {{item}} aus {_EINKAUF_DAT} raus",
            f"(nimm|nehm[e]|lösch[e]|streich[e]) {{item}} von {_EINKAUF_DAT} runter",
            f"{{item}} (von|auf|aus) {_EINKAUF_DAT} (entfernen|löschen|streichen)",
            f"{{item}} von {_EINKAUF_DAT} [runter[ ]]nehmen",
            f"{{item}} aus {_EINKAUF_DAT} [raus[ ]]nehmen",
        ],
    },
}

# Spoken answers, as the Shopping List integration gives them
RESPONSES: dict[str, dict[str, str]] = {
    "en": {
        "added": "Added {item}",
        "completed": "Checked off {item}",
        "not_found": "{item} is not on the list",
        "error": "Could not change the Zenkit list",
    },
    "de": {
        "added": "{item} hinzugefügt",
        "completed": "{item} abgehakt",
        "not_found": "{item} steht nicht auf der Liste",
        "error": "Die Zenkit-Liste konnte nicht geändert werden",
    },
}
DEFAULT_LANGUAGE = "en"


def _language(hass: HomeAssistant) -> str:
    """Language of the sentences, English for languages without them."""
    language = hass.config.language.split("-")[0].lower()
    return language if language in SENTENCES else DEFAULT_LANGUAGE


@callback
def async_setup_shopping_list(hass: HomeAssistant, entry: ZenkitConfigEntry) -> None:
    """Register the shopping list sentences for the list chosen in the options."""
    list_uuid = entry.options.get(CONF_SHOPPING_LIST)
    if not list_uuid:
        return
    language = _language(hass)
    responses = RESPONSES[language]
    unique_id = f"{entry.entry_id}_{list_uuid}"

    def entity_id() -> str:
        """Entity id of the list, it may be renamed at any time."""
        found = er.async_get(hass).async_get_entity_id(TODO_DOMAIN, DOMAIN, unique_id)
        if found is None:
            raise HomeAssistantError(f"No todo entity for list {list_uuid}")
        return found

    async def open_items(target: str) -> list[dict[str, Any]]:
        result = await hass.services.async_call(
            TODO_DOMAIN,
            "get_items",
            {"status": [TodoItemStatus.NEEDS_ACTION]},
            target={"entity_id": target},
            blocking=True,
            return_response=True,
        )
        return result[target]["items"]  # type: ignore[index]

    def find(items: list[dict[str, Any]], item: str) -> dict[str, Any] | None:
        return next(
            (i for i in items if i["summary"].casefold() == item.casefold()), None
        )

    async def add(target: str, item: str) -> str:
        # Like Shopping List, an item that is on the list already is not added
        if find(await open_items(target), item) is None:
            await hass.services.async_call(
                TODO_DOMAIN,
                "add_item",
                {"item": item},
                target={"entity_id": target},
                blocking=True,
            )
        return responses["added"]

    async def complete(target: str, item: str) -> str:
        if (found := find(await open_items(target), item)) is None:
            return responses["not_found"]
        await hass.services.async_call(
            TODO_DOMAIN,
            "update_item",
            {"item": found["uid"], "status": TodoItemStatus.COMPLETED},
            target={"entity_id": target},
            blocking=True,
        )
        return responses["completed"]

    def trigger(action: str):
        handler = add if action == ADD else complete

        async def handle(user_input: ConversationInput, result: RecognizeResult) -> str:
            item = str(result.entities["item"].value).strip()
            try:
                text = await handler(entity_id(), item)
            except HomeAssistantError as error:
                _LOGGER.warning("Assist could not %s %s: %s", action, item, error)
                text = responses["error"]
            return text.format(item=item)

        return handle

    manager = get_agent_manager(hass)
    for action, sentences in SENTENCES[language].items():
        entry.async_on_unload(manager.register_trigger(sentences, trigger(action)))
    _LOGGER.debug("Registered Assist shopping list sentences for %s", unique_id)
