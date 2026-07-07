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


# ── Path Helpers ──────────────────────────────────────────────────────────────

def get_data_dir() -> Path:
    """Return data directory. Checks (in order): CM_DATA_DIR env var, config.yaml, platform default."""
    import os
    if env_dir := os.environ.get("CM_DATA_DIR"):
        return Path(env_dir)
    # Respect config.yaml if present
    try:
        from cloakbrowser_manager_cli.core.config import load_config
        cfg = load_config()
        if cfg.data_dir:
            return Path(cfg.data_dir).expanduser().resolve()
    except Exception:
        pass
    return Path.home() / ".cloakbrowser-manager"


def get_db_path() -> Path:
    """Return the path to the SQLite database file."""
    return get_data_dir() / "profiles.db"


# ── Connection Management ────────────────────────────────────────────────────

@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    """Get a SQLite connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


# ── Schema & Migrations ──────────────────────────────────────────────────────

def init_db() -> None:
    """Create tables and run migrations. Idempotent."""
    get_db_path().parent.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript("""
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
                launch_args         TEXT DEFAULT '[]',
                extension_paths     TEXT DEFAULT '[]',
                browser_version     TEXT,
                stealth_args        BOOLEAN DEFAULT 1,
                device_memory       INTEGER,
                brand               TEXT,
                brand_version       TEXT,
                platform_version    TEXT,
                location            TEXT,
                storage_quota       INTEGER,
                taskbar_height      INTEGER,
                fonts_dir           TEXT,
                windows_font_metrics BOOLEAN DEFAULT 0,
                webrtc_ip           TEXT,
                fingerprint_noise   BOOLEAN,
                fingerprint_mode    TEXT DEFAULT 'normal',
                allow_3p_cookies    BOOLEAN DEFAULT 0,
                license_through_proxy BOOLEAN DEFAULT 0,
                widevine_enabled    BOOLEAN DEFAULT 0,
                notes               TEXT,
                tags                TEXT DEFAULT '[]',
                license_key         TEXT,
                auto_launch         BOOLEAN DEFAULT 0,
                user_data_dir       TEXT NOT NULL,
                cdp_port            INTEGER,
                pid                 INTEGER,
                status              TEXT DEFAULT 'stopped',
                last_launched       TEXT,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            );
        """)
        conn.commit()
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
        "auto_launch": "ALTER TABLE profiles ADD COLUMN auto_launch BOOLEAN DEFAULT 0",
        "extension_paths": "ALTER TABLE profiles ADD COLUMN extension_paths TEXT DEFAULT '[]'",
        "browser_version": "ALTER TABLE profiles ADD COLUMN browser_version TEXT",
        "stealth_args": "ALTER TABLE profiles ADD COLUMN stealth_args BOOLEAN DEFAULT 1",
        "device_memory": "ALTER TABLE profiles ADD COLUMN device_memory INTEGER",
        "brand": "ALTER TABLE profiles ADD COLUMN brand TEXT",
        "brand_version": "ALTER TABLE profiles ADD COLUMN brand_version TEXT",
        "platform_version": "ALTER TABLE profiles ADD COLUMN platform_version TEXT",
        "location": "ALTER TABLE profiles ADD COLUMN location TEXT",
        "storage_quota": "ALTER TABLE profiles ADD COLUMN storage_quota INTEGER",
        "taskbar_height": "ALTER TABLE profiles ADD COLUMN taskbar_height INTEGER",
        "fonts_dir": "ALTER TABLE profiles ADD COLUMN fonts_dir TEXT",
        "windows_font_metrics": "ALTER TABLE profiles ADD COLUMN windows_font_metrics BOOLEAN DEFAULT 0",
        "webrtc_ip": "ALTER TABLE profiles ADD COLUMN webrtc_ip TEXT",
        "fingerprint_noise": "ALTER TABLE profiles ADD COLUMN fingerprint_noise BOOLEAN",
        "fingerprint_mode": "ALTER TABLE profiles ADD COLUMN fingerprint_mode TEXT DEFAULT 'normal'",
        "allow_3p_cookies": "ALTER TABLE profiles ADD COLUMN allow_3p_cookies BOOLEAN DEFAULT 0",
        "license_through_proxy": "ALTER TABLE profiles ADD COLUMN license_through_proxy BOOLEAN DEFAULT 0",
        "widevine_enabled": "ALTER TABLE profiles ADD COLUMN widevine_enabled BOOLEAN DEFAULT 0",
    }
    for col, sql in migrations.items():
        if col not in cols:
            conn.execute(sql)
    conn.commit()


# ── Serialization Helpers ────────────────────────────────────────────────────

def _now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _serialize_tags(tags: list[dict] | list[str]) -> str:
    """Normalize tags to JSON string. Accepts list of dicts or strings."""
    result: list[dict] = []
    for t in tags:
        if isinstance(t, dict):
            result.append(t)
        else:
            result.append({"tag": str(t), "color": None})
    return json.dumps(result)


def _deserialize_tags(raw: str) -> list[dict]:
    """Parse JSON tags string into list of dicts."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _deserialize_string_list(raw: str) -> list[str]:
    """Parse a JSON string list field into a list of strings."""
    try:
        parsed = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed]


