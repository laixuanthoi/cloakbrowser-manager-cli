# SPEC: CloakBrowser Manager CLI/TUI

## Table of Contents
1. [Vision](#1-vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Data Model](#3-data-model)
4. [CLI Command Reference](#4-cli-command-reference)
5. [TUI Design](#5-tui-design)
6. [Module Design](#6-module-design)
7. [Profile Lifecycle](#7-profile-lifecycle)
8. [Browser Lifecycle (Native)](#8-browser-lifecycle-native)
9. [Automation API (CDP)](#9-automation-api-cdp)
10. [Configuration System](#10-configuration-system)
11. [Tech Stack](#11-tech-stack)
12. [Implementation Phases](#12-implementation-phases)

---

## 1. Vision

A **native CLI/TUI application** to create, manage, and launch isolated CloakBrowser profiles directly on desktop — no Docker, no web UI, no VNC.

### Core Principles
- **CLI-first**: Every operation has a CLI command. Pipe-friendly JSON/YAML output.
- **TUI for interactivity**: A terminal dashboard for browsing profiles, viewing live status, and quick actions.
- **Native windows**: Browsers open as real OS windows (headed mode) — not streamed via VNC.
- **Local SQLite**: No server, no Docker. Just a `~/.cloakbrowser-manager/` directory.
- **CDP for automation**: Every running profile exposes a CDP port for Playwright/Puppeteer.
- **Cross-platform**: Windows, macOS, Linux.

### What It Replaces
| Existing Manager (Web) | CLI/TUI Manager (This Project) |
|---|---|
| Docker container | Native process |
| Web UI (React + noVNC) | CLI + TUI (Textual/Python) |
| VNC streaming | Native OS windows |
| KasmVNC + Xvfb | Headed mode (real GPU windows) |
| FastAPI server | Direct Python CLI |
| HTTP REST API | CLI args + CDP |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    User Terminal                      │
│  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │  CLI Commands │  │  TUI Dashboard (Textual)     │  │
│  │  (click/arg)  │  │  - Profile list w/ status    │  │
│  │               │  │  - Launch/stop hotkeys       │  │
│  │  cm profile   │  │  - CDP port display          │  │
│  │  cm launch    │  │  - Live logs                 │  │
│  │  cm stop      │  │  - Quick edit                │  │
│  │  cm list      │  │                              │  │
│  │  cm cdp       │  │                              │  │
│  └──────┬───────┘  └──────────────┬───────────────┘  │
└─────────┼──────────────────────────┼─────────────────┘
          │                          │
          ▼                          ▼
┌─────────────────────────────────────────────────────┐
│              Core Engine (Python)                     │
│                                                       │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ Database │  │  Profile  │  │  Browser Manager  │  │
│  │ (SQLite) │  │  Manager  │  │  (lifecycle)      │  │
│  └──────────┘  └───────────┘  └────────┬─────────┘  │
│                                         │             │
│                          ┌──────────────┼──────┐     │
│                          │  CDP Port    │      │     │
│                          │  Allocator   │      │     │
│                          └──────────────┘      │     │
│                                                 │     │
└─────────────────────────────────────────────────┼─────┘
                                                  │
                    ┌─────────────────────────────┼─────┐
                    │     Native OS Windows        │     │
                    │                              │     │
                    │  ┌─────────────────────────┐ │     │
                    │  │  CloakBrowser Instance  │ │     │
                    │  │  (headed, real window)  │ │     │
                    │  │  CDP port: 5100+        │ │     │
                    │  │  user_data_dir: per-    │ │     │
                    │  │    profile directory    │ │     │
                    │  └─────────────────────────┘ │     │
                    │                              │     │
                    │  ┌─────────────────────────┐ │     │
                    │  │  CloakBrowser Instance  │ │     │
                    │  │  (headed, real window)  │ │     │
                    │  │  CDP port: 5101+        │ │     │
                    │  └─────────────────────────┘ │     │
                    └──────────────────────────────┘     │
                                                         │
  ┌──────────────────────────────────────────────────────┘
  │  Automation Tools (connect via CDP)
  │  - Playwright: connect_over_cdp("http://127.0.0.1:5100")
  │  - Puppeteer: connect({ browserURL: "http://127.0.0.1:5100" })
  │  - Any CDP client
  └──────────────────────────────────────────────────────
```

### Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | CloakBrowser Python SDK is first-class. Rich ecosystem for CLI/TUI. |
| **CLI framework** | Click | Battle-tested, composable commands, good help output. |
| **TUI framework** | Textual | Modern Python TUI, built-in widgets, async, cross-platform. |
| **Database** | SQLite | Zero setup, single file, proven in existing Manager. |
| **Data dir** | `~/.cloakbrowser-manager/` | Cross-platform, follows XDG-ish conventions. |
| **Browser mode** | Headed (real windows) | No VNC needed. Users see actual Chrome windows. |
| **CDP range** | 5100-5199 | Same as existing Manager. Rotating allocation. |
| **Package name** | `cloakbrowser-manager` (PyPI) | CLI entry: `cm` or `cbmanager` |

---

## 3. Data Model

### SQLite Schema

```sql
-- File: ~/.cloakbrowser-manager/profiles.db

CREATE TABLE profiles (
    id                  TEXT PRIMARY KEY,          -- UUID4
    name                TEXT NOT NULL,             -- Display name
    fingerprint_seed    INTEGER NOT NULL,          -- Random 10000-99999
    proxy               TEXT,                      -- http://user:pass@host:port or socks5://...
    timezone            TEXT,                      -- e.g. "America/New_York"
    locale              TEXT,                      -- e.g. "en-US"
    platform            TEXT DEFAULT 'windows',    -- windows | macos | linux
    user_agent          TEXT,                      -- Custom UA or null (auto)
    screen_width        INTEGER DEFAULT 1920,
    screen_height       INTEGER DEFAULT 1080,
    gpu_vendor          TEXT,                      -- e.g. "NVIDIA Corporation"
    gpu_renderer        TEXT,                      -- e.g. "RTX 4090"
    hardware_concurrency INTEGER,                  -- null = auto
    color_scheme        TEXT,                      -- light | dark | no-preference | null
    humanize            BOOLEAN DEFAULT 0,         -- Human-like mouse/keyboard
    human_preset        TEXT DEFAULT 'default',    -- default | careful
    headless            BOOLEAN DEFAULT 0,         -- Headless mode (rare, mostly headed)
    geoip               BOOLEAN DEFAULT 0,         -- Auto-detect tz/locale from proxy IP
    launch_args         TEXT DEFAULT '[]',         -- JSON array of extra Chromium flags
    notes               TEXT,                      -- Free-form notes
    tags                TEXT DEFAULT '[]',         -- JSON array of tag strings
    license_key         TEXT,                      -- Optional Pro license for this profile
    user_data_dir       TEXT NOT NULL,             -- ~/.cloakbrowser-manager/profiles/<id>/
    cdp_port            INTEGER,                   -- Assigned CDP port (null when stopped)
    pid                 INTEGER,                   -- OS process ID (null when stopped)
    status              TEXT DEFAULT 'stopped',    -- stopped | running | launching | error
    last_launched       TEXT,                      -- ISO timestamp
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
```

### Python Models (Pydantic)

```python
class ProfileCreate(BaseModel):
    name: str
    fingerprint_seed: int | None = None
    proxy: str | None = None
    timezone: str | None = None
    locale: str | None = None
    platform: Literal["windows", "macos", "linux"] = "windows"
    user_agent: str | None = None
    screen_width: int = 1920
    screen_height: int = 1080
    gpu_vendor: str | None = None
    gpu_renderer: str | None = None
    hardware_concurrency: int | None = None
    color_scheme: Literal["light", "dark", "no-preference"] | None = None
    humanize: bool = False
    human_preset: Literal["default", "careful"] = "default"
    headless: bool = False
    geoip: bool = False
    launch_args: list[str] = []
    notes: str | None = None
    tags: list[str] = []
    license_key: str | None = None

class Profile(ProfileCreate):
    id: str
    user_data_dir: str
    cdp_port: int | None = None
    pid: int | None = None
    status: Literal["stopped", "running", "launching", "error"] = "stopped"
    last_launched: str | None = None
    created_at: str
    updated_at: str
```

---

## 4. CLI Command Reference

### Entry Point: `cm`

```bash
cm --help
# CloakBrowser Manager — CLI/TUI for managing stealth browser profiles
#
# Usage: cm [OPTIONS] COMMAND [ARGS]...
#
# Options:
#   --data-dir PATH     Override data directory (default: ~/.cloakbrowser-manager)
#   --json              Output as JSON
#   --yaml              Output as YAML
#   --verbose, -v       Verbose output
#   --version           Show version
#
# Commands:
#   profile    Manage browser profiles
#   launch     Launch a profile
#   stop       Stop a running profile
#   list       List all profiles
#   status     Show status of profiles
#   cdp        Show/manage CDP endpoints
#   tui        Launch interactive TUI dashboard
#   config     Manage global configuration
#   info       System diagnostics
```

### 4.1 `cm profile` — CRUD

```bash
# Create a profile
cm profile create my-profile \
    --platform windows \
    --proxy "http://user:pass@gate.example.com:8080" \
    --timezone "America/New_York" \
    --locale "en-US" \
    --humanize \
    --tags "gmail,us-east"
# Output:
# Created profile "my-profile" (id: a1b2c3d4)
#   fingerprint_seed: 84721
#   user_data_dir: ~/.cloakbrowser-manager/profiles/a1b2c3d4

# Create with explicit fingerprint seed (for reproducible fingerprints)
cm profile create my-profile --fingerprint-seed 12345

# Quick create with just a name + proxy
cm profile create my-profile --proxy "http://proxy:8080"

# List all profiles
cm profile list
# Output (table):
# ID          NAME           STATUS    CDP PORT  PROXY
# a1b2c3d4    my-profile     stopped   -         http://proxy:8080
# b2c3d4e5    work-chrome    running   5100      socks5://proxy:1080

cm profile list --json
# [{ "id": "a1b2c3d4", "name": "my-profile", "status": "stopped", ... }, ...]

cm profile list --running
# Only show running profiles

# Show a profile
cm profile show a1b2c3d4
cm profile show my-profile          # by name (unique match)
cm profile show a1b2                # by ID prefix
# Output: detailed view with all fields

# Edit a profile
cm profile edit a1b2c3d4 --proxy "http://new-proxy:9090"
cm profile edit a1b2c3d4 --humanize --human-preset careful
cm profile edit a1b2c3d4 --tags "gmail,us-east,production"
cm profile edit a1b2c3d4 --notes "Work Gmail account"

# Delete a profile
cm profile delete a1b2c3d4
cm profile delete a1b2c3d4 --force    # Skip confirmation
cm profile delete a1b2c3d4 --keep-data  # Keep user_data_dir on disk

# Clone a profile
cm profile clone a1b2c3d4 --name "my-profile-2"
```

### 4.2 `cm launch` — Start Browsers

```bash
# Launch a profile (opens window)
cm launch a1b2c3d4
# Output:
# Launching my-profile...
#   Browser window opened
#   CDP: http://127.0.0.1:5100
#   PID: 12345

# Launch multiple profiles
cm launch a1b2c3d4 b2c3d4e5 c3d4e5f6

# Launch and wait (keep CLI alive until browser closes)
cm launch a1b2c3d4 --wait

# Launch with custom URL
cm launch a1b2c3d4 --url "https://gmail.com"

# Launch detached (background, don't open window)
# Note: headless mode - no window, just CDP
cm launch a1b2c3d4 --headless
# (overrides profile's headless setting for this launch)

# Launch all profiles with auto_launch=true
cm launch --auto

# Launch with debug logging
cm launch a1b2c3d4 --verbose
```

### 4.3 `cm stop` — Stop Browsers

```bash
# Stop a profile
cm stop a1b2c3d4
# Output: Stopped my-profile. Sessions saved.

# Stop all running profiles
cm stop --all

# Force stop (kill process if graceful close fails)
cm stop a1b2c3d4 --force

# Stop by name
cm stop my-profile
```

### 4.4 `cm list` — Quick Overview

```bash
cm list
# Compact table:
# NAME          STATUS    CDP      PROXY
# my-profile    running   5100     http://proxy:8080
# work-chrome   stopped   -        socks5://proxy:1080
# gmail-prod    error     5102     -

cm list --json
cm list --running
cm list --stopped
cm list --tag gmail
cm list --filter "proxy contains 8080"
```

### 4.5 `cm status` — Live Status

```bash
cm status
# System-wide:
#   Profiles: 12 total, 3 running, 1 error
#   CloakBrowser: v0.4.8 (Chromium 148)
#   Data dir: ~/.cloakbrowser-manager
#   CDP ports in use: 5100, 5101, 5102

cm status a1b2c3d4
# Per-profile:
#   Name: my-profile
#   Status: running
#   CDP: http://127.0.0.1:5100
#   PID: 12345
#   Uptime: 2h 34m
#   Window: headed, 1920x1080
#   Proxy: http://proxy:8080

cm status --watch     # Live refresh every 2s (like htop)
```

### 4.6 `cm cdp` — CDP Endpoints

```bash
# List CDP endpoints for all running profiles
cm cdp list
# my-profile        http://127.0.0.1:5100
# work-chrome       http://127.0.0.1:5101

# Get CDP URL for a specific profile
cm cdp url a1b2c3d4
# http://127.0.0.1:5100

# Copy CDP URL to clipboard
cm cdp url a1b2c3d4 --copy

# Generate code snippet
cm cdp code a1b2c3d4 --lang python
# from playwright.sync_api import sync_playwright
# with sync_playwright() as pw:
#     browser = pw.chromium.connect_over_cdp("http://127.0.0.1:5100")
#     page = browser.contexts[0].pages[0]
#     page.goto("https://example.com")

cm cdp code a1b2c3d4 --lang javascript
# const { chromium } = require('playwright');
# const browser = await chromium.connectOverCDP('http://127.0.0.1:5100');
```

### 4.7 `cm tui` — Interactive Dashboard

```bash
cm tui
# Launches full-screen TUI dashboard (see Section 5)

cm tui --compact    # Minimal mode, fewer details
```

### 4.8 `cm config` — Global Settings

```bash
cm config show
# Current configuration:
#   data_dir: ~/.cloakbrowser-manager
#   cdp_port_start: 5100
#   cdp_port_range: 100
#   default_browser: cloakbrowser
#   auto_cleanup: true
#   log_level: info

cm config set cdp_port_start 6000
cm config set default_browser cloakbrowser-pro

# Set global Pro license (applied to all profiles unless overridden)
cm config set license_key cb_xxxxxxxx
```

### 4.9 `cm info` — Diagnostics

```bash
cm info
# System:
#   OS: Windows 11 (10.0.22631)
#   Python: 3.12.3
#   Architecture: AMD64
#
# CloakBrowser:
#   Version: 0.4.8
#   Chromium: 148.0.7778.215.5
#   Binary: ~/.cloakbrowser/chromium-148/...
#   License: Pro (cb_xxx...)
#   Status: ready
#
# Manager:
#   Version: 0.1.0
#   Data dir: ~/.cloakbrowser-manager
#   Profiles: 12 (3 running)
#   CDP ports free: 97/100

cm info --json    # Machine-readable
```

---

## 5. TUI Design

Built with **Textual** (Python). The TUI is a full-screen terminal dashboard.

### Layout

```
┌─ CloakBrowser Manager ────────── 12 profiles (3 running) ───────────────────┐
│ ┌─ Sidebar ───────────────────────────────────────────────────────────────┐ │
│ │  FILTER BY TAG                                                          │ │
│ │  [All] [gmail] [work] [production] [+New]                               │ │
│ │                                                                          │ │
│ │  ┌─ Profile List ──────────────────────────────────────────────────────┐│ │
│ │  │ ▶ my-profile            ● running    5100   gmail                  ││ │
│ │  │   work-chrome           ● running    5101   work                   ││ │
│ │  │   gmail-prod            ● running    5102   gmail,production       ││ │
│ │  │   test-profile          ○ stopped    -      test                   ││ │
│ │  │   scraper-1             ○ stopped    -      scraper                ││ │
│ │  │   ...                                                              ││ │
│ │  └────────────────────────────────────────────────────────────────────┘│ │
│ │                                                                          │ │
│ │  ACTIONS                                                                 │ │
│ │  [N]ew  [L]aunch  [S]top  [E]dit  [D]elete  [C]DP  [Q]uit              │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌─ Detail Pane (for selected profile) ────────────────────────────────────┐ │
│ │  ▶ gmail-prod                                           [running]       │ │
│ │                                                                          │ │
│ │  ID:          c3d4e5f6                                                 │ │
│ │  Platform:    windows         Screen:    1920×1080                      │ │
│ │  Proxy:       http://proxy:8080    GeoIP:  yes                         │ │
│ │  Timezone:    America/New_York    Locale:  en-US                        │ │
│ │  Humanize:    yes (default)      Headless: no                          │ │
│ │  Fingerprint: 49281              CDP:     http://127.0.0.1:5102        │ │
│ │  PID:         28934              Uptime: 3h 12m                        │ │
│ │  Tags:        gmail, production                                         │ │
│ │                                                                          │ │
│ │  [Copy CDP URL] [Open in Browser] [View Logs]                           │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ ┌─ Logs ──────────────────────────────────────────────────────────────────┐ │
│ │  14:32:01  Launched gmail-prod (cdp:5102, pid:28934)                   │ │
│ │  14:31:45  Stopped test-profile (pid:28102)                             │ │
│ │  14:30:00  Created new profile "scraper-2"                              │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│ F1:Help  F2:Launch  F3:Stop  F4:Edit  F5:Refresh  F6:CDP  F10:Quit         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Keybindings

| Key | Action |
|---|---|
| `↑` / `↓` / `j` / `k` | Navigate profile list |
| `Enter` | Select profile (show detail) |
| `n` | New profile dialog |
| `l` | Launch selected profile |
| `s` | Stop selected profile |
| `e` | Edit selected profile |
| `d` | Delete selected profile |
| `c` | Copy CDP URL to clipboard |
| `o` | Open CDP URL in default browser |
| `r` | Refresh list |
| `f` | Filter profiles (search) |
| `F1` | Help |
| `F5` | Refresh |
| `F10` / `q` / `Ctrl+C` | Quit |

### TUI Component Tree

```
App
├── Header (title + stats)
├── Container (horizontal)
│   ├── Sidebar
│   │   ├── TagFilter (horizontal chip list)
│   │   ├── ProfileList (DataTable)
│   │   └── ActionBar (footer buttons)
│   └── Body (vertical)
│       ├── ProfileDetail (rich panel)
│       └── LogPanel (RichLog)
├── Footer (hotkey hints)
└── Modal screens (overlay)
    ├── CreateProfileModal
    ├── EditProfileModal
    ├── ConfirmDeleteModal
    └── CodeSnippetModal
```

---

## 6. Module Design

```
cloakbrowser_manager_cli/
├── __init__.py
├── __main__.py              # Entry: python -m cloakbrowser_manager
├── _version.py
│
├── cli/
│   ├── __init__.py
│   ├── main.py              # Click group, top-level dispatch
│   ├── profile.py           # cm profile * commands
│   ├── launch.py            # cm launch * commands
│   ├── stop.py              # cm stop * commands
│   ├── list.py              # cm list * commands
│   ├── status.py            # cm status * commands
│   ├── cdp.py               # cm cdp * commands
│   ├── config.py            # cm config * commands
│   ├── info.py              # cm info * commands
│   └── tui.py               # cm tui command
│
├── tui/
│   ├── __init__.py
│   ├── app.py               # Textual App class
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── dashboard.py     # Main dashboard screen
│   │   ├── create_profile.py
│   │   ├── edit_profile.py
│   │   └── confirm.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── profile_list.py  # DataTable widget
│   │   ├── tag_filter.py    # Tag chip filter
│   │   ├── profile_detail.py
│   │   └── log_panel.py
│   └── styles.css           # Textual CSS
│
├── core/
│   ├── __init__.py
│   ├── database.py          # SQLite operations
│   ├── models.py            # Pydantic models
│   ├── browser_manager.py   # Launch/stop/manage browser processes
│   ├── cdp_manager.py       # CDP port allocation & health check
│   ├── config.py            # Global config (~/.cloakbrowser-manager/config.yaml)
│   └── utils.py             # Platform utils, proxy normalization, etc.
│
└── tests/
    ├── __init__.py
    ├── test_database.py
    ├── test_browser_manager.py
    ├── test_cli.py
    └── test_cdp_manager.py
```

### Module Responsibilities

#### `core/database.py`
- SQLite connection management (WAL mode, foreign keys)
- CRUD for profiles
- Auto-migration for schema changes
- Tag management (stored as JSON array in profiles table)
- Data directory creation & management

#### `core/models.py`
- Pydantic v2 models (same structure as existing Manager but simplified)
- Input validation (proxy format, platform enum, etc.)
- JSON serialization for CLI output

#### `core/browser_manager.py`
- Process lifecycle: launch → monitor → stop
- Wraps `cloakbrowser.launch_persistent_context()` (or `launch()`)
- Maps profile settings → CloakBrowser args (fingerprint, gpu, screen, etc.)
- Tracks running instances (pid → profile_id mapping)
- Handles graceful shutdown (close context → kill if needed)
- No VNC — native windows only.
- Platform-specific handling (Windows: no DISPLAY needed; Linux: use DISPLAY; macOS: native)

#### `core/cdp_manager.py`
- Port allocation from configurable range (default: 5100-5199)
- Port availability check before launch
- Health check: verify CDP endpoint is reachable
- Rotates ports to avoid TIME_WAIT collisions on rapid restart

#### `core/config.py`
- Read/write `~/.cloakbrowser-manager/config.yaml`
- Global defaults: data_dir, cdp_port_start, cdp_port_range, license_key, default_browser
- Merges with env vars: `CM_DATA_DIR`, `CM_CDP_PORT_START`, etc.

---

## 7. Profile Lifecycle

```
┌─────────┐    create    ┌───────────┐    launch     ┌──────────┐
│  (none)  │ ──────────→ │  stopped  │ ────────────→ │ running  │
└─────────┘              └───────────┘               └──────────┘
                               ↑                     │        │
                               │    stop             │        │ crash
                               │←────────────────────┘        │
                               │                              │
                               │              ┌──────────┐    │
                               │              │  error   │←───┘
                               │              └──────────┘
                               │                    │
                               │    delete          │ delete
                               └────────────────────┘
```

- **stopped**: Profile exists, user_data_dir on disk, no process running.
- **launching**: Brief transition while Chromium starts up.
- **running**: Browser process alive, CDP port open. `pid` and `cdp_port` populated.
- **error**: Browser crashed or failed to launch. `status` kept until next launch.

Auto-cleanup: When browser process exits (user closes window, crashes), the manager detects it and updates status to `stopped`. The profile data (cookies, sessions) persists in user_data_dir.

---

## 8. Browser Lifecycle (Native)

### Launch Flow

```
cm launch <profile_id>
│
├── 1. Load profile from DB
├── 2. Check status: if already running → error
├── 3. Allocate CDP port (find free port in range)
├── 4. Clean stale lock files in user_data_dir
│      (SingletonLock, SingletonCookie, SingletonSocket)
├── 5. Build CloakBrowser args:
│      --fingerprint=<seed>
│      --fingerprint-platform=<p>
│      --fingerprint-gpu-vendor=<vendor>
│      --fingerprint-gpu-renderer=<renderer>
│      --fingerprint-screen-width=<w>
│      --fingerprint-screen-height=<h>
│      --remote-debugging-port=<cdp_port>
│      + launch_args from profile
├── 6. Call cloakbrowser.launch_persistent_context():
│      user_data_dir=<profile_dir>
│      headless=<profile.headless>
│      proxy=<profile.proxy>
│      timezone, locale, humanize, etc.
│      viewport={"width": w, "height": h}
├── 7. Store pid, cdp_port in DB
├── 8. Register cleanup hook (on browser close → update status)
└── 9. Return success with CDP URL
```

### Stop Flow

```
cm stop <profile_id>
│
├── 1. Find running instance
├── 2. Try graceful close: browser_context.close() (Playwright)
│      → Saves cookies/localStorage before exit
├── 3. If graceful fails or --force: kill process (os.kill(pid))
├── 4. Wait for process exit (timeout 10s)
├── 5. Clean up: set status=stopped, cdp_port=null, pid=null
└── 6. Return success
```

### Platform Differences

| Aspect | Windows | macOS | Linux |
|---|---|---|---|
| **Window** | Native Win32 window | Native Cocoa window | X11/Wayland (needs DISPLAY) |
| **GPU** | Hardware GPU passthrough | Hardware GPU passthrough | Software or hardware |
| **Process kill** | `taskkill /F /PID` | `kill -9` | `kill -9` |
| **Socket** | Same Python API | Same Python API | Same Python API |
| **Data dir** | `%LOCALAPPDATA%\cloakbrowser-manager` | `~/Library/Application Support/cloakbrowser-manager` | `~/.cloakbrowser-manager` |
| **Headless** | `headless=True` (no window) | `headless=True` (no window) | `headless=True` (no window, no DISPLAY needed) |

---

## 9. Automation API (CDP)

Every running profile exposes Chrome DevTools Protocol on a local port.

### Connection

```python
# Playwright
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("http://127.0.0.1:5100")
    # browser.contexts[0] is the persistent context
    page = browser.contexts[0].pages[0]
    page.goto("https://example.com")
```

```javascript
// Playwright
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP('http://127.0.0.1:5100');
const page = browser.contexts()[0].pages()[0];
await page.goto('https://example.com');
```

```javascript
// Puppeteer
const puppeteer = require('puppeteer-core');
const browser = await puppeteer.connect({
    browserURL: 'http://127.0.0.1:5100',
    defaultViewport: null,
});
const pages = await browser.pages();
const page = pages[0];
```

### CDP Manager Features

- **Port health check**: `cm cdp check a1b2c3d4` — verifies CDP is responding
- **Connection codegen**: `cm cdp code a1b2c3d4 --lang python` — generates ready-to-use code
- **Port listing**: `cm cdp list` — shows all active CDP endpoints
- **Port conflict detection**: warns if port is in use by another process

---

## 10. Configuration System

### Global Config File

```yaml
# ~/.cloakbrowser-manager/config.yaml

# Data directory
data_dir: ~/.cloakbrowser-manager

# CDP port allocation
cdp:
  port_start: 5100
  port_range: 100

# Default CloakBrowser variant
default_browser: cloakbrowser  # or "cloakbrowser-pro"

# Global Pro license (can be overridden per-profile)
license_key: cb_xxxxxxxx

# Behavior
auto_cleanup: true        # Automatically clean up on crash
log_level: info           # debug, info, warning, error
launch_timeout: 30        # seconds
stop_timeout: 10          # seconds

# CLI defaults for new profiles
defaults:
  platform: windows
  screen_width: 1920
  screen_height: 1080
  headless: false
  humanize: false
  geoip: false
```

### Environment Variables

| Variable | Config Key | Description |
|---|---|---|
| `CM_DATA_DIR` | `data_dir` | Override data directory |
| `CM_CDP_PORT_START` | `cdp.port_start` | Start of CDP port range |
| `CM_CDP_PORT_RANGE` | `cdp.port_range` | Number of ports in CDP range |
| `CM_LICENSE_KEY` | `license_key` | Global Pro license key |
| `CM_LOG_LEVEL` | `log_level` | Logging verbosity |

---

## 11. Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | CloakBrowser Python SDK is primary. Mature CLI/TUI ecosystem. |
| **CLI** | Click 8.x | Composable, well-documented, rich output. |
| **TUI** | Textual 2.x | Modern, async-native, cross-platform. Active development. |
| **Models** | Pydantic v2 | Fast, validation, serialization. Same as existing Manager. |
| **Database** | SQLite (stdlib `sqlite3`) | Zero deps, single file, battle-tested. |
| **Browser** | `cloakbrowser` (PyPI) | Drop-in Playwright replacement with stealth patches. |
| **Async** | `asyncio` (stdlib) | Browser management is async. CLI optionally sync. |
| **Output** | Rich (for CLI tables/formatting) | Beautiful terminal output, already used by Textual. |
| **YAML** | PyYAML or `ruamel.yaml` | Config file format. |
| **Packaging** | `pyproject.toml` + setuptools/poetry | Standard Python packaging. |
| **Testing** | pytest + pytest-asyncio | Standard test framework. |
| **Linting** | ruff + mypy | Fast, modern linter + type checker. |

### Dependencies

```toml
[project]
name = "cloakbrowser-manager"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "cloakbrowser>=0.4.0",
    "click>=8.0",
    "textual>=2.0",
    "pydantic>=2.0",
    "pyyaml>=6.0",
    "rich>=13.0",
]

[project.scripts]
cm = "cloakbrowser_manager_cli.cli.main:cli"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.5",
    "mypy>=1.10",
]
```

---

## 12. Implementation Phases

### Phase 1: Core Engine (Week 1-2)
**Goal**: Database + browser lifecycle, usable via CLI.

- [x]<sup>todo</sup> Project scaffolding (`pyproject.toml`, `__main__.py`, structure)
- [ ] `core/database.py` — SQLite schema, CRUD, migrations
- [ ] `core/models.py` — Pydantic models
- [ ] `core/config.py` — Config file read/write
- [ ] `core/browser_manager.py` — Launch/stop CloakBrowser processes
- [ ] `core/cdp_manager.py` — Port allocation
- [ ] `core/utils.py` — Proxy normalization, platform detection
- [ ] CLI: `cm profile create/list/show/edit/delete`
- [ ] CLI: `cm launch` / `cm stop`
- [ ] CLI: `cm list` / `cm status`

### Phase 2: Rich CLI (Week 3)
**Goal**: Full CLI with JSON/YAML output, codegen, diagnostics.

- [ ] CLI: `cm cdp list/url/code/check`
- [ ] CLI: `cm config show/set`
- [ ] CLI: `cm info`
- [ ] Rich table formatting for all list commands
- [ ] JSON/YAML output mode (`--json`, `--yaml` flags)
- [ ] CDP connection code generation (Python, JS, Puppeteer)
- [ ] CLI integration tests

### Phase 3: TUI Dashboard (Week 4-5)
**Goal**: Full interactive terminal dashboard.

- [ ] `tui/app.py` — Textual App with dashboard screen
- [ ] `tui/widgets/profile_list.py` — DataTable with live status
- [ ] `tui/widgets/tag_filter.py` — Filter chips
- [ ] `tui/widgets/profile_detail.py` — Rich detail panel
- [ ] `tui/widgets/log_panel.py` — Live log stream
- [ ] `tui/screens/create_profile.py` — Creation modal
- [ ] `tui/screens/edit_profile.py` — Edit modal
- [ ] Keybindings: launch, stop, edit, delete, CDP copy
- [ ] Auto-refresh (poll profile status every 2s)

### Phase 4: Polish & Distribution (Week 6)
**Goal**: Package, test, document.

- [ ] Cross-platform testing (Windows, macOS, Linux)
- [ ] Error handling & recovery (browser crash, port conflicts)
- [ ] Comprehensive `--help` for all commands
- [ ] PyPI package (`pip install cloakbrowser-manager`)
- [ ] README with screenshots
- [ ] User guide (mkdocs or GitHub wiki)
- [ ] CI/CD (GitHub Actions: test on all platforms)
- [ ] Shell completion (bash, zsh, fish)

---

## Appendix A: Comparison with Existing Manager

| Feature | Web Manager | CLI/TUI Manager |
|---|---|---|
| Deployment | Docker container | `pip install` |
| Interface | Web browser | Terminal |
| Browser view | VNC (noVNC) | Native OS window |
| Resource usage | ~512MB RAM + container overhead | ~200MB per browser instance |
| Multi-profile | Yes, in one container | Yes, each as separate process |
| Automation | CDP over HTTP proxy | Direct CDP |
| Cross-platform | Docker only | Native Windows/macOS/Linux |
| Headless mode | Via VNC | True headless |
| Extensions | Via launch_args | Via launch_args or `extension_paths` |
| Auth | Token-based | None (local only, OS user isolation) |

## Appendix B: Example Workflows

### Workflow 1: Multi-account Gmail
```bash
# Create profiles for 3 Gmail accounts
cm profile create gmail-1 --proxy "http://us-proxy:8080" --timezone "America/Chicago" --humanize --tags gmail
cm profile create gmail-2 --proxy "http://uk-proxy:8080" --timezone "Europe/London" --humanize --tags gmail
cm profile create gmail-3 --proxy "http://jp-proxy:8080" --timezone "Asia/Tokyo" --humanize --tags gmail

# Launch all Gmail profiles
cm launch $(cm profile list --tag gmail --json | jq -r '.[].id')

# Open TUI to monitor
cm tui
```

### Workflow 2: Web Scraping
```bash
cm profile create scraper --proxy "http://residential-proxy:8080" --geoip --human-preset careful --headless
cm launch scraper
cm cdp code scraper --lang python | pbcopy  # Copy connection code
# Paste into scraping script...
```

### Workflow 3: Debug with live window + CDP
```bash
cm profile create debug-session --humanize --platform windows
cm launch debug-session --url "https://target-site.com"
# Watch browser window, interact manually
# Then connect via CDP to run automation:
cm cdp url debug-session
# → http://127.0.0.1:5100
```

---

*Last updated: 2026-07-07*
