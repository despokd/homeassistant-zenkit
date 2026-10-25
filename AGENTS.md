# AGENTS.md

Home Assistant custom integration (`custom_components/zenkit/`) exposing Zenkit lists as HA `todo` entities. Zenkit is a project management / task platform.

# Architecture

`config_flow.py` (API key) → `api.py` (REST client) → `coordinator.py` (polling) → `todo.py` (one entity per list). Details: [docs/technical/architecture.md](docs/technical/architecture.md).

Key facts:

- `api.py` uses sync `requests` wrapped in `asyncio.to_thread`, not aiohttp.
- Zenkit has no fixed todo schema; fields are user-defined and keyed `<elementUuid>_<type>`. Summary/status/description/due are derived heuristically in `todo.py`.
- Updates only support `name`; other fields raise `NotImplementedError` in `api.update_entry`.
- After any write, entities call `coordinator.async_refresh()`.
- Zenkit API quirks and undocumented behavior go in [docs/zenkit/](docs/zenkit/README.md).
- docs have a README.md in each directory as starting point

## Resources

- [Zenkit User Docs](https://help.zenkit.com/en/support/home)
- [Zenkit Api Docs](https://todo.zenkit.com/docs/api/overview/structure)

## Development

Docker compose at `localhost:8123` with user `docker` password `docker`. Zenkit API key will be added by user at HA.

## TODOs

Use GitHub issues