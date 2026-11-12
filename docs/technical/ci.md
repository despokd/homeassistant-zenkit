# CI

`.github/workflows/CI.yaml` runs on pushes to `main`, on pull requests, weekly (to catch breaking changes in Home Assistant, hassfest and HACS) and manually. A new push to a PR cancels its running checks.

| Job | Checks |
| --- | --- |
| Python Code Format Check | `black --check`, with the version pinned in `requirements_test.txt` |
| Tests (min) | `pytest` on Python 3.14 against the minimum supported Home Assistant (`requirements_test_min.txt`) |
| Tests (latest) | `pytest` on Python 3.14 against the latest `pytest-homeassistant-custom-component` (`requirements_test.txt`) |
| Check hassfest | Home Assistant's integration validation |
| HACS Validation | HACS repository requirements |

Branch protection uses the job names as required status checks; renaming a job (including the matrix variants) needs an update there.

## Minimum Home Assistant version

`hacs.json` declares the oldest supported Home Assistant release. `Tests (min)` runs against it, with the requirements pinned in `requirements_test_min.txt`, and fails if the installed `homeassistant` differs from `hacs.json`. `Tests (latest)` runs against whatever `pytest-homeassistant-custom-component` resolves to, which tracks the newest release.

To raise the minimum:

1. Set `homeassistant` in `hacs.json`.
2. In `requirements_test_min.txt`, pin the `pytest-homeassistant-custom-component` version that requires exactly that `homeassistant` version (its versions follow Home Assistant releases; check the `homeassistant==` requirement on PyPI, e.g. `https://pypi.org/pypi/pytest-homeassistant-custom-component/<version>/json`).
3. Pin the conversation integration's requirements to the versions of that release (`requirements` in `homeassistant/components/conversation/manifest.json`), adding any that are new, such as `gazetteer-matcher` from 2026.9.
4. Update the version in `docs/user/installation.md` and anywhere else `README.md` and `docs/` mention it.

Run the tests locally against the minimum in a separate venv: `uv venv -p 3.14 .venv-min && uv pip install -p .venv-min -r requirements_test_min.txt`, then `.venv-min/bin/python -m pytest`.

hassfest and HACS validation use the `master`/`main` branch of their actions on purpose, so they check against the current rules. All other actions are pinned to a major version.

`.github/workflows/pr-title.yaml` checks that PR titles follow Conventional Commits, see [Releases](releases.md).

## Dependabot

`.github/dependabot.yml` opens weekly PRs for:

- GitHub Actions versions, grouped into one PR, titled `ci: …`
- pinned versions in `requirements_test.txt` (currently `black`), titled `chore(deps): …`

Both prefixes don't trigger a release. Unpinned test requirements are not updated by Dependabot; CI always installs their latest version. The pins in `requirements_test_min.txt` are ignored, since they follow the minimum version in `hacs.json` and are bumped by hand.