def _deserialize_launch_args(raw: str) -> list[str]:
    """Parse JSON launch_args string into list of strings."""
    return _deserialize_string_list(raw)


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a DB row to a dict with deserialized JSON fields."""
    d = dict(row)
    d["tags"] = _deserialize_tags(d.get("tags", "[]"))
    d["launch_args"] = _deserialize_launch_args(d.get("launch_args", "[]"))
    d["extension_paths"] = _deserialize_string_list(d.get("extension_paths", "[]"))
    for key in (
        "humanize", "headless", "geoip", "auto_launch", "stealth_args",
        "windows_font_metrics", "allow_3p_cookies", "license_through_proxy",
        "widevine_enabled",
    ):
        d[key] = bool(d.get(key, key == "stealth_args"))
    if d.get("fingerprint_noise") is not None:
        d["fingerprint_noise"] = bool(d["fingerprint_noise"])
    d["fingerprint_mode"] = d.get("fingerprint_mode") or "normal"
    return d


# ── CRUD Operations ──────────────────────────────────────────────────────────

def create_profile(
    name: str,
    fingerprint_seed: int | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Create a new browser profile.

    Args:
        name: Display name for the profile.
        fingerprint_seed: Fixed seed (10000-99999). Random if None.
        **fields: See schema columns.

    Returns:
        The created profile as a dict.
    """
    profile_id = str(uuid.uuid4())
    seed = fingerprint_seed if fingerprint_seed is not None else random.randint(10000, 99999)
    user_data_dir = str(get_data_dir() / "profiles" / profile_id)
    now = _now()

    # Check for duplicate names
    if find_profile(name):
        raise ValueError(f"A profile named '{name}' already exists. Use a unique name.")

    tags_raw = _serialize_tags(fields.pop("tags", []) or [])
    launch_args_raw = json.dumps(fields.pop("launch_args", []) or [])
    extension_paths_raw = json.dumps(fields.pop("extension_paths", []) or [])

    with get_db() as conn:
        conn.execute(
            """INSERT INTO profiles (
                id, name, fingerprint_seed, proxy, timezone, locale, platform,
                user_agent, screen_width, screen_height, gpu_vendor, gpu_renderer,
                hardware_concurrency, color_scheme, humanize, human_preset, headless,
                geoip, launch_args, extension_paths, browser_version, stealth_args,
                device_memory, brand, brand_version, platform_version, location,
                storage_quota, taskbar_height, fonts_dir, windows_font_metrics,
                webrtc_ip, fingerprint_noise, fingerprint_mode, allow_3p_cookies,
                license_through_proxy, widevine_enabled, notes, tags, license_key,
                auto_launch, user_data_dir, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile_id,
                name,
                seed,
                fields.get("proxy"),
                fields.get("timezone"),
                fields.get("locale"),
                fields.get("platform", "windows"),
                fields.get("user_agent"),
                fields.get("screen_width", 1920),
                fields.get("screen_height", 1080),
                fields.get("gpu_vendor"),
                fields.get("gpu_renderer"),
                fields.get("hardware_concurrency"),
                fields.get("color_scheme"),
                int(fields.get("humanize", False)),
                fields.get("human_preset", "default"),
                int(fields.get("headless", False)),
                int(fields.get("geoip", False)),
                launch_args_raw,
                extension_paths_raw,
                fields.get("browser_version"),
                int(fields.get("stealth_args", True)),
                fields.get("device_memory"),
                fields.get("brand"),
                fields.get("brand_version"),
                fields.get("platform_version"),
                fields.get("location"),
                fields.get("storage_quota"),
                fields.get("taskbar_height"),
                fields.get("fonts_dir"),
                int(fields.get("windows_font_metrics", False)),
                fields.get("webrtc_ip"),
                None if fields.get("fingerprint_noise") is None else int(fields.get("fingerprint_noise")),
                fields.get("fingerprint_mode", "normal"),
                int(fields.get("allow_3p_cookies", False)),
                int(fields.get("license_through_proxy", False)),
                int(fields.get("widevine_enabled", False)),
                fields.get("notes"),
                tags_raw,
                fields.get("license_key"),
                int(fields.get("auto_launch", False)),
                user_data_dir,
                "stopped",
                now,
                now,
            ),
        )
        conn.commit()

    return get_profile(profile_id)  # type: ignore[return-value]


def get_profile(profile_id: str) -> dict[str, Any] | None:
    """Get a profile by exact ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (profile_id,)
        ).fetchone()
        if not row:
            return None
        return _row_to_dict(row)


