"""Tests for the Zenkit api client."""

import datetime
import re
from dataclasses import dataclass
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

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


@dataclass
class Reply:
    """A response of the fake API, or a connection error to raise."""

    json: Any = None
    status: int = 200
    text: str | None = None
    exc: Exception | None = None


def _response(json, status_code=200):
    return Reply(json=json, status=status_code)


class FakeApi:
    """Zenkit API on aioclient_mock.

    Each method answers with a function of the URL, or a list of replies in order
    (the last one repeats). By default GET returns the entry or the elements, and
    writes succeed.
    """

    def __init__(self, hass, aioclient_mock) -> None:
        self._mock = aioclient_mock
        self.session = async_get_clientsession(hass)
        self.elements = ELEMENTS
        self.get = lambda url: _response(
            self.elements if url.endswith("/elements") else ENTRY
        )
        self.post = [_response({})]
        self.put = [_response({})]
        for method in ("get", "post", "put"):
            aioclient_mock.request(method, re.compile("."), side_effect=self._reply)

    async def _reply(self, method, url, data):
        handler = getattr(self, method.lower())
        if callable(handler):
            reply = handler(str(url))
        else:
            reply = handler.pop(0) if len(handler) > 1 else handler[0]
        return AiohttpClientMockResponse(
            method,
            url,
            status=reply.status,
            json=reply.json,
            text=reply.text,
            exc=reply.exc,
        )

    def calls(self, method: str) -> list[tuple[str, Any]]:
        """URLs and JSON bodies of the requests sent with a method."""
        return [
            (str(url), data)
            for m, url, data, _ in self._mock.mock_calls
            if m.upper() == method
        ]

    def zenkit(self) -> Zenkit:
        return Zenkit(self.session, "key")


@pytest.fixture
def api(hass, aioclient_mock):
    """Mock the Zenkit API."""
    return FakeApi(hass, aioclient_mock)


def _put_body(api):
    (call,) = api.calls("PUT")
    return call[1]


def _post_body(api):
    (call,) = api.calls("POST")
    return call[1]


async def test_update_name(api):
    await api.zenkit().update_entry("list", "entry-uuid", name="Buy oat milk")

    assert _put_body(api) == {f"{TITLE}_text": "Buy oat milk"}


@pytest.mark.parametrize(
    ("completed", "option_id"), [(True, DONE_ID), (False, TODO_ID)]
)
async def test_update_completed(api, completed, option_id):
    await api.zenkit().update_entry("list", "entry-uuid", completed=completed)

    assert _put_body(api) == {f"{STAGE}_categories": [option_id]}


async def test_update_name_and_completed_in_one_request(api):
    await api.zenkit().update_entry(
        "list", "entry-uuid", name="Buy oat milk", completed=True
    )

    assert _put_body(api) == {
        f"{TITLE}_text": "Buy oat milk",
        f"{STAGE}_categories": [DONE_ID],
    }


async def test_update_completed_without_roles_uses_color(api):
    api.elements = [
        _element(None, [_option(7, None, "#0089d1"), _option(8, None, "#3ba744")])
    ]

    await api.zenkit().update_entry("list", "entry-uuid", completed=True)

    assert _put_body(api) == {f"{STAGE}_categories": [8]}


async def test_update_open_without_todo_option_clears_status(api):
    api.elements = [_element("stage", [_option(DONE_ID, "done", "#3ba744")])]

    await api.zenkit().update_entry("list", "entry-uuid", completed=False)

    assert _put_body(api) == {f"{STAGE}_categories": []}


async def test_update_completed_without_status_field_fails(api):
    api.elements = [_element("title", [], category=1, uuid=TITLE)]

    with pytest.raises(UpdateFailedException):
        await api.zenkit().update_entry("list", "entry-uuid", completed=True)
    assert not api.calls("PUT")


async def test_update_unsupported_field_fails(api):
    with pytest.raises(NotImplementedError):
        await api.zenkit().update_entry("list", "entry-uuid", priority="high")
    assert not api.calls("PUT")


@pytest.mark.parametrize(
    ("description", "value"), [("2 liters\noat", "2 liters\noat"), (None, None)]
)
async def test_update_description(api, description, value):
    await api.zenkit().update_entry("list", "entry-uuid", description=description)

    assert _put_body(api) == {f"{NOTES}_text": value}


async def test_update_description_without_roles_uses_first_other_text_field(
    api,
):
    api.elements = [
        _element(None, [], category=1, uuid=TITLE, primary=True),
        _element(None, [], category=1, uuid=NOTES),
    ]

    await api.zenkit().update_entry("list", "entry-uuid", description="2 liters")

    assert _put_body(api) == {f"{NOTES}_text": "2 liters"}


async def test_update_description_without_text_field_fails(api):
    api.elements = [_element("title", [], category=1, uuid=TITLE)]

    with pytest.raises(UpdateFailedException):
        await api.zenkit().update_entry("list", "entry-uuid", description="2 liters")
    assert not api.calls("PUT")


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
async def test_update_due(api, due, fields):
    await api.zenkit().update_entry("list", "entry-uuid", due=due)

    assert _put_body(api) == {f"{DUE}{k}": v for k, v in fields.items()}


