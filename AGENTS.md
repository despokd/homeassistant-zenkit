# AGENTS.md

Home Assistant custom integration (`custom_components/zenkit/`) exposing Zenkit lists as HA `todo` entities. Zenkit is a project management / task platform.

# Architecture

`config_flow.py` (API key) → `api.py` (REST client) → `coordinator.py` (polling) → `todo.py` (one entity per list). Details: [docs/technical/architecture.md](docs/technical/architecture.md).

Key facts:

- `api.py` uses sync `requests` wrapped in `asyncio.to_thread`, not aiohttp.
- Zenkit has no fixed todo schema; fields are user-defined and keyed `<elementUuid>_<type>`. Summary/status/description/due are derived heuristically in `todo.py`.
- Updates support `name` and `completed`; other fields raise `NotImplementedError` in `api.update_entry`.
- After any write, entities call `coordinator.async_refresh_list(shortId)`. A list that fails to load only makes its own entity unavailable (`coordinator.failed_lists`).
- Zenkit API quirks and undocumented behavior go in [docs/zenkit/](docs/zenkit/README.md).
- docs have a README.md in each directory as starting point

## Resources

- [Zenkit User Docs](https://help.zenkit.com/en/support/home)
- [Zenkit Api Docs](https://todo.zenkit.com/docs/api/overview/structure)

## Development

Docker compose at `localhost:8123` with user `docker` password `docker`. Access via API. Zenkit API key will be added by user at HA.

Tests: `python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt`, then `.venv/bin/python -m pytest`. Formatting is checked with `black`.

## TODOs

Use GitHub issues