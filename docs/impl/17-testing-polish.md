# T17: Testing, Packaging & CI/CD

## Goal
Comprehensive tests, PyPI packaging, GitHub Actions CI, and documentation.

## Files to Create/Update
- `tests/` — test suite
- `README.md` — user-facing documentation
- `.github/workflows/ci.yml` — CI pipeline
- `pyproject.toml` — final packaging config (update from T01)

---

## 1. Test Suite

### `tests/conftest.py` — shared fixtures

```python
"""Shared test fixtures for cloakbrowser-manager tests."""

import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def temp_data_dir(monkeypatch) -> Path:
    """Create a temporary data directory and redirect all DB/config operations to it."""
    import os
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setenv("CM_DATA_DIR", str(tmp))

    # Patch core.database.get_data_dir
    import cloakbrowser_manager_cli.core.database as database_mod
    monkeypatch.setattr(database_mod, "get_data_dir", lambda: tmp)

    # Patch core.config.get_data_dir
    import cloakbrowser_manager_cli.core.config as config_mod

    def _mock_config_path():
        return tmp / "config.yaml"

    monkeypatch.setattr(config_mod, "_config_path", _mock_config_path)
    monkeypatch.setattr(config_mod, "get_data_dir", lambda: tmp / "data")

    # Ensure directories
    (tmp / "data" / "profiles").mkdir(parents=True, exist_ok=True)
    (tmp / "data").mkdir(parents=True, exist_ok=True)

    return tmp


@pytest.fixture(autouse=True)
def setup_db(temp_data_dir):
    """Initialize DB before each test."""
    from cloakbrowser_manager_cli.core import database as db
    from cloakbrowser_manager_cli.core import config as cfg
    cfg.ensure_directories()
    db.init_db()
```

### `tests/test_cli.py` — CLI integration tests

```python
"""Integration tests for CLI commands using Click's CliRunner."""

import pytest
from click.testing import CliRunner
from cloakbrowser_manager_cli.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "profile" in result.output
    assert "launch" in result.output
    assert "tui" in result.output


def test_version(runner):
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_profile_create(runner):
    result = runner.invoke(cli, ["profile", "create", "test-cli-1"])
    assert result.exit_code == 0
    assert "test-cli-1" in result.output


def test_profile_create_with_options(runner):
    result = runner.invoke(cli, [
        "profile", "create", "full-profile",
        "--proxy", "http://proxy:8080",
        "--platform", "linux",
        "--humanize",
        "--tag", "gmail",
        "--tag", "work",
        "--notes", "test notes",
    ])
    assert result.exit_code == 0


def test_profile_list(runner):
    runner.invoke(cli, ["profile", "create", "p1"])
    runner.invoke(cli, ["profile", "create", "p2"])
    result = runner.invoke(cli, ["profile", "list"])
    assert result.exit_code == 0
    assert "p1" in result.output
    assert "p2" in result.output


def test_profile_list_json(runner):
    runner.invoke(cli, ["profile", "create", "json-test"])
    result = runner.invoke(cli, ["--json", "profile", "list"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert any(p["name"] == "json-test" for p in data)


def test_profile_show(runner):
    result = runner.invoke(cli, ["profile", "create", "show-test"])
    # Extract ID from output or use profile list
    list_result = runner.invoke(cli, ["--json", "profile", "list"])
    import json
    profiles = json.loads(list_result.output)
    profile_id = [p for p in profiles if p["name"] == "show-test"][0]["id"]

    result = runner.invoke(cli, ["profile", "show", profile_id[:8]])
    assert result.exit_code == 0
    assert "show-test" in result.output


def test_profile_edit(runner):
    runner.invoke(cli, ["profile", "create", "edit-test"])
    result = runner.invoke(cli, ["profile", "edit", "edit-test", "--notes", "updated notes"])
    assert result.exit_code == 0


def test_profile_clone(runner):
    runner.invoke(cli, ["profile", "create", "clone-src"])
    result = runner.invoke(cli, ["profile", "clone", "clone-src", "--name", "clone-dst"])
    assert result.exit_code == 0
    assert "clone-dst" in result.output


def test_profile_delete(runner):
    runner.invoke(cli, ["profile", "create", "delete-test"])
    result = runner.invoke(cli, ["profile", "delete", "delete-test", "--force"])
    assert result.exit_code == 0


def test_list_command(runner):
    runner.invoke(cli, ["profile", "create", "list-test"])
    result = runner.invoke(cli, ["list"])
    assert result.exit_code == 0
    assert "list-test" in result.output


def test_status_command(runner):
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0
    assert "profiles" in result.output.lower()


def test_config_show(runner):
    result = runner.invoke(cli, ["config", "show"])
    assert result.exit_code == 0


def test_config_set(runner):
    result = runner.invoke(cli, ["config", "set", "--log-level", "debug"])
    assert result.exit_code == 0


def test_info(runner):
    result = runner.invoke(cli, ["info"])
    assert result.exit_code == 0


def test_info_json(runner):
    result = runner.invoke(cli, ["--json", "info"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output)
    assert "os" in data
    assert "python" in data
```

### `tests/test_integration.py` — DB + Browser Manager integration

