# CloakBrowser Manager — CLI/TUI

Native CLI and TUI tool for managing [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) profiles — create, launch, and manage isolated stealth browser instances with unique fingerprints.

## Features

- **CLI-first**: Every operation via terminal commands with JSON/YAML output
- **TUI dashboard**: Interactive terminal UI with live status, filtering, and keyboard shortcuts
- **Native windows**: Browsers open as real OS windows — no Docker, no VNC
- **Profile management**: Create/edit/delete/clone profiles with custom fingerprints
- **Session persistence**: Cookies, localStorage, and cache survive browser restarts
- **CDP automation**: Each running profile exposes a Chrome DevTools Protocol port
- **Code generation**: Auto-generate Playwright (Python/JS) and Puppeteer connection snippets
- **Tag & search**: Organize profiles with tags and full-text search
- **Cross-platform**: Windows, macOS, Linux

## Documentation

- [docs/README.md](docs/README.md) — internal docs index
- [docs/SPEC.md](docs/SPEC.md) — project specification
- [AGENTS.md](AGENTS.md) — guidance for AI coding agents and maintainers

## Install

Requires Python 3.10+ and [CloakBrowser](https://pypi.org/project/cloakbrowser/).

### Quick install (recommended)

```bash
git clone https://github.com/laixuanthoi/cloakbrowser-manager-cli.git
cd cloakbrowser-manager-cli
uv tool install -e .
cm --help
```

This gives you a persistent `cm` command usable from any terminal.

### Dev install with uv

```bash
git clone https://github.com/laixuanthoi/cloakbrowser-manager-cli.git
cd cloakbrowser-manager-cli
uv sync --extra dev
uv run cm tui
uv run pytest tests/ -q
```

### From PyPI

```bash
pip install cloakbrowser-manager
```

### From GitHub with pip

```bash
pip install git+https://github.com/laixuanthoi/cloakbrowser-manager-cli.git
```

### Editable pip install

```bash
git clone https://github.com/laixuanthoi/cloakbrowser-manager-cli.git
cd cloakbrowser-manager-cli
pip install -e ".[dev]"
```

## Quick Start

```bash
# Create profiles
cm profile create gmail-us --proxy http://residential-proxy:8080 --timezone America/Chicago --humanize --tag gmail
cm profile create scraper-eu --proxy socks5://eu-gate:1080 --headless --geoip --tag scraper
cm profile create work --platform macos --screen-width 2560 --screen-height 1440 --gpu-vendor "Apple" --gpu-renderer "M3 Pro"

# See them
cm list
# ┌────────────┬───────────┬─────┬────────────────────────────┬──────────┐
# │ NAME       │ STATUS    │ CDP │ PROXY                      │ TAGS     │
# ├────────────┼───────────┼─────┼────────────────────────────┼──────────┤
# │ work       │ ○ stopped │ —   │ —                          │ work     │
# │ scraper-eu │ ○ stopped │ —   │ socks5://eu-gate:1080      │ scraper  │
# │ gmail-us   │ ○ stopped │ —   │ http://user:****@proxy:80… │ gmail    │
# └────────────┴───────────┴─────┴────────────────────────────┴──────────┘

# Launch a profile (opens native browser window)
cm launch gmail-us

# Open TUI dashboard
cm tui

# Connect via Playwright
cm cdp url gmail-us
# → http://127.0.0.1:5100

cm cdp code gmail-us --lang python
# from playwright.sync_api import sync_playwright
# with sync_playwright() as pw:
#     browser = pw.chromium.connect_over_cdp("http://127.0.0.1:5100")
#     page = browser.contexts[0].pages[0]
#     page.goto("https://example.com")

# See system status
cm status
cm info
```

## REST API Server

The manager can also run a FastAPI REST server for local automation or for a
small authenticated internal service. It uses the same SQLite database and core
browser manager as the CLI/TUI.

> Native mode note: this project does **not** run Docker, VNC, or noVNC. Browsers
> launch as native OS windows (or true headless when requested), and API CDP
> endpoints return the direct local CDP URL such as `http://127.0.0.1:5100`.

### Start the server

```bash
# Localhost only (default; CORS is not enabled by default)
cm serve

# Explicit host/port
cm serve --host 127.0.0.1 --port 8080

# Require Bearer token auth for protected routes
cm serve --auth-token "change-me"
```

You can also start/stop the API server from the TUI:

```bash
cm tui
# Press v → enter host/port/auth token → Start
# Press v again to stop the managed API subprocess
```

OpenAPI documentation is available while the server is running:

```txt
http://127.0.0.1:8080/docs
http://127.0.0.1:8080/openapi.json
```

`GET /api/status` and `/api/auth/*` compatibility endpoints are public. Profile,
runtime, CDP, config, info, and stealth endpoints require auth when a token is
configured.

### Auth token usage

```bash
TOKEN="change-me"
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8080/api/profiles
```

The API does not create server-side sessions. `/api/auth/login` only validates a
token; clients should keep sending the same `Authorization: Bearer ...` header.
Secrets such as config license keys, profile license keys, proxy credentials, and
API tokens are not echoed back in raw form by API responses.

### curl examples

Create a profile:

```bash
curl -X POST http://127.0.0.1:8080/api/profiles \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "api-gmail-us",
    "platform": "windows",
    "timezone": "America/New_York",
    "locale": "en-US",
    "humanize": true,
    "tags": [{"tag": "gmail"}]
  }'
```

List profiles:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/profiles
```

Launch a profile:

```bash
curl -X POST http://127.0.0.1:8080/api/profiles/api-gmail-us/launch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url": "https://gmail.com", "headless": false}'
```

Get the direct CDP URL:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://127.0.0.1:8080/api/profiles/api-gmail-us/cdp
# {"cdp_url":"http://127.0.0.1:5100", ...}
```

Run a stealth test:

```bash
curl -X POST http://127.0.0.1:8080/api/profiles/api-gmail-us/stealth-test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"headless": true, "external": false, "timeout": 60}'
```

Connect Playwright to the returned CDP URL:

```python
from playwright.sync_api import sync_playwright

cdp_url = "http://127.0.0.1:5100"
with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(cdp_url)
    page = browser.contexts[0].pages[0]
    page.goto("https://example.com")
```

## Command Reference

### Profile Management

| Command | Description |
|---|---|
| `cm profile create <name>` | Create a new browser profile with fingerprint settings |
| `cm profile list` | List all profiles with status, CDP port, proxy, tags |
| `cm profile show <id>` | Show full details for a profile |
| `cm profile edit <id>` | Edit profile settings (proxy, tags, platform, etc.) |
| `cm profile delete <id>` | Delete a profile and its browser data |
| `cm profile clone <id> --name <new>` | Clone settings to a new profile (new fingerprint, fresh data) |
| `cm profile export <id> --out profile.json` | Export reusable profile settings to JSON |
| `cm profile import profile.json --name <new>` | Import exported profile settings as a new profile |

### Launch & Stop

| Command | Description |
|---|---|
| `cm launch <id> [<id>...]` | Launch one or more profiles as native browser windows |
| `cm launch --auto` | Launch all profiles with `auto_launch=true` |
| `cm launch <id> --url <url>` | Launch and navigate to a specific URL |
| `cm launch <id> --wait` | Keep CLI alive until browser window closes |
| `cm stop <id>` | Gracefully stop a running profile (saves session) |
| `cm stop <id> --force` | Force kill the browser process |
| `cm stop --all` | Stop all running profiles |

### Overview

| Command | Description |
|---|---|
| `cm list` | Compact table view with status icons |
| `cm list --tag <tag>` | Filter by tag |
| `cm list --search <text>` | Full-text search across names, notes, tags |
| `cm list --running` | Show only running profiles |
| `cm status` | System overview: total profiles, CDP usage, version |
| `cm status <id>` | Detailed per-profile status with uptime |
| `cm status --watch` | Auto-refresh status every 2 seconds (like htop) |
| `cm health` | Check profile health using DB runtime fields, PID/CDP, and latest stealth report |
| `cm health <id>` | Check one profile's health |

### CDP Automation

| Command | Description |
|---|---|
| `cm cdp list` | List CDP endpoints for all running profiles |
| `cm cdp url <id>` | Print CDP URL for a running profile |
| `cm cdp url <id> --copy` | Copy CDP URL to clipboard |
| `cm cdp code <id> --lang python` | Generate Playwright connection code |
| `cm cdp code <id> --lang puppeteer` | Generate Puppeteer connection code |
| `cm cdp check <id>` | Health-check the CDP endpoint |

### Maintenance

| Command | Description |
|---|---|
| `cm backup create` | Create a zip backup of profiles DB and config |
| `cm backup list` | List backups in the default backup directory |
| `cm backup restore backup.zip --force` | Restore DB/config from a backup zip |
| `cm proxy check <id>` | Validate a profile proxy configuration |
| `cm proxy check <id> --connect` | Make a real HTTP request through the profile proxy |
| `cm proxy check --all` | Check every profile's proxy configuration |

### Configuration

| Command | Description |
|---|---|
| `cm config show` | Show current global configuration |
| `cm config set --<key> <value>` | Update a config value |
| `cm config get <key>` | Get a single config value |
| `cm config reset` | Reset to defaults |
| `cm info` | System diagnostics: OS, Python, CloakBrowser version |

### TUI

| Command | Description |
|---|---|
| `cm tui` | Launch interactive terminal dashboard |

**TUI Keybindings**:

| Key | Action |
|---|---|
| `n` | New profile |
| `e` | Edit selected |
| `a` | Advanced settings |
| `d` | Delete selected |
| `x` | Clone selected |
| `l` | Launch selected |
| `s` | Stop selected |
| `t` | Run stealth test |
| `c` | Copy CDP URL + show code snippet |
| `v` | Start/stop REST API server |
| `r` | Refresh |
| `F1` | Help modal |
| `q` | Quit |

## Global Options

```
cm [--json | --yaml] [--data-dir PATH] [-v | --verbose] <command>
```

- `--json` / `--yaml`: Machine-readable output (pipes well with `jq`, scripts)
- `--data-dir PATH`: Override data directory (default: `~/.cloakbrowser-manager`)
- `-v` / `--verbose`: Enable debug logging

## Data

All data is stored in `~/.cloakbrowser-manager/`:

| Path | Contents |
|---|---|
| `profiles.db` | SQLite database of all profiles and settings |
| `profiles/<uuid>/` | Per-profile CloakBrowser user data (cookies, sessions, cache, bookmarks) |
| `config.yaml` | Global configuration (CDP ports, license key, defaults) |

### Platform-specific defaults

| OS | Default Data Directory |
|---|---|
| Windows | `%LOCALAPPDATA%\cloakbrowser-manager` |
| macOS | `~/Library/Application Support/cloakbrowser-manager` |
| Linux | `~/.cloakbrowser-manager` |

## Profile Settings

Each profile supports these fingerprint and behavior settings:

| Setting | Description | Default |
|---|---|---|
| `name` | Display name | (required) |
| `fingerprint_seed` | Deterministic fingerprint (10000-99999) | random |
| `proxy` | HTTP/SOCKS5 proxy URL | none |
| `timezone` | Browser timezone (e.g. `America/Chicago`) | system |
| `locale` | Browser locale (e.g. `en-US`) | system |
| `platform` | Reported OS: `windows`, `macos`, `linux` | `windows` |
| `user_agent` | Custom User-Agent string | auto |
| `screen_width` / `screen_height` | Reported screen resolution | 1920×1080 |
| `gpu_vendor` / `gpu_renderer` | Reported GPU info | auto |
| `hardware_concurrency` | Reported CPU cores | auto |
| `color_scheme` | `light`, `dark`, `no-preference` | none |
| `humanize` | Human-like mouse/keyboard/scroll | `false` |
| `human_preset` | `default` or `careful` | `default` |
| `headless` | No browser window (CDP-only) | `false` |
| `geoip` | Auto-detect tz/locale from proxy IP | `false` |
| `auto_launch` | Launch on manager startup | `false` |
| `launch_args` | Extra Chromium CLI flags | `[]` |
| `tags` | Labels for organization | `[]` |
| `notes` | Free-form text | none |
| `license_key` | Per-profile Pro license | none |

## How It Works

CloakBrowser Manager stores profile configurations in SQLite and uses the [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) Python SDK to launch stealth Chromium instances. Each profile gets:

1. **Its own `user_data_dir`** — cookies, localStorage, cache, extensions
2. **A unique CDP port** (5100-5199 by default) — for Playwright/Puppeteer automation
3. **Native OS window** — headed mode uses real GPU, real Chrome UI
4. **Fingerprint arguments** — passed as Chromium CLI flags (`--fingerprint=...`, `--fingerprint-gpu-vendor=...`, etc.)

When you `cm stop`, the browser context closes gracefully, saving all session data. The CDP port is freed for reuse.

No Docker and no VNC. The CLI/TUI talks to CloakBrowser directly, and the optional REST API server reuses the same local core when you need HTTP automation.

## Development

```bash
git clone https://github.com/laixuanthoi/cloakbrowser-manager-cli.git
cd cloakbrowser-manager-cli
uv sync --extra dev

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/

# Type check
uv run mypy src/cloakbrowser_manager_cli/

# Run CLI
uv run cm --help
```

## License

MIT — see [LICENSE](LICENSE).
