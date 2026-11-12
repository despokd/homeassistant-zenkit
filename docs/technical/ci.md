# CI

`.github/workflows/CI.yaml` runs on pushes to `main`, on pull requests, weekly (to catch breaking changes in Home Assistant, hassfest and HACS) and manually. A new push to a PR cancels its running checks.

| Job | Checks |
| --- | --- |
| Python Code Format Check | `black --check`, with the version pinned in `requirements_test.txt` |
| Tests (min) | `pytest` on Python 3.14 against the minimum supported Home Assistant (`requirements_test_min.txt`) |
| Tests (latest) | `pytest` on Python 3.14 against the latest `pytest-homeassistant` (`requirements_test.txt`) |
| Check hassfest | Home Assistant's integration validation |
| HACS Validation | HACS repository requirements |

Branch protection uses the job names as required status checks; renaming a job (including the matrix variants) needs an update there.

## Minimum Home Assistant version

`hacs.json` declares the oldest supported Home Assistant release. `Tests (min)` runs against it, with the requirements pinned in `requirements_test_min.txt`, and fails if the installed `homeassistant` differs from `hacs.json`. `Tests (latest)` runs against whatever `pytest-homeassistant` resolves to. It's published by Home Assistant core with each release and pins that exact `homeassistant` version, so it usually tracks the newest release.

To raise the minimum:

1. Set `homeassistant` in `hacs.json`.
2. In `requirements_test_min.txt`, pin `pytest-homeassistant` to the same version (its versions are Home Assistant's, and each pins `homeassistant` to its own version).
3. Pin the conversation integration's requirements to the versions of that release (`requirements` in `homeassistant/components/conversation/manifest.json`), adding any that are new.
4. Update the version in `docs/user/installation.md` and anywhere else `README.md` and `docs/` mention it.

Run the tests locally against the minimum in a separate venv: `uv venv -p 3.14 .venv-min && uv pip install -p .venv-min -r requirements_test_min.txt`, then `.venv-min/bin/python -m pytest`.

hassfest and HACS validation use the `master`/`main` branch of their actions on purpose, so they check against the current rules. All other actions are pinned to a major version.

`.github/workflows/pr-title.yaml` checks that PR titles follow Conventional Commits, see [Releases](releases.md).

## Dependabot

`.github/dependabot.yml` opens weekly PRs for:

- GitHub Actions versions, grouped into one PR, titled `ci: …`
- pinned versions in `requirements_test.txt` (currently `black`), titled `chore(deps): …`

Both prefixes don't trigger a release. Unpinned test requirements are not updated by Dependabot; CI always installs their latest version. The pins in `requirements_test_min.txt` are ignored, since they follow the minimum version in `hacs.json` and are bumped by hand.

## Test package

Tests use [`pytest-homeassistant`](https://pypi.org/project/pytest-homeassistant/), the test package Home Assistant core publishes since 2026.11. It replaced the community-maintained `pytest-homeassistant-custom-component`, which stopped at Home Assistant 2026.10.4; that is why the minimum Home Assistant version is 2026.11.0. The two must not be installed together (overlapping fixtures), so recreate an older local venv. `pytest.ini` disables the respx pytest plugin, as the package's README asks: it would import `httpx` before Home Assistant installs its alias for it.
