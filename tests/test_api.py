"""Tests for the Zenkit api client."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.zenkit.api import Zenkit
from custom_components.zenkit.exceptions import UpdateFailedException

TITLE = "title-uuid"
STAGE = "stage-uuid"
TODO_ID, DONE_ID = 1, 2

ENTRY = {
    "uuid": "entry-uuid",
    "displayString": "Buy milk",
    f"{TITLE}_text": "Buy milk",
    f"{STAGE}_categories": [TODO_ID],
}


def _element(role, options, category=6, uuid=STAGE):
    return {
        "uuid": uuid,
        "elementcategory": category,
        "resourceRole": role,
        "elementData": {"predefinedCategories": options},
    }


def _option(id, role, color):
    return {"id": id, "resourceRole": role, "colorHex": color}


ELEMENTS = [
    _element("title", [], category=1, uuid=TITLE),
    _element(
        "stage",
        [_option(TODO_ID, "todo", "#0089d1"), _option(DONE_ID, "done", "#3ba744")],
    ),
]


def _response(json, status_code=200):
    response = MagicMock(status_code=status_code)
    response.json.return_value = json
    return response


@pytest.fixture
def requests_mock():
    """Mock requests: GET returns the entry or elements, PUT succeeds."""
    with patch("custom_components.zenkit.api.requests") as requests:
        requests.elements = ELEMENTS
        requests.get.side_effect = lambda url, **kwargs: _response(
            requests.elements if url.endswith("/elements") else ENTRY
        )
        requests.put.return_value = _response({})
        yield requests


def _put_body(requests_mock):
    assert requests_mock.put.call_count == 1
    return requests_mock.put.call_args.kwargs["json"]


async def test_update_name(requests_mock):
    await Zenkit("key").update_entry("list", "entry-uuid", name="Buy oat milk")

    assert _put_body(requests_mock) == {f"{TITLE}_text": "Buy oat milk"}


@pytest.mark.parametrize(
    ("completed", "option_id"), [(True, DONE_ID), (False, TODO_ID)]
)
async def test_update_completed(requests_mock, completed, option_id):
    await Zenkit("key").update_entry("list", "entry-uuid", completed=completed)

    assert _put_body(requests_mock) == {f"{STAGE}_categories": [option_id]}


async def test_update_name_and_completed_in_one_request(requests_mock):
    await Zenkit("key").update_entry(
        "list", "entry-uuid", name="Buy oat milk", completed=True
    )

    assert _put_body(requests_mock) == {
        f"{TITLE}_text": "Buy oat milk",
        f"{STAGE}_categories": [DONE_ID],
    }


async def test_update_completed_without_roles_uses_color(requests_mock):
    requests_mock.elements = [
        _element(None, [_option(7, None, "#0089d1"), _option(8, None, "#3ba744")])
    ]

    await Zenkit("key").update_entry("list", "entry-uuid", completed=True)

    assert _put_body(requests_mock) == {f"{STAGE}_categories": [8]}


async def test_update_open_without_todo_option_clears_status(requests_mock):
    requests_mock.elements = [_element("stage", [_option(DONE_ID, "done", "#3ba744")])]

    await Zenkit("key").update_entry("list", "entry-uuid", completed=False)

    assert _put_body(requests_mock) == {f"{STAGE}_categories": []}


async def test_update_completed_without_status_field_fails(requests_mock):
    requests_mock.elements = [_element("title", [], category=1, uuid=TITLE)]

    with pytest.raises(UpdateFailedException):
        await Zenkit("key").update_entry("list", "entry-uuid", completed=True)
    requests_mock.put.assert_not_called()


async def test_update_unsupported_field_fails(requests_mock):
    with pytest.raises(NotImplementedError):
        await Zenkit("key").update_entry("list", "entry-uuid", description="2 liters")
    requests_mock.put.assert_not_called()