```python
"""Integration tests combining DB and Browser Manager."""

import pytest
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import BrowserManager


def test_create_and_launch_flow():
    """End-to-end flow: create profile → verify in DB → check launch readiness."""
    # Create
    p = db.create_profile("integration-test", platform="linux")
    assert p["status"] == "stopped"
    assert p["id"]

    # Verify retrieval
    p2 = db.get_profile(p["id"])
    assert p2["name"] == "integration-test"

    # Verify find
    p3 = db.find_profile("integration-test")
    assert p3 is not None

    # Verify list includes it
    profiles = db.list_profiles()
    assert any(pr["name"] == "integration-test" for pr in profiles)

    # Manager validation (without actually launching)
    mgr = BrowserManager()
    status = mgr.get_status(p["id"])
    assert status["status"] == "stopped"
    assert status["cdp_port"] is None

    # Cleanup
    db.delete_profile(p["id"])


def test_multiple_profiles():
    for i in range(5):
        db.create_profile(f"multi-{i}", tags=[{"tag": f"group-{i%2}"}])

    all_profiles = db.list_profiles()
    assert len(all_profiles) >= 5

    # Filter by tag
    group0 = db.list_profiles(tag="group-0")
    assert len(group0) >= 2

    # Filter by search
    found = db.list_profiles(search="multi-1")
    assert len(found) == 1


def test_update_workflow():
    p = db.create_profile("update-flow")

    # Update multiple fields
    updated = db.update_profile(
        p["id"],
        name="updated-flow",
        proxy="http://new:9090",
        humanize=True,
    )
    assert updated["name"] == "updated-flow"
    assert updated["proxy"] == "http://new:9090"
    assert updated["humanize"] is True

    # Verify tag update
    db.update_profile(p["id"], tags=[{"tag": "new-tag", "color": "blue"}])
    p3 = db.get_profile(p["id"])
    assert len(p3["tags"]) == 1
    assert p3["tags"][0]["tag"] == "new-tag"

    db.delete_profile(p["id"])
```

## 2. README.md

```markdown
# CloakBrowser Manager — CLI/TUI

Native CLI and TUI tool for managing [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) profiles — create, launch, and manage isolated stealth browser instances with unique fingerprints.

## Features

- **CLI-first**: Every operation via terminal commands
- **TUI dashboard**: Interactive terminal UI (like htop for browsers)
- **Native windows**: Browsers open as real OS windows — no Docker, no VNC
- **Profile management**: Create/edit/delete profiles with custom fingerprints
- **Session persistence**: Cookies, localStorage survive restarts
- **CDP automation**: Each profile exposes a Chrome DevTools Protocol port
- **Code generation**: Auto-generate Playwright/Puppeteer connection code
- **Cross-platform**: Windows, macOS, Linux

## Install

```bash
pip install cloakbrowser-manager
```

Requires Python 3.11+ and [CloakBrowser](https://pypi.org/project/cloakbrowser/).

## Quick Start

```bash
# Create your first profile
cm profile create my-profile --proxy http://proxy:8080 --humanize

# Launch it
cm launch my-profile

# See what's running
cm status

# Open the TUI dashboard
cm tui

# Connect via Playwright
cm cdp code my-profile --lang python
```

## Commands

| Command | Description |
|---|---|
| `cm profile create <name>` | Create a new browser profile |
| `cm profile list` | List all profiles |
| `cm profile show <id>` | Show profile details |
| `cm profile edit <id>` | Edit profile settings |
| `cm profile delete <id>` | Delete a profile |
| `cm profile clone <id>` | Clone a profile's settings |
| `cm launch <id> [<id>...]` | Launch one or more profiles |
| `cm stop <id> [<id>...]` | Stop running profiles |
| `cm stop --all` | Stop all running profiles |
| `cm list` | Compact profile list |
| `cm status` | System status overview |
| `cm status --watch` | Live status refresh |
| `cm cdp list` | List CDP endpoints |
| `cm cdp url <id>` | Get CDP URL for a profile |
| `cm cdp code <id>` | Generate connection code |
| `cm cdp check <id>` | Check CDP health |
| `cm tui` | Launch TUI dashboard |
| `cm config show` | Show configuration |
| `cm config set` | Update configuration |
| `cm info` | System diagnostics |

## Data

All data is stored in `~/.cloakbrowser-manager/`:
- `profiles.db` — SQLite database of profiles
- `profiles/<id>/` — per-profile CloakBrowser user data (cookies, sessions, cache)
- `config.yaml` — global configuration

## License

MIT
```

## 3. CI/CD (`.github/workflows/ci.yml`)

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ["3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest tests/ -v --tb=short

      - name: Lint with ruff
        run: |
          ruff check src/

      - name: Type check with mypy
        run: |
          mypy src/cloakbrowser_manager_cli/
```

## Notes
- CLI tests use Click's `CliRunner` — no actual browser launches needed.
- Integration tests focus on DB + model layer; browser tests require CloakBrowser binary.
- CI matrix covers all 3 OS and Python 3.11-3.13.
- `ruff` for linting, `mypy` for type checking.
- Tests use `monkeypatch` to redirect data directories to temp dirs — no pollution.

## Verification
```bash
pytest tests/ -v
ruff check src/
mypy src/cloakbrowser_manager_cli/
```
