"""Shared test fixtures for cloakbrowser-manager tests."""

import tempfile
from pathlib import Path
import os
import pytest


@pytest.fixture
def temp_data_dir(monkeypatch) -> Path:
    """Create a temporary data directory and redirect all DB/config operations to it.

    This fixture monkeypatches at the module level so that both core modules
    and CLI commands use the same temporary directory. Each test gets a fresh
    directory, preventing cross-test contamination.
    """
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setenv("CM_DATA_DIR", str(tmp))

    # Patch core.database.get_data_dir
    import cloakbrowser_manager_cli.core.database as database_mod
    monkeypatch.setattr(database_mod, "get_data_dir", lambda: tmp)

    # Patch core.config — both _config_path and get_data_dir
    import cloakbrowser_manager_cli.core.config as config_mod

    def _mock_config_path():
        return tmp / "config.yaml"

    monkeypatch.setattr(config_mod, "_config_path", _mock_config_path)
    monkeypatch.setattr(config_mod, "get_data_dir", lambda: tmp)

    # Ensure directory structure
    data_dir = tmp / "profiles"
    data_dir.mkdir(parents=True, exist_ok=True)

    return tmp


@pytest.fixture(autouse=True)
def setup_db(temp_data_dir):
    """Initialize DB and config directories before each test.

    Runs automatically for all tests. Creates the SQLite database
    and runs migrations in the temporary data directory.
    """
    from cloakbrowser_manager_cli.core import database as db
    db.init_db()
