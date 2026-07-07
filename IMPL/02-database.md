# T02: Core Database Module

## Goal
SQLite database for profile persistence. CRUD operations with auto-migration.

## File
`src/cloakbrowser_manager_cli/core/database.py`

## Dependencies
- `T01` (package structure exists)
- Uses `pathlib.Path`, `sqlite3` (stdlib), `uuid`, `json`, `datetime`, `random`
- Imports from `cloakbrowser_manager_cli.core.models` (T03) — but models are simple dicts; can start without T03

## Schema

```sql
CREATE TABLE IF NOT EXISTS profiles (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    fingerprint_seed    INTEGER NOT NULL,
    proxy               TEXT,
    timezone            TEXT,
    locale              TEXT,
    platform            TEXT DEFAULT 'windows',
    user_agent          TEXT,
    screen_width        INTEGER DEFAULT 1920,
    screen_height       INTEGER DEFAULT 1080,
    gpu_vendor          TEXT,
    gpu_renderer        TEXT,
    hardware_concurrency INTEGER,
    color_scheme        TEXT,
    humanize            BOOLEAN DEFAULT 0,
    human_preset        TEXT DEFAULT 'default',
    headless            BOOLEAN DEFAULT 0,
    geoip               BOOLEAN DEFAULT 0,
    launch_args         TEXT DEFAULT '[]',      -- JSON array
    notes               TEXT,
    tags                TEXT DEFAULT '[]',      -- JSON array of {tag, color}
    license_key         TEXT,
    user_data_dir       TEXT NOT NULL,
    cdp_port            INTEGER,
    pid                 INTEGER,
    status              TEXT DEFAULT 'stopped',
    last_launched       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
```

## API Design

