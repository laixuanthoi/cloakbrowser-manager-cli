# AGENTS.md

Guidance for AI coding agents working on this repository.

## Project overview

`cloakbrowser-manager` is a native Python CLI/TUI package for managing CloakBrowser profiles without Docker or VNC.

- Package import name: `cloakbrowser_manager_cli`
- PyPI/package name: `cloakbrowser-manager`
- Console command: `cm`
- Main CLI entry: `src/cloakbrowser_manager_cli/cli/main.py`
- TUI entry: `src/cloakbrowser_manager_cli/tui/app.py`
- REST API app: `src/cloakbrowser_manager_cli/api/app.py`

## Important constraints

- Keep browser execution native: no Docker, no VNC/noVNC.
- CDP ports are allocated automatically by `CDPManager` from the configured range.
- Do not expose secrets in API/CLI output. Redact proxy credentials and license keys.
- Never delete arbitrary paths from restored/malicious DB data. Use safe profile-data deletion helpers.
- REST API must use local browser/CDP URLs, not a VNC proxy layer.
- TUI should remain usable on Windows Terminal/Git Bash/PowerShell.

## Common commands

```bash
# Run tests
python -m pytest tests/ -q

# Run CLI from source
python -m cloakbrowser_manager_cli --help
python -m cloakbrowser_manager_cli tui

# Build wheel
python -m build --wheel

# Install editable dev package
pip install -e ".[dev]"
```

## Packaging notes

- `pyproject.toml` defines the package metadata and console script.
- `tui/styles.css` is package data and must stay included in `pyproject.toml`.
- After install, users should be able to run:

```bash
cm --help
cm tui
```

## Code structure

```txt
src/cloakbrowser_manager_cli/
  api/      FastAPI REST API routes/schemas/auth
  cli/      Click command groups
  core/     DB/config/models/browser/CDP utilities
  tui/      Textual app, screens, widgets, styles

tests/      pytest suite
docs/       spec, plans, progress, implementation notes
```

## Testing expectations

Before finishing code changes, run:

```bash
python -m pytest tests/ -q
```

For packaging changes, also run:

```bash
rm -rf build dist src/*.egg-info
python -m build --wheel
```

## Style guidance

- Prefer small, focused changes.
- Use existing Click/Rich/Textual patterns.
- Keep JSON/YAML output machine-readable when commands use `ctx.output`.
- Keep TUI modals centered using shared `#modal` styling.
- Add regression tests for audit/security fixes.

## Documentation

- Root `README.md` is user-facing.
- `docs/README.md` indexes project internals.
- Planning and implementation documents belong under `docs/`, not repo root.