async def test_update_due_without_date_field_fails(api):
    api.elements = [_element("title", [], category=1, uuid=TITLE)]

    with pytest.raises(UpdateFailedException):
        await api.zenkit().update_entry(
            "list", "entry-uuid", due=datetime.date(2026, 11, 3)
        )
    assert not api.calls("PUT")


async def test_update_caches_elements(api):
    zk = api.zenkit()

    await zk.update_entry("list", "entry-uuid", name="Buy oat milk")

    assert zk.elements == {"list": ELEMENTS}


async def test_create_entry_with_fields_in_one_request(api):
    await api.zenkit().create_entry(
        "list",
        "entry-uuid",
        name="Buy milk",
        description="2 liters",
        due=datetime.date(2026, 11, 3),
    )

    assert _post_body(api) == {
        "uuid": "entry-uuid",
        f"{TITLE}_text": "Buy milk",
        f"{NOTES}_text": "2 liters",
        f"{DUE}_date": "2026-11-03",
        f"{DUE}_hasTime": False,
    }
    assert not api.calls("PUT")


def _page(entries, total):
    return _response({"listEntries": entries, "countData": {"filteredTotal": total}})


def _error_response(status_code, text):
    return Reply(status=status_code, text=text)


@pytest.fixture
def no_sleep():
    with patch("custom_components.zenkit.api.asyncio.sleep") as sleep:
        yield sleep


async def test_get_list_entries_merges_pages(api):
    api.post = [
        _page([{"id": i} for i in range(100)], 150),
        _page([{"id": i} for i in range(100, 150)], 150),
    ]

    entries = await api.zenkit().get_list_entries("list")

    assert entries == [{"id": i} for i in range(150)]
    skips = [body["skip"] for _, body in api.calls("POST")]
    assert skips == [0, 100]


async def test_get_list_entries_empty_list(api):
    api.post = [_page(None, 0)]

    assert await api.zenkit().get_list_entries("list") == []


async def test_get_list_entries_retries_failed_page(api, no_sleep):
    api.post = [
        _page([{"id": i} for i in range(100)], 101),
        _error_response(502, "<html>Bad Gateway</html>"),
        _error_response(200, ""),
        _page([{"id": 100}], 101),
    ]

    entries = await api.zenkit().get_list_entries("list")

    assert len(entries) == 101
    assert [c.args[0] for c in no_sleep.call_args_list] == [1, 3]


async def test_get_list_entries_fails_after_retries(api, no_sleep, caplog):
    api.post = [_error_response(503, "<html>down</html>")]

    with pytest.raises(UpdateFailedException):
        await api.zenkit().get_list_entries("list")

    assert len(api.calls("POST")) == 3
    assert "HTTP 503: <html>down</html>" in caplog.text


async def test_get_list_entries_client_error_is_not_retried(api, no_sleep):
    api.post = [_error_response(404, "not found")]

    with pytest.raises(UpdateFailedException):
        await api.zenkit().get_list_entries("list")

    assert len(api.calls("POST")) == 1
    no_sleep.assert_not_called()


@pytest.mark.parametrize(
    "error", [aiohttp.ClientConnectionError("reset"), TimeoutError()]
)
async def test_get_list_entries_retries_connection_error(api, no_sleep, error):
    api.post = [Reply(exc=error), _page([{"id": 1}], 1)]

    assert await api.zenkit().get_list_entries("list") == [{"id": 1}]


def _filter(api):
    return api.calls("POST")[-1][1]["filter"]


async def test_get_list_entries_unfiltered_without_fields(api):
    api.post = [_page([{"id": 1}], 1)]

    await api.zenkit().get_list_entries("list")

    assert _filter(api) == {}


async def test_get_list_entries_leaves_out_completed(api):
    api.post = [
        _page([{"id": i} for i in range(100)], 101),
        _page([{"id": 100}], 101),
    ]
    zk = api.zenkit()
    zk.elements["list"] = [*ELEMENTS[:3], {**ELEMENTS[3], "id": 7}]

    await zk.get_list_entries("list")

    expected = {
        "AND": {
            "TERMS": [
                {
                    "elementId": 7,
                    "modus": "contains",
                    "filterCategories": [DONE_ID],
                    "negated": True,
                }
            ]
        }
    }
    filters = [body["filter"] for _, body in api.calls("POST")]
    assert filters == [expected, expected]


async def test_get_list_entries_filters_status_found_by_color(api):
    api.post = [_page([], 0)]
    zk = api.zenkit()
    zk.elements["list"] = [
        {**_element(None, [_option(DONE_ID, None, "#3ba744")]), "id": 8}
    ]

    await zk.get_list_entries("list")

    term = _filter(api)["AND"]["TERMS"][0]
    assert (term["elementId"], term["filterCategories"]) == (8, [DONE_ID])


