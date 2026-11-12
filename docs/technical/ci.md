# CI

`.github/workflows/CI.yaml` runs on pushes to `main`, on pull requests, weekly (to catch breaking changes in Home Assistant, hassfest and HACS) and manually. A new push to a PR cancels its running checks.

| Job | Checks |
| --- | --- |
| Python Code Format Check | `black --check`, with the version pinned in `requirements_test.txt` |
| Tests | `pytest` on Python 3.14 against the latest `pytest-homeassistant-custom-component` |
| Check hassfest | Home Assistant's integration validation |
| HACS Validation | HACS repository requirements |

hassfest and HACS validation use the `master`/`main` branch of their actions on purpose, so they check against the current rules. All other actions are pinned to a major version.

`.github/workflows/pr-title.yaml` checks that PR titles follow Conventional Commits, see [Releases](releases.md).

## Dependabot

`.github/dependabot.yml` opens weekly PRs for:

- GitHub Actions versions, grouped into one PR, titled `ci: …`
- pinned versions in `requirements_test.txt` (currently `black`), titled `chore(deps): …`

Both prefixes don't trigger a release. Unpinned test requirements are not updated by Dependabot; CI always installs their latest version.
