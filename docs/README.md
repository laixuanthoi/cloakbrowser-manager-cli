# CloakBrowser Manager Documentation

This directory contains project planning, implementation notes, and technical reference docs for CloakBrowser Manager.

## Core docs

- [SPEC.md](SPEC.md) — product and technical specification.
- [PLAN.md](PLAN.md) — original implementation plan.
- [PROGRESS.md](PROGRESS.md) — project progress log.
- [PLAN_ADVANCED_STEALTH.md](PLAN_ADVANCED_STEALTH.md) — advanced fingerprint/stealth feature plan.
- [PLAN_REST_API.md](PLAN_REST_API.md) — REST API server plan.

## Implementation notes

Detailed implementation slices live in [impl/](impl/):

1. [Scaffolding](impl/01-scaffolding.md)
2. [Database](impl/02-database.md)
3. [Models](impl/03-models.md)
4. [Config](impl/04-config.md)
5. [Browser Manager](impl/05-browser-manager.md)
6. [CDP Manager](impl/06-cdp-manager.md)
7. [Utilities](impl/07-utils.md)
8. [CLI Main](impl/08-cli-main.md)
9. [CLI Profile](impl/09-cli-profile.md)
10. [CLI Launch/Stop](impl/10-cli-launch-stop.md)
11. [CLI List/Status](impl/11-cli-list-status.md)
12. [CLI CDP](impl/12-cli-cdp.md)
13. [CLI Config/Info](impl/13-cli-config-info.md)
14. [TUI App](impl/14-tui-app.md)
15. [TUI Widgets](impl/15-tui-widgets.md)
16. [TUI Screens](impl/16-tui-screens.md)
17. [Testing & Polish](impl/17-testing-polish.md)

## Useful commands

```bash
python -m pytest tests/ -q
python -m build --wheel
python -m cloakbrowser_manager_cli --help
cm tui
```
