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

## Install

```bash
pip install cloakbrowser-manager
```

Requires Python 3.10+ and [CloakBrowser](https://pypi.org/project/cloakbrowser/) (`pip install cloakbrowser`).

### From source

```bash
git clone https://github.com/CloakHQ/CloakBrowser-Manager-CLI.git
cd CloakBrowser-Manager-CLI
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

### CDP Automation

| Command | Description |
|---|---|
| `cm cdp list` | List CDP endpoints for all running profiles |
| `cm cdp url <id>` | Print CDP URL for a running profile |
| `cm cdp url <id> --copy` | Copy CDP URL to clipboard |
| `cm cdp code <id> --lang python` | Generate Playwright connection code |
| `cm cdp code <id> --lang puppeteer` | Generate Puppeteer connection code |
| `cm cdp check <id>` | Health-check the CDP endpoint |

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
| `l` | Launch selected |
| `s` | Stop selected |
| `e` | Edit selected |
| `d` | Delete selected |
| `c` | Copy CDP URL + show code snippet |
| `r` | Refresh |
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

No Docker, no VNC, no web server — just a CLI talking to CloakBrowser directly.

## Development

```bash
git clone <repo>
cd cloakbrowser-manager-cli
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check src/

# Type check
mypy src/cloakbrowser_manager_cli/

# Run CLI
python -m cloakbrowser_manager_cli --help
```

## License

MIT — see [LICENSE](LICENSE).
