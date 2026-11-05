# 0001 HTTP client: Home Assistant's shared aiohttp session

Status: accepted, implemented ([#35](https://github.com/despokd/homeassistant-zenkit/issues/35))

## Context

Before, `api.py` sent every request with `requests.get/post/put` wrapped in `asyncio.to_thread`:

- Each call opens a new HTTPS connection (DNS, TCP and TLS handshake) to the same host. A poll of a 16-list account makes about 34 calls.
- Each call occupies a thread of Home Assistant's shared executor.
- No call sets a timeout. `requests` waits forever by default, so a stalled Zenkit server can block a refresh and its executor thread indefinitely.

Calls are sequential (no `asyncio.gather`), so the handshake cost adds up per poll.

Two options were considered:

| | A: `requests.Session` per `Zenkit` client | B: HA's shared aiohttp session |
|---|---|---|
| Connection reuse | Yes (keep-alive) | Yes (pool shared with HA) |
| Executor threads | Still one per call | None |
| Lifecycle | Close on unload, also the client of the config flow | Owned by HA, nothing to close |
| Timeouts | Need adding to every call | `aiohttp.ClientTimeout` on the session call |
| Change size | Small, tests mostly unchanged | Every call site and the tests |
| HA convention | No | Yes, inject the web session (as core Todoist does) |

## Decision

Use option B: `Zenkit` takes an `aiohttp.ClientSession` from `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)` and sends requests with it directly, without threads.

## Consequences

- **Constructor:** `Zenkit(api_key)` becomes `Zenkit(session, api_key)`. `__init__.py` and `config_flow.py` pass `async_get_clientsession(hass)`. The client never closes the session, HA owns it.
- **Call sites:** every request goes through `Zenkit._request(method, url, json=, params=)`. It sends `session.request(...)` and reads the body as text inside the `async with` block, into a `_Response(status, text)` that outlives the connection. `_log_error` and `_is_retryable` use `status` instead of `status_code`; the log line no longer has the HTTP reason phrase.
- **Errors:** `requests.exceptions.RequestException` becomes `aiohttp.ClientError` plus `TimeoutError`. The mapping to `CannotConnectException`, `CannotLoginException` and `UpdateFailedException` and the retry loop with `RETRY_DELAYS` stay as they are. `_Response.json()` parses with `json.loads`, so a non-JSON body (such as a proxy error page) still raises `ValueError`, regardless of the response's content type. Calls without error handling let `aiohttp.ClientError` and `TimeoutError` propagate, as `RequestException` did.
- **Timeouts:** every request gets `aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)` (30 s, `const.py`), so a stalled server fails the request and the retry or error path runs instead of hanging.
- **Requirements:** `requests` is no longer imported. `aiohttp` ships with HA, so `manifest.json` still lists no requirements.
- **Tests:** `tests/test_api.py` used to patch `custom_components.zenkit.api.requests`. Its `api` fixture is now a `FakeApi` on the `aioclient_mock` fixture of `pytest-homeassistant-custom-component`: each method answers with a function of the URL or a list of replies in order, and `api.calls(method)` returns the URLs and JSON bodies sent. Other tests mock `Zenkit` and are unchanged.
- **Behavior:** requests stay sequential, the number of requests per poll is unchanged. Running list fetches in parallel becomes possible later but is a separate decision (Zenkit rate limits are undocumented; `_is_retryable` already treats HTTP 429 as transient).
