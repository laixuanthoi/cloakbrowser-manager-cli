# T01: Project Scaffolding

## Goal
Set up the Python project structure, package configuration, and entry point.

## Deliverables

### 1. `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "cloakbrowser-manager"
version = "0.1.0"
description = "CLI/TUI manager for CloakBrowser — create, manage, and launch stealth browser profiles"
requires-python = ">=3.11"
license = {text = "MIT"}
readme = "README.md"
authors = [{name = "...", email = "..."}]
keywords = ["cloakbrowser", "browser", "antidetect", "cli", "tui"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Internet :: WWW/HTTP :: Browsers",
]

dependencies = [
    "cloakbrowser>=0.4.0",
    "click>=8.0,<9",
    "pydantic>=2.0,<3",
    "pyyaml>=6.0,<7",
    "rich>=13.0,<14",
    "textual>=2.0,<3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.5",
    "mypy>=1.10",
]

[project.scripts]
cm = "cloakbrowser_manager_cli.cli.main:cli"

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 2. Directory Structure
Create exactly this structure:
```
src/cloakbrowser_manager_cli/
├── __init__.py           # Empty, just marks package
├── __main__.py           # python -m cloakbrowser_manager_cli → forwards to cli
├── _version.py           # __version__ = "0.1.0"
├── cli/
│   ├── __init__.py       # Empty
│   ├── main.py           # Placeholder: def cli(): pass
│   ├── profile.py        # Placeholder
│   ├── launch.py         # Placeholder
│   ├── stop.py           # Placeholder
│   ├── list_cmd.py       # Placeholder (avoid shadowing builtin list)
│   ├── status.py         # Placeholder
│   ├── cdp.py            # Placeholder
│   ├── config_cmd.py     # Placeholder
│   ├── info.py           # Placeholder
│   └── tui.py            # Placeholder
├── tui/
│   ├── __init__.py       # Empty
│   ├── app.py            # Placeholder
│   ├── screens/
│   │   └── __init__.py   # Empty
│   └── widgets/
│       └── __init__.py   # Empty
├── core/
│   ├── __init__.py       # Empty
│   ├── database.py       # Placeholder
│   ├── models.py         # Placeholder
│   ├── browser_manager.py# Placeholder
│   ├── cdp_manager.py    # Placeholder
│   ├── config.py         # Placeholder
│   └── utils.py          # Placeholder
└── tests/
    ├── __init__.py       # Empty
    └── conftest.py       # Placeholder with fixtures
```

### 3. `src/cloakbrowser_manager_cli/__main__.py`
```python
"""Allow running as: python -m cloakbrowser_manager_cli"""
from cloakbrowser_manager_cli.cli.main import cli

if __name__ == "__main__":
    cli()
```

### 4. `src/cloakbrowser_manager_cli/_version.py`
```python
__version__ = "0.1.0"
```

### 5. `src/cloakbrowser_manager_cli/cli/main.py` (placeholder)
```python
"""CLI entry point — Click group."""
import click

@click.group()
@click.version_option(version="0.1.0", prog_name="cloakbrowser-manager")
def cli():
    """CloakBrowser Manager — CLI/TUI for managing stealth browser profiles."""
    pass

if __name__ == "__main__":
    cli()
```

### 6. `src/cloakbrowser_manager_cli/tests/conftest.py`
```python
"""Shared test fixtures."""
import tempfile
from pathlib import Path
import pytest

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)
```

### 7. `.gitignore`
```
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.env
.venv/
.ruff_cache/
.mypy_cache/
.pytest_cache/
*.db
*.log
```

## Verification
After creation, run from project root:
```bash
pip install -e ".[dev]"
cm --help          # Should show Click help
cm --version       # Should print version
python -m cloakbrowser_manager_cli --help
ruff check src/    # Should pass
```

## Notes
- All `.py` files under `cli/`, `tui/`, `core/` are minimal placeholders.
- `__init__.py` files are empty — they just make the dirs packages.
- The real implementations come in T02-T17.
- Package must be pip-installable with `pip install -e .` from project root.