```python
"""SQLite database operations for browser profiles."""

from __future__ import annotations

import datetime
import json
import random
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# Data directory — resolved from config or default
def get_data_dir() -> Path:
    """Return data directory. Default: ~/.cloakbrowser-manager.
    Can be overridden by CM_DATA_DIR env var or config.
    """
    import os
    if env_dir := os.environ.get("CM_DATA_DIR"):
        return Path(env_dir)
    return Path.home() / ".cloakbrowser-manager"

def get_db_path() -> Path:
    return get_data_dir() / "profiles.db"

@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()

def init_db() -> None:
    """Create tables and run migrations. Idempotent."""
    get_db_path().parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                fingerprint_seed INTEGER NOT NULL,
                proxy TEXT,
                timezone TEXT,
                locale TEXT,
                platform TEXT DEFAULT 'windows',
                user_agent TEXT,
                screen_width INTEGER DEFAULT 1920,
                screen_height INTEGER DEFAULT 1080,
                gpu_vendor TEXT,
                gpu_renderer TEXT,
                hardware_concurrency INTEGER,
                color_scheme TEXT,
                humanize BOOLEAN DEFAULT 0,
                human_preset TEXT DEFAULT 'default',
                headless BOOLEAN DEFAULT 0,
                geoip BOOLEAN DEFAULT 0,
                launch_args TEXT DEFAULT '[]',
                notes TEXT,
                tags TEXT DEFAULT '[]',
                license_key TEXT,
                user_data_dir TEXT NOT NULL,
                cdp_port INTEGER,
                pid INTEGER,
                status TEXT DEFAULT 'stopped',
                last_launched TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        conn.commit()
        # Run migrations (add columns that may be missing)
        _run_migrations(conn)

def _run_migrations(conn: sqlite3.Connection) -> None:
    """Add missing columns for schema upgrades."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()}
    migrations = {
        "color_scheme": "ALTER TABLE profiles ADD COLUMN color_scheme TEXT",
        "launch_args": "ALTER TABLE profiles ADD COLUMN launch_args TEXT DEFAULT '[]'",
        "notes": "ALTER TABLE profiles ADD COLUMN notes TEXT",
        "tags": "ALTER TABLE profiles ADD COLUMN tags TEXT DEFAULT '[]'",
        "license_key": "ALTER TABLE profiles ADD COLUMN license_key TEXT",
        "cdp_port": "ALTER TABLE profiles ADD COLUMN cdp_port INTEGER",
        "pid": "ALTER TABLE profiles ADD COLUMN pid INTEGER",
        "status": "ALTER TABLE profiles ADD COLUMN status TEXT DEFAULT 'stopped'",
        "last_launched": "ALTER TABLE profiles ADD COLUMN last_launched TEXT",
    }
    for col, sql in migrations.items():
        if col not in cols:
            conn.execute(sql)
    conn.commit()

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def _serialize_tags(tags: list[dict] | list[str]) -> str:
    """Normalize tags to JSON string. Accepts list of dicts or strings."""
    result = []
    for t in tags:
        if isinstance(t, dict):
            result.append(t)
        else:
            result.append({"tag": str(t), "color": None})
    return json.dumps(result)

def _deserialize_tags(raw: str) -> list[dict]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

def _deserialize_launch_args(raw: str) -> list[str]:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a DB row to a dict with deserialized JSON fields."""
    d = dict(row)
    d["tags"] = _deserialize_tags(d.get("tags", "[]"))
    d["launch_args"] = _deserialize_launch_args(d.get("launch_args", "[]"))
    d["humanize"] = bool(d.get("humanize", False))
    d["headless"] = bool(d.get("headless", False))
    d["geoip"] = bool(d.get("geoip", False))
    return d

def create_profile(name: str, fingerprint_seed: int | None = None, **fields: Any) -> dict[str, Any]:
    profile_id = str(uuid.uuid4())
    seed = fingerprint_seed if fingerprint_seed is not None else random.randint(10000, 99999)
    user_data_dir = str(get_data_dir() / "profiles" / profile_id)
    now = _now()

    tags_raw = _serialize_tags(fields.pop("tags", []) or [])
    launch_args_raw = json.dumps(fields.pop("launch_args", []) or [])

    with get_db() as conn:
        conn.execute("""INSERT INTO profiles (
            id, name, fingerprint_seed, proxy, timezone, locale, platform,
            user_agent, screen_width, screen_height, gpu_vendor, gpu_renderer,
            hardware_concurrency, color_scheme, humanize, human_preset, headless,
            geoip, launch_args, notes, tags, license_key, user_data_dir, status,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            profile_id, name, seed,
            fields.get("proxy"), fields.get("timezone"), fields.get("locale"),
            fields.get("platform", "windows"), fields.get("user_agent"),
            fields.get("screen_width", 1920), fields.get("screen_height", 1080),
            fields.get("gpu_vendor"), fields.get("gpu_renderer"),
            fields.get("hardware_concurrency"), fields.get("color_scheme"),
            int(fields.get("humanize", False)), fields.get("human_preset", "default"),
            int(fields.get("headless", False)), int(fields.get("geoip", False)),
            launch_args_raw, fields.get("notes"), tags_raw,
            fields.get("license_key"), user_data_dir, "stopped", now, now,
        ))
        conn.commit()
    return get_profile(profile_id)

def get_profile(profile_id: str) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not row:
            return None
        return _row_to_dict(row)

def find_profile(identifier: str) -> dict[str, Any] | None:
    """Find by exact ID or unique name prefix."""
    with get_db() as conn:
        # Try exact ID first
        row = conn.execute("SELECT * FROM profiles WHERE id = ?", (identifier,)).fetchone()
        if row:
            return _row_to_dict(row)
        # Try ID prefix
        rows = conn.execute(
            "SELECT * FROM profiles WHERE id LIKE ?", (f"{identifier}%",)
        ).fetchall()
        if len(rows) == 1:
            return _row_to_dict(rows[0])
        # Try exact name
        row = conn.execute("SELECT * FROM profiles WHERE name = ?", (identifier,)).fetchone()
        if row:
            return _row_to_dict(row)
    return None

def list_profiles(
    status: str | None = None,
    tag: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List profiles with optional filters."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
        profiles = [_row_to_dict(r) for r in rows]
    if status:
        profiles = [p for p in profiles if p.get("status") == status]
    if tag:
        profiles = [p for p in profiles if any(t["tag"] == tag for t in p.get("tags", []))]
    if search:
        q = search.lower()
        profiles = [
            p for p in profiles
            if q in p.get("name", "").lower()
            or q in str(p.get("notes", "")).lower()
            or q in p.get("id", "").lower()
            or any(q in t["tag"].lower() for t in p.get("tags", []))
        ]
    return profiles

def update_profile(profile_id: str, **fields: Any) -> dict[str, Any] | None:
    existing = get_profile(profile_id)
    if not existing:
        return None

    updatable = (
        "name", "fingerprint_seed", "proxy", "timezone", "locale", "platform",
        "user_agent", "screen_width", "screen_height", "gpu_vendor", "gpu_renderer",
        "hardware_concurrency", "color_scheme", "humanize", "human_preset", "headless",
        "geoip", "notes", "license_key", "status", "cdp_port", "pid", "last_launched",
    )

    set_clauses = []
    values = []
    for col in updatable:
        if col in fields:
            val = fields[col]
            if col in ("humanize", "headless", "geoip"):
                val = int(val)
            set_clauses.append(f"{col} = ?")
            values.append(val)

    # Handle special JSON fields
    if "launch_args" in fields:
        set_clauses.append("launch_args = ?")
        values.append(json.dumps(fields["launch_args"] or []))
    if "tags" in fields:
        set_clauses.append("tags = ?")
        values.append(_serialize_tags(fields["tags"] or []))

    if set_clauses:
        set_clauses.append("updated_at = ?")
        values.append(_now())
        values.append(profile_id)
        with get_db() as conn:
            conn.execute(
                f"UPDATE profiles SET {', '.join(set_clauses)} WHERE id = ?",
                values,
            )
            conn.commit()

    return get_profile(profile_id)

def delete_profile(profile_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0

def get_running_profiles() -> list[dict[str, Any]]:
    return list_profiles(status="running")

def count_by_status() -> dict[str, int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM profiles GROUP BY status"
        ).fetchall()
    return {r["status"]: r["cnt"] for r in rows}
```

