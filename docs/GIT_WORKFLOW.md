# Git & GitHub workflow

Goal: nobody pushes straight to `main`; every change is a small branch, a pull request, a review, and a green pipeline.

## Branches
| Branch | Purpose |
|---|---|
| `main` | Always deployable. Protected. Jenkins builds and deploys from it. |
| `feature/<short-name>` | New work, e.g. `feature/ansible-roles`, `feature/zap-stage` |
| `fix/<short-name>` | Bug fixes |
| `docs/<short-name>` | Documentation only |

## Day-to-day
```bash
git checkout main && git pull
git checkout -b feature/grafana-dashboard
# ...edit, then commit in small steps...
git add -A && git commit -m "Add deployment duration panel to Grafana dashboard"
git push -u origin feature/grafana-dashboard
# open a Pull Request on GitHub, request a review, merge (squash) when approved and green
```

## Commit messages
Imperative, specific, under ~70 characters: `Add ZAP API scan stage`, not `fixed stuff`.
Optional prefixes: `feat:`, `fix:`, `docs:`, `ci:`, `infra:`.

## Pull requests
- Small (one purpose), with the template filled in.
- At least one teammate reviews. Use "Squash and merge" so `main` history stays readable.
- Delete the branch after merging.

## One-time repository settings (needs repo admin, see SETUP_GUIDE Part 2)
Settings > Branches > Add rule for `main`: require a pull request, require 1 approval,
require review from Code Owners, disallow force-pushes.
