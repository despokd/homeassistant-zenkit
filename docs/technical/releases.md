# Releases

Releases are automated with [release-please](https://github.com/googleapis/release-please) (`.github/workflows/release.yaml`).

1. Every push to `main` creates or updates a Release PR. It bumps `version` in `custom_components/zenkit/manifest.json`, `.release-please-manifest.json` and adds the new commits to `CHANGELOG.md`.
2. Merging the Release PR creates the tag `vX.Y.Z` and a GitHub Release with the changelog section as release notes. HACS picks up the release.

The version bump follows the [Conventional Commits](https://www.conventionalcommits.org/) types since the last release:

| Commit | Bump |
| --- | --- |
| `fix:`, `perf:` | patch |
| `feat:` | minor |
| `feat!:` or `BREAKING CHANGE:` footer | major |
| `docs:`, `chore:`, `test:`, `ci:`, … | none, not in the changelog |

A squash merge uses the PR title as commit message, or the commit message for single-commit PRs. `.github/workflows/pr-title.yaml` checks that both follow Conventional Commits.

Don't bump the version in `manifest.json` by hand.

CI does not run on the Release PR, because PRs opened with the workflow's `GITHUB_TOKEN` don't trigger other workflows.

The repository setting **Settings → Actions → General → Allow GitHub Actions to create and approve pull requests** must be enabled, otherwise release-please can't open the Release PR.