## Tests

Create `tests/test_database.py`:
```python
import pytest
from cloakbrowser_manager_cli.core.database import (
    init_db, create_profile, get_profile, find_profile,
    list_profiles, update_profile, delete_profile, get_db_path,
)

# Use a fixture that points to a temp DB
@pytest.fixture(autouse=True)
def setup_temp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "profiles.db"
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_db_path",
        lambda: db_path,
    )
    monkeypatch.setattr(
        "cloakbrowser_manager_cli.core.database.get_data_dir",
        lambda: tmp_path,
    )
    init_db()

def test_create_and_get():
    p = create_profile("test", platform="linux")
    assert p["name"] == "test"
    assert p["platform"] == "linux"
    assert p["status"] == "stopped"
    assert len(p["id"]) == 36  # UUID

    p2 = get_profile(p["id"])
    assert p2 is not None
    assert p2["name"] == "test"

def test_find_by_id_prefix():
    p = create_profile("my-profile")
    assert find_profile(p["id"][:4]) is not None

def test_find_by_name():
    p = create_profile("unique-name")
    assert find_profile("unique-name") is not None

def test_list_filter_by_status():
    create_profile("a", proxy="http://p:8080")
    running = list_profiles(status="running")
    assert len(running) == 0

def test_list_filter_by_tag():
    create_profile("tagged", tags=[{"tag": "gmail", "color": "red"}])
    results = list_profiles(tag="gmail")
    assert len(results) == 1

def test_update():
    p = create_profile("to-update")
    updated = update_profile(p["id"], name="updated", proxy="http://new:9090")
    assert updated["name"] == "updated"
    assert updated["proxy"] == "http://new:9090"

def test_update_tags():
    p = create_profile("tag-test", tags=[{"tag": "old"}])
    updated = update_profile(p["id"], tags=[{"tag": "new", "color": "blue"}])
    assert len(updated["tags"]) == 1
    assert updated["tags"][0]["tag"] == "new"
    assert updated["tags"][0]["color"] == "blue"

def test_delete():
    p = create_profile("to-delete")
    assert delete_profile(p["id"]) is True
    assert get_profile(p["id"]) is None

def test_fingerprint_seed_auto():
    p = create_profile("auto-seed")
    assert 10000 <= p["fingerprint_seed"] <= 99999

def test_fingerprint_seed_explicit():
    p = create_profile("explicit-seed", fingerprint_seed=12345)
    assert p["fingerprint_seed"] == 12345

def test_count_by_status():
    create_profile("s1")
    create_profile("s2")
    counts = count_by_status()
    assert counts.get("stopped", 0) >= 2
```

## Verification
```bash
pytest tests/test_database.py -v
```

## Notes
- `tags` stored as JSON array of `{tag: str, color: str|None}` dicts.
- `launch_args` stored as JSON array of strings.
- `find_profile()` supports ID, ID prefix (unique match only), and exact name.
- All booleans stored as INTEGER (0/1), deserialized to Python bool.
- WAL mode for concurrent read safety.