def find_profile(identifier: str) -> dict[str, Any] | None:
    """Find a profile by ID, ID prefix (unique match), or exact name.

    Args:
        identifier: Full ID, ID prefix, or exact profile name.

    Returns:
        The profile dict if found (and unique for prefix), else None.
    """
    with get_db() as conn:
        # Try exact ID first
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = ?", (identifier,)
        ).fetchone()
        if row:
            return _row_to_dict(row)

        # Try ID prefix
        rows = conn.execute(
            "SELECT * FROM profiles WHERE id LIKE ?", (f"{identifier}%",)
        ).fetchall()
        if len(rows) == 1:
            return _row_to_dict(rows[0])

        # Try exact name
        row = conn.execute(
            "SELECT * FROM profiles WHERE name = ?", (identifier,)
        ).fetchone()
        if row:
            return _row_to_dict(row)

    return None


def list_profiles(
    status: str | None = None,
    tag: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List profiles with optional filters.

    Args:
        status: Filter by status ("running", "stopped", "launching", "error").
        tag: Filter by tag name.
        search: Free-text search across name, notes, ID, and tag names.

    Returns:
        List of profile dicts, ordered by created_at DESC.
    """
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM profiles ORDER BY created_at DESC"
        ).fetchall()
        profiles = [_row_to_dict(r) for r in rows]

    if status:
        profiles = [p for p in profiles if p.get("status") == status]
    if tag:
        profiles = [
            p for p in profiles
            if any(t["tag"] == tag for t in p.get("tags", []))
        ]
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
    """Update a profile's fields. Only provided fields are changed.

    Args:
        profile_id: Profile ID to update.
        **fields: Field names and values to update.

    Returns:
        Updated profile dict, or None if not found.
    """
    existing = get_profile(profile_id)
    if not existing:
        return None

    updatable = (
        "name", "fingerprint_seed", "proxy", "timezone", "locale", "platform",
        "user_agent", "screen_width", "screen_height", "gpu_vendor", "gpu_renderer",
        "hardware_concurrency", "color_scheme", "humanize", "human_preset", "headless",
        "geoip", "auto_launch", "browser_version", "stealth_args", "device_memory",
        "brand", "brand_version", "platform_version", "location", "storage_quota",
        "taskbar_height", "fonts_dir", "windows_font_metrics", "webrtc_ip",
        "fingerprint_noise", "fingerprint_mode", "allow_3p_cookies",
        "license_through_proxy", "widevine_enabled", "notes", "license_key", "status",
        "cdp_port", "pid", "last_launched",
    )

    set_clauses: list[str] = []
    values: list[Any] = []
    for col in updatable:
        if col in fields:
            val = fields[col]
            if col in (
                "humanize", "headless", "geoip", "auto_launch", "stealth_args",
                "windows_font_metrics", "allow_3p_cookies", "license_through_proxy",
                "widevine_enabled",
            ):
                val = int(val)
            if col == "fingerprint_noise" and val is not None:
                val = int(val)
            set_clauses.append(f"{col} = ?")
            values.append(val)

    # Handle special JSON fields
    if "launch_args" in fields:
        set_clauses.append("launch_args = ?")
        values.append(json.dumps(fields["launch_args"] or []))
    if "extension_paths" in fields:
        set_clauses.append("extension_paths = ?")
        values.append(json.dumps(fields["extension_paths"] or []))
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
    """Delete a profile from the database.

    Args:
        profile_id: Profile ID to delete.

    Returns:
        True if the profile was deleted, False if not found.
    """
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        conn.commit()
        return cursor.rowcount > 0


# ── Aggregate Queries ────────────────────────────────────────────────────────

def get_running_profiles() -> list[dict[str, Any]]:
    """Get all profiles currently marked as running."""
    return list_profiles(status="running")


def count_by_status() -> dict[str, int]:
    """Count profiles grouped by status."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM profiles GROUP BY status"
        ).fetchall()
    return {r["status"]: r["cnt"] for r in rows}