async def test_get_list_entries_unfiltered_without_done_option(api):
    api.post = [_page([], 0)]
    zk = api.zenkit()
    zk.elements["list"] = [
        {**_element("stage", [_option(TODO_ID, "todo", "#0089d1")]), "id": 9}
    ]

    await zk.get_list_entries("list")

    assert _filter(api) == {}


@pytest.fixture
def user():
    return {"id": 1, "username": "user", "api_key": "key"}


async def test_login_returns_user(api, user):
    api.get = lambda url: _response(user)

    assert await api.zenkit().login() == user


async def test_login_invalid_key(api):
    api.get = lambda url: _response({"error": {}}, status_code=401)

    with pytest.raises(CannotLoginException):
        await api.zenkit().login()


async def test_login_server_error(api):
    api.get = lambda url: _response(None, status_code=502)

    with pytest.raises(CannotConnectException):
        await api.zenkit().login()


async def test_login_network_error(api):
    api.get = lambda url: Reply(exc=aiohttp.ClientConnectionError("offline"))

    with pytest.raises(CannotConnectException):
        await api.zenkit().login()


async def test_unread_notifications_count(api):
    api.get = lambda url: _response(
        {"newNotificationsCount": 3, "thereAreMoreResults": True, "notifications": []}
    )

    assert await api.zenkit().get_unread_notifications_count() == 3
    assert api.calls("GET")[-1][0].endswith("/users/me/notifications?limit=1")


async def test_unread_notifications_count_fails(api):
    api.get = lambda url: _response({}, status_code=500)

    with pytest.raises(UpdateFailedException):
        await api.zenkit().get_unread_notifications_count()


async def test_get_organization(api):
    api.get = lambda url: _response(
        {"myOrganizationId": 2, "organizations": [{"id": 1}, {"id": 2, "name": "B"}]}
    )

    assert await api.zenkit().get_organization(2) == {"id": 2, "name": "B"}
    assert await api.zenkit().get_organization(3) is None
    assert api.calls("GET")[-1][0].endswith("/users/me/organizations")


async def test_get_organization_members_count(api):
    api.get = lambda url: _response({"filteredTotal": 2, "users": []})

    assert await api.zenkit().get_organization_members_count(1) == 2
    assert api.calls("GET")[-1][0].endswith("/organizations/1/users")


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


def _workspaces(api, *workspaces):
    api.get = lambda url: _response(list(workspaces))


async def test_get_lists_adds_folders(api):
    _workspaces(
        api,
        _workspace(1, "Home", lists=[10]),
        _workspace(2, "Garden", parent=1, lists=[20]),
        _workspace(3, "Beds", parent=2, lists=[30]),
    )

    lists = await api.zenkit().get_lists()

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


async def test_get_lists_unknown_parent_is_top_level(api):
    _workspaces(api, _workspace(2, "Shared", parent=99, lists=[20]))

    lists = await api.zenkit().get_lists()

    assert lists[0]["_folder"]["workspace"] == "Shared"
    assert lists[0]["_folder"]["folder_path"] == []


async def test_get_lists_parent_cycle_stops(api):
    _workspaces(
        api,
        _workspace(1, "A", parent=2, lists=[10]),
        _workspace(2, "B", parent=1),
    )

    lists = await api.zenkit().get_lists()

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
def full_list(api):
    """A list with named status and label options, an assignees field and members."""
    api.elements = [
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
    api.get = lambda url: _response(USERS if url.endswith("/users") else api.elements)
    return api


async def test_create_entry_with_status_labels_and_assignees(full_list):
    await full_list.zenkit().create_entry(
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
    assert full_list.calls("GET")[-1][0].endswith("/lists/list/users")


async def test_create_entry_without_assignees_fetches_no_users(full_list):
    await full_list.zenkit().create_entry("list", "entry-uuid", name="Buy milk")

    assert not any(url.endswith("/users") for url, _ in full_list.calls("GET"))


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
        await full_list.zenkit().create_entry("list", "entry-uuid", name="x", **kwargs)

    assert error.value.translation_key == key
    assert error.value.translation_placeholders == placeholders
    assert not full_list.calls("POST")


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [({"labels": ["Important"]}, "labels"), ({"assignees": ["jane"]}, "assignees")],
)
async def test_create_entry_without_field_fails(api, kwargs, field):
    with pytest.raises(ServiceValidationError) as error:
        await api.zenkit().create_entry("list", "entry-uuid", name="x", **kwargs)

    assert error.value.translation_key == "missing_field"
    assert error.value.translation_placeholders == {"field": field}
    assert not api.calls("POST")


async def test_update_status_by_name(full_list):
    await full_list.zenkit().update_entry("list", "entry-uuid", status="To do")

    assert _put_body(full_list) == {f"{STAGE}_categories": [1]}


async def test_create_entry_with_checklist(api):
    await api.zenkit().create_entry(
        "list",
        "entry-uuid",
        checklist={"name": "Packing", "items": ["Passport", "Charger"]},
        name="Trip",
    )

    body = _post_body(api)
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


async def test_update_checklist_is_not_supported(api):
    with pytest.raises(NotImplementedError):
        await api.zenkit().update_entry("list", "entry-uuid", checklist={})
