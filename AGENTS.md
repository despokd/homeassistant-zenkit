# AGENTS.md

Home Assistant custom integration (`custom_components/zenkit/`) exposing Zenkit lists as HA `todo` entities. Zenkit is a project management / task platform.

# Architecture

`config_flow.py` (API key) → `api.py` (REST client) → `coordinator.py` (polling) → `todo.py` (one entity per list). Details: [docs/technical/architecture.md](docs/technical/architecture.md).

Key facts:

- `api.py` uses sync `requests` wrapped in `asyncio.to_thread`, not aiohttp.
- Zenkit has no fixed todo schema; fields are user-defined and keyed `<elementUuid>_<type>`. Summary/status/description/due are derived heuristically in `todo.py`.
- Writes support `name`, `completed`, `description`, `due`, `status`, `labels` and `assignees` (option and member names, see `_entry_fields` in `api.py`); other fields raise `NotImplementedError`. The todo entity only writes the first four, `zenkit.create_entry` (`services.py`) the rest, and a `checklist` on create only.
- After any write, entities call `coordinator.async_refresh_list(shortId)`. A list that fails to load only makes its own entity unavailable (`coordinator.failed_lists`).
- Zenkit API quirks and undocumented behavior go in [docs/zenkit/](docs/zenkit/README.md).
- docs have a README.md in each directory as starting point
- Every entity attribute needs a translated name (`entity.<platform>.<translation_key>.state_attributes.<attribute>.name`) in `strings.json`, `translations/en.json` and `translations/de.json`. The entity needs a `translation_key` for this. `tests/test_translations.py` checks it.
- `README.md` is the page shown in the HA Marketplace and HACS. Use absolute `raw.githubusercontent.com` URLs for images there (relative paths and `brands.home-assistant.io` don't work).

## Resources

- [Zenkit User Docs](https://help.zenkit.com/en/support/home)
- [Zenkit Api Docs](https://todo.zenkit.com/docs/api/overview/structure)

## Development

Docker compose at `localhost:8123` with user `docker` password `docker`. Access via API. Zenkit API key will be added by user at HA.

After changing code in `custom_components/zenkit/`, restart the local HA instance so it loads the mounted code (a config entry reload does not re-import changed modules): call the `homeassistant.restart` service via the HA API and wait until `/api/config` responds again. Note that HA keeps the entity ID of an entity it has seen before, so changed entity ID logic only shows for new entities.

Before each commit, check `README.md` and `docs/` against the change: search them for the features, entities, attributes and terms it touches, until every statement about the changed behavior (including limitations, intervals, entity ids and devices) matches the code. User-facing behavior lives in `README.md` and `docs/user/`, internals in `docs/technical/`.

Commit messages and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …); they drive the automated version bump and release notes. Don't bump the version by hand. Details: [docs/technical/releases.md](docs/technical/releases.md).

Tests: `python3 -m venv .venv && .venv/bin/pip install -r requirements_test.txt`, then `.venv/bin/python -m pytest`. Formatting is checked with `black`.

## TODOs

Use GitHub issues