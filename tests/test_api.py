"""Tests for the Zenkit api client."""

import datetime
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.exceptions import ServiceValidationError
from requests.exceptions import RequestException

from custom_components.zenkit.api import Zenkit, user_image_url
from custom_components.zenkit.exceptions import (
    CannotConnectException,
    CannotLoginException,
    UpdateFailedException,
)

TITLE = "title-uuid"
NOTES = "notes-uuid"
DUE = "due-uuid"
STAGE = "stage-uuid"
TODO_ID, DONE_ID = 1, 2

ENTRY = {
    "uuid": "entry-uuid",
    "displayString": "Buy milk",
    f"{TITLE}_text": "Buy milk",
    f"{STAGE}_categories": [TODO_ID],
}


def _element(role, options, category=6, uuid=STAGE, primary=False):
    return {
        "uuid": uuid,
        "elementcategory": category,
        "resourceRole": role,
        "isPrimary": primary,
        "elementData": {"predefinedCategories": options},
    }


def _option(id, role, color):
    return {"id": id, "resourceRole": role, "colorHex": color}


ELEMENTS = [
    _element("title", [], category=1, uuid=TITLE, primary=True),
    _element("notes", [], category=1, uuid=NOTES),
    _element("dueDate", [], category=4, uuid=DUE),
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
        requests.post.return_value = _response({})
        yield requests


def _put_body(requests_mock):
    assert requests_mock.put.call_count == 1
    return requests_mock.put.call_args.kwargs["json"]


def _post_body(requests_mock):
    assert requests_mock.post.call_count == 1
    return requests_mock.post.call_args.kwargs["json"]


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
        await Zenkit("key").update_entry("list", "entry-uuid", priority="high")
    requests_mock.put.assert_not_called()


@pytest.mark.parametrize(
    ("description", "value"), [("2 liters\noat", "2 liters\noat"), (None, None)]
)
async def test_update_description(requests_mock, description, value):
    await Zenkit("key").update_entry("list", "entry-uuid", description=description)

    assert _put_body(requests_mock) == {f"{NOTES}_text": value}


async def test_update_description_without_roles_uses_first_other_text_field(
    requests_mock,
):
    requests_mock.elements = [
        _element(None, [], category=1, uuid=TITLE, primary=True),
        _element(None, [], category=1, uuid=NOTES),
    ]

    await Zenkit("key").update_entry("list", "entry-uuid", description="2 liters")

    assert _put_body(requests_mock) == {f"{NOTES}_text": "2 liters"}


async def test_update_description_without_text_field_fails(requests_mock):
    requests_mock.elements = [_element("title", [], category=1, uuid=TITLE)]

    with pytest.raises(UpdateFailedException):
        await Zenkit("key").update_entry("list", "entry-uuid", description="2 liters")
    requests_mock.put.assert_not_called()


@pytest.mark.parametrize(
    ("due", "fields"),
    [
        (datetime.date(2026, 11, 3), {"_date": "2026-11-03", "_hasTime": False}),
        (
            datetime.datetime(
                2026,
                11,
                3,
                15,
                30,
                tzinfo=datetime.timezone(datetime.timedelta(hours=1)),
            ),
            {"_date": "2026-11-03T14:30:00.000Z", "_hasTime": True},
        ),
        (None, {"_date": None, "_hasTime": False}),
    ],
)
async def test_update_due(requests_mock, due, fields):
    await Zenkit("key").update_entry("list", "entry-uuid", due=due)

    assert _put_body(requests_mock) == {f"{DUE}{k}": v for k, v in fields.items()}


async def test_update_due_without_date_field_fails(requests_mock):
    requests_mock.elements = [_element("title", [], category=1, uuid=TITLE)]

    with pytest.raises(UpdateFailedException):
        await Zenkit("key").update_entry(
            "list", "entry-uuid", due=datetime.date(2026, 11, 3)
        )
    requests_mock.put.assert_not_called()


async def test_update_caches_elements(requests_mock):
    zk = Zenkit("key")

    await zk.update_entry("list", "entry-uuid", name="Buy oat milk")

    assert zk.elements == {"list": ELEMENTS}


async def test_create_entry_with_fields_in_one_request(requests_mock):
    await Zenkit("key").create_entry(
        "list",
        "entry-uuid",
        name="Buy milk",
        description="2 liters",
        due=datetime.date(2026, 11, 3),
    )

    assert _post_body(requests_mock) == {
        "uuid": "entry-uuid",
        f"{TITLE}_text": "Buy milk",
        f"{NOTES}_text": "2 liters",
        f"{DUE}_date": "2026-11-03",
        f"{DUE}_hasTime": False,
    }
    requests_mock.put.assert_not_called()


def _page(entries, total):
    return _response({"listEntries": entries, "countData": {"filteredTotal": total}})


def _error_response(status_code, text):
    response = _response(None, status_code)
    response.json.side_effect = ValueError("Expecting value")
    response.reason = "Error"
    response.text = text
    return response


@pytest.fixture
def no_sleep():
    with patch("custom_components.zenkit.api.asyncio.sleep") as sleep:
        yield sleep


async def test_get_list_entries_merges_pages(requests_mock):
    requests_mock.post.side_effect = [
        _page([{"id": i} for i in range(100)], 150),
        _page([{"id": i} for i in range(100, 150)], 150),
    ]

    entries = await Zenkit("key").get_list_entries("list")

    assert entries == [{"id": i} for i in range(150)]
    skips = [c.kwargs["json"]["skip"] for c in requests_mock.post.call_args_list]
    assert skips == [0, 100]


async def test_get_list_entries_empty_list(requests_mock):
    requests_mock.post.return_value = _page(None, 0)

    assert await Zenkit("key").get_list_entries("list") == []


async def test_get_list_entries_retries_failed_page(requests_mock, no_sleep):
    requests_mock.post.side_effect = [
        _page([{"id": i} for i in range(100)], 101),
        _error_response(502, "<html>Bad Gateway</html>"),
        _error_response(200, ""),
        _page([{"id": 100}], 101),
    ]

    entries = await Zenkit("key").get_list_entries("list")

    assert len(entries) == 101
    assert [c.args[0] for c in no_sleep.call_args_list] == [1, 3]


async def test_get_list_entries_fails_after_retries(requests_mock, no_sleep, caplog):
    requests_mock.post.return_value = _error_response(503, "<html>down</html>")

    with pytest.raises(UpdateFailedException):
        await Zenkit("key").get_list_entries("list")

    assert requests_mock.post.call_count == 3
    assert "HTTP 503 Error: <html>down</html>" in caplog.text


async def test_get_list_entries_client_error_is_not_retried(requests_mock, no_sleep):
    requests_mock.post.return_value = _error_response(404, "not found")

    with pytest.raises(UpdateFailedException):
        await Zenkit("key").get_list_entries("list")

    assert requests_mock.post.call_count == 1
    no_sleep.assert_not_called()


async def test_get_list_entries_retries_connection_error(requests_mock, no_sleep):
    from requests.exceptions import ConnectionError

    requests_mock.post.side_effect = [ConnectionError("reset"), _page([{"id": 1}], 1)]

    assert await Zenkit("key").get_list_entries("list") == [{"id": 1}]


@pytest.fixture
def user():
    return {"id": 1, "username": "user", "api_key": "key"}


async def test_login_returns_user(requests_mock, user):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response(user)

    assert await Zenkit("key").login() == user


async def test_login_invalid_key(requests_mock):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response({"error": {}}, status_code=401)

    with pytest.raises(CannotLoginException):
        await Zenkit("key").login()


async def test_login_server_error(requests_mock):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response(None, status_code=502)

    with pytest.raises(CannotConnectException):
        await Zenkit("key").login()


async def test_login_network_error(requests_mock):
    requests_mock.get.side_effect = RequestException("offline")

    with pytest.raises(CannotConnectException):
        await Zenkit("key").login()


async def test_unread_notifications_count(requests_mock):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response(
        {"newNotificationsCount": 3, "thereAreMoreResults": True, "notifications": []}
    )

    assert await Zenkit("key").get_unread_notifications_count() == 3
    assert requests_mock.get.call_args.kwargs["params"] == {"limit": 1}


async def test_unread_notifications_count_fails(requests_mock):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response({}, status_code=500)

    with pytest.raises(UpdateFailedException):
        await Zenkit("key").get_unread_notifications_count()


async def test_get_organization(requests_mock):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response(
        {"myOrganizationId": 2, "organizations": [{"id": 1}, {"id": 2, "name": "B"}]}
    )

    assert await Zenkit("key").get_organization(2) == {"id": 2, "name": "B"}
    assert await Zenkit("key").get_organization(3) is None
    assert requests_mock.get.call_args.args[0].endswith("/users/me/organizations")


async def test_get_organization_members_count(requests_mock):
    requests_mock.get.side_effect = None
    requests_mock.get.return_value = _response({"filteredTotal": 2, "users": []})

    assert await Zenkit("key").get_organization_members_count(1) == 2
    assert requests_mock.get.call_args.args[0].endswith("/organizations/1/users")


@pytest.mark.parametrize(
    ("user", "url"),
    [
        (
            {"imageLink": "123", "isImagePreferred": True},
            "https://zenkit.com/api/v1/files/123/convert?w=64&h=64",
        ),
        ({"imageLink": "123", "isImagePreferred": False}, None),
        ({"imageLink": None, "isImagePreferred": True}, None),
    ],
)
def test_user_image_url(user, url):
    assert user_image_url(user, 64) == url


def _workspace(id, name, parent=None, lists=()):
    return {
        "id": id,
        "name": name,
        "resourceType": "folder",
        "parentWorkspaceId": parent,
        "lists": [{"id": list_id, "name": f"List {list_id}"} for list_id in lists],
    }


def _workspaces(requests_mock, *workspaces):
    requests_mock.get.side_effect = lambda url, **kwargs: _response(list(workspaces))


async def test_get_lists_adds_folders(requests_mock):
    _workspaces(
        requests_mock,
        _workspace(1, "Home", lists=[10]),
        _workspace(2, "Garden", parent=1, lists=[20]),
        _workspace(3, "Beds", parent=2, lists=[30]),
    )

    lists = await Zenkit("key").get_lists()

    assert [list["id"] for list in lists] == [10, 20, 30]
    assert [list["_folder"] for list in lists] == [
        {"workspace": "Home", "folder": None, "folder_id": None, "folder_path": []},
        {
            "workspace": "Home",
            "folder": "Garden",
            "folder_id": 2,
            "folder_path": ["Garden"],
        },
        {
            "workspace": "Home",
            "folder": "Beds",
            "folder_id": 3,
            "folder_path": ["Garden", "Beds"],
        },
    ]


async def test_get_lists_unknown_parent_is_top_level(requests_mock):
    _workspaces(requests_mock, _workspace(2, "Shared", parent=99, lists=[20]))

    lists = await Zenkit("key").get_lists()

    assert lists[0]["_folder"]["workspace"] == "Shared"
    assert lists[0]["_folder"]["folder_path"] == []


async def test_get_lists_parent_cycle_stops(requests_mock):
    _workspaces(
        requests_mock,
        _workspace(1, "A", parent=2, lists=[10]),
        _workspace(2, "B", parent=1),
    )

    lists = await Zenkit("key").get_lists()

    assert lists[0]["_folder"] == {
        "workspace": "B",
        "folder": "A",
        "folder_id": 1,
        "folder_path": ["A"],
    }


LABELS = "labels-uuid"
ASSIGNEES = "assignees-uuid"
USERS = [
    {"id": 7, "displayname": "Jane Doe", "fullname": "Jane Doe", "username": "jane"},
    {"id": 8, "displayname": "John Roe", "fullname": "John Roe", "username": "john"},
]


def _named(id, name, role=None):
    return {"id": id, "name": name, "resourceRole": role}


@pytest.fixture
def full_list(requests_mock):
    """A list with named status and label options, an assignees field and members."""
    requests_mock.elements = [
        _element("title", [], category=1, uuid=TITLE, primary=True),
        {
            **_element(
                "stage",
                [_named(1, "To do", "todo"), _named(3, "In progress")],
            ),
            "name": "Phase",
        },
        {
            **_element("tags", [_named(5, "Important"), _named(6, "Later")]),
            "uuid": LABELS,
            "name": "Tags",
        },
        {**_element("assignments", [], category=14), "uuid": ASSIGNEES},
    ]
    requests_mock.get.side_effect = lambda url, **kwargs: _response(
        USERS if url.endswith("/users") else requests_mock.elements
    )
    return requests_mock


async def test_create_entry_with_status_labels_and_assignees(full_list):
    await Zenkit("key").create_entry(
        "list",
        "entry-uuid",
        name="Buy milk",
        status="in progress",
        labels=["Important", " later "],
        assignees=["Jane Doe", "john", "7"],
    )

    assert _post_body(full_list) == {
        "uuid": "entry-uuid",
        f"{TITLE}_text": "Buy milk",
        f"{STAGE}_categories": [3],
        f"{LABELS}_categories": [5, 6],
        f"{ASSIGNEES}_persons": [7, 8, 7],
    }
    assert full_list.get.call_args_list[-1].args[0].endswith("/lists/list/users")


async def test_create_entry_without_assignees_fetches_no_users(full_list):
    await Zenkit("key").create_entry("list", "entry-uuid", name="Buy milk")

    assert not any(
        call.args[0].endswith("/users") for call in full_list.get.call_args_list
    )


@pytest.mark.parametrize(
    ("kwargs", "key", "placeholders"),
    [
        (
            {"status": "Blocked"},
            "unknown_option",
            {"field": "Phase", "value": "Blocked", "options": "To do, In progress"},
        ),
        (
            {"labels": ["Important", "Urgent"]},
            "unknown_option",
            {"field": "Tags", "value": "Urgent", "options": "Important, Later"},
        ),
        (
            {"assignees": ["Max"]},
            "unknown_user",
            {"value": "Max", "users": "Jane Doe, John Roe"},
        ),
    ],
)
async def test_create_entry_with_unknown_value_fails(
    full_list, kwargs, key, placeholders
):
    with pytest.raises(ServiceValidationError) as error:
        await Zenkit("key").create_entry("list", "entry-uuid", name="x", **kwargs)

    assert error.value.translation_key == key
    assert error.value.translation_placeholders == placeholders
    full_list.post.assert_not_called()


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [({"labels": ["Important"]}, "labels"), ({"assignees": ["jane"]}, "assignees")],
)
async def test_create_entry_without_field_fails(requests_mock, kwargs, field):
    with pytest.raises(ServiceValidationError) as error:
        await Zenkit("key").create_entry("list", "entry-uuid", name="x", **kwargs)

    assert error.value.translation_key == "missing_field"
    assert error.value.translation_placeholders == {"field": field}
    requests_mock.post.assert_not_called()


async def test_update_status_by_name(full_list):
    await Zenkit("key").update_entry("list", "entry-uuid", status="To do")

    assert _put_body(full_list) == {f"{STAGE}_categories": [1]}


async def test_create_entry_with_checklist(requests_mock):
    await Zenkit("key").create_entry(
        "list",
        "entry-uuid",
        checklist={"name": "Packing", "items": ["Passport", "Charger"]},
        name="Trip",
    )

    body = _post_body(requests_mock)
    (checklist,) = body.pop("checklists")
    assert body == {"uuid": "entry-uuid", f"{TITLE}_text": "Trip"}
    assert checklist.pop("uuid")
    assert checklist == {
        "name": "Packing",
        "items": [
            {"text": "Passport", "checked": False},
            {"text": "Charger", "checked": False},
        ],
        "shouldCheckedItemsBeHidden": False,
    }


async def test_update_checklist_is_not_supported(requests_mock):
    with pytest.raises(NotImplementedError):
        await Zenkit("key").update_entry("list", "entry-uuid", checklist={})
