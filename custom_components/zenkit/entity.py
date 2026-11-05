"""Helpers for the entities of Zenkit lists."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import ZenkitDataUpdateCoordinator


@callback
def async_add_list_entities(
    coordinator: ZenkitDataUpdateCoordinator,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    entities_fn: Callable[[dict], Iterable[Entity]],
) -> None:
    """Add the entities of each list, and of lists added later in Zenkit.

    On every coordinator update, entities whose unique id is new are added, e.g.
    of a new list or a calendar once the fields of its list are known. Entities
    of removed lists are removed with their device, see __init__.py.
    """
    # Unique ids of the added entities by list uuid
    added: dict[str, set[str]] = {}

    @callback
    def add_new_entities() -> None:
        uuids = {zenkit_list["uuid"] for zenkit_list in coordinator.lists}
        for uuid in added.keys() - uuids:
            # A list restored in Zenkit gets its entities again
            del added[uuid]
        new_entities = []
        for zenkit_list in coordinator.lists:
            known = added.setdefault(zenkit_list["uuid"], set())
            for entity in entities_fn(zenkit_list):
                if entity.unique_id not in known:
                    known.add(entity.unique_id)
                    new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(add_new_entities))
