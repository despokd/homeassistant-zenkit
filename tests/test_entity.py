"""Tests for the entities of Zenkit lists."""

from unittest.mock import MagicMock

from custom_components.zenkit.entity import async_add_list_entities


def _entity(unique_id):
    entity = MagicMock()
    entity.unique_id = unique_id
    return entity


def _setup(lists, entities_fn=lambda list: [_entity(list["uuid"])]):
    """Set up with a coordinator update callback and the added unique ids."""
    coordinator = MagicMock()
    coordinator.lists = lists
    added = []
    async_add_list_entities(
        coordinator,
        MagicMock(),
        lambda entities: added.extend(entity.unique_id for entity in entities),
        entities_fn,
    )
    update = coordinator.async_add_listener.call_args.args[0]
    return coordinator, update, added


def test_adds_entities_of_lists():
    _, _, added = _setup([{"uuid": "a"}, {"uuid": "b"}])

    assert added == ["a", "b"]


def test_adds_entities_of_new_lists_once():
    coordinator, update, added = _setup([{"uuid": "a"}])
    coordinator.lists = [{"uuid": "a"}, {"uuid": "b"}]

    update()
    update()

    assert added == ["a", "b"]


def test_adds_entities_once_list_supports_them():
    supported = set()
    coordinator, update, added = _setup(
        [{"uuid": "a"}],
        lambda list: [_entity(list["uuid"])] if list["uuid"] in supported else [],
    )
    supported.add("a")

    update()

    assert added == ["a"]


def test_restored_list_gets_entities_again():
    coordinator, update, added = _setup([{"uuid": "a"}])
    coordinator.lists = []
    update()
    coordinator.lists = [{"uuid": "a"}]

    update()

    assert added == ["a", "a"]
