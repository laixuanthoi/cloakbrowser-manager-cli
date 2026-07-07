# Advanced Fingerprint / Browser Options + Stealth Testing Plan

## Goal

Bring the native CLI/TUI manager closer to current CloakBrowser capabilities by adding:

1. First-class advanced fingerprint/browser options instead of relying only on raw `launch_args`.
2. Built-in stealth/proxy diagnostics via `cm stealth test`.
3. Better runtime reconciliation when browsers close/crash or PID tracking is unavailable.

---

## Phase A — Data Model & Schema

### A1. Add profile fields

Add DB/model fields for advanced CloakBrowser options:

| Field | Type | Maps to |
|---|---|---|
| `extension_paths` | JSON list[str] | `extension_paths=[...]` launch kwarg |
| `browser_version` | str/null | `browser_version=` launch kwarg |
| `stealth_args` | bool | `stealth_args=` launch kwarg |
| `device_memory` | int/null | `--fingerprint-device-memory=` |
| `brand` | str/null | `--fingerprint-brand=` |
| `brand_version` | str/null | `--fingerprint-brand-version=` |
| `platform_version` | str/null | `--fingerprint-platform-version=` |
| `location` | str/null | `--fingerprint-location=` |
| `storage_quota` | int/null | `--fingerprint-storage-quota=` |
| `taskbar_height` | int/null | `--fingerprint-taskbar-height=` |
| `fonts_dir` | str/null | `--fingerprint-fonts-dir=` |
| `windows_font_metrics` | bool | `--fingerprint-windows-font-metrics` |
| `webrtc_ip` | str/null | `--fingerprint-webrtc-ip=` |
| `fingerprint_noise` | bool/null | `--fingerprint-noise=false` when false |
| `fingerprint_mode` | enum `normal/off` | `--fingerprint=off` when off |
| `allow_3p_cookies` | bool | `--fingerprint-allow-3p-cookies` |
| `license_through_proxy` | bool | `--license-through-proxy` |
| `widevine_enabled` | bool | diagnostic/env handling, not necessarily launch arg |

### A2. Migrations

Update `core/database.py` migrations for all new columns. JSON columns:

- `extension_paths TEXT DEFAULT '[]'`

Booleans:

- stored as INTEGER 0/1.

### A3. Pydantic models

Update:

- `ProfileCreate`
- `ProfileUpdate`
- `Profile`
- serializers/deserializers

Validation:

- `extension_paths`: normalize to list of paths.
- `fingerprint_mode`: `normal | off`.
- `webrtc_ip`: `auto`, IPv4/IPv6, or null.
- `location`: accept raw string initially, e.g. `lat,long`.

---

## Phase B — BrowserManager Mapping

### B1. Launch kwargs

Map profile fields directly:

```python
launch_kwargs = {
    ...,
    "extension_paths": profile.get("extension_paths") or None,
    "browser_version": profile.get("browser_version") or None,
    "stealth_args": bool(profile.get("stealth_args", True)),
}
```

Only include kwargs when supported/non-null.

### B2. Fingerprint args builder

Extend `_build_fingerprint_args()` with advanced flags:

```text
--fingerprint-device-memory=<n>
--fingerprint-brand=<brand>
--fingerprint-brand-version=<version>
--fingerprint-platform-version=<version>
--fingerprint-location=<location>
--fingerprint-storage-quota=<mb>
--fingerprint-taskbar-height=<px>
--fingerprint-fonts-dir=<path>
--fingerprint-windows-font-metrics
--fingerprint-webrtc-ip=<auto|ip>
--fingerprint-noise=false
--fingerprint=off
--fingerprint-allow-3p-cookies
--license-through-proxy
```

Important rule:

- If `fingerprint_mode == off`, do **not** also add `--fingerprint=<seed>` or `--fingerprint-platform`, unless explicitly intended. This should be a clean pass-through/debug mode.

### B3. GeoIP dependency UX

If `geoip=True` and `geoip2` is missing, show actionable error:

```bash
pip install "cloakbrowser[geoip]"
```

Optional: add `cm info` diagnostic for GeoIP support.

---

## Phase C — CLI Advanced Options

### C1. `cm profile create/edit`

Add options:

```bash
--extension PATH             # repeatable
--browser-version VERSION
--stealth-args/--no-stealth-args
--device-memory GB
--brand BRAND
--brand-version VERSION
--platform-version VERSION
--location LAT,LON
--storage-quota MB
--taskbar-height PX
--fonts-dir PATH
--windows-font-metrics/--no-windows-font-metrics
--webrtc-ip auto|IP
--fingerprint-noise/--no-fingerprint-noise
--fingerprint-mode normal|off
--allow-3p-cookies/--no-allow-3p-cookies
--license-through-proxy/--no-license-through-proxy
--widevine/--no-widevine
```

### C2. `cm profile show`

Group output sections:

- Basic
- Network
- Fingerprint
- Advanced
- Runtime

### C3. `cm info`

Add diagnostics:

- CloakBrowser version
- downloaded binary version/path if available
- GeoIP support installed? yes/no
- Widevine CDM detected? yes/no
- Pro license present? yes/no redacted

---

## Phase D — TUI Advanced UX

### D1. Keep create modal simple

Do not overload create modal initially. Keep current quick-create fields.

### D2. Add Advanced Edit modal/screen

Add separate advanced screen/tab from detail pane:

- Key: `a` = Advanced
- Sections:
  - Browser: extensions, browser version, stealth args
  - Fingerprint: device memory, brand, WebRTC, storage quota, noise, pass-through
  - Compatibility: allow 3P cookies, Widevine

### D3. Display advanced summary in detail pane

Add compact lines:

```text
Browser Version: auto
Extensions: 2
Stealth Args: yes
WebRTC IP: auto
3P Cookies: disabled
Fingerprint Mode: normal
```

---

## Phase E — Stealth Testing CLI

### E1. Add command group

New file: `cli/stealth.py`

Commands:

```bash
cm stealth test PROFILE
cm stealth test --all
cm stealth test PROFILE --external
cm stealth test PROFILE --url https://bot.sannysoft.com/
cm stealth report PROFILE
```

Register in `cli/main.py`.

### E2. Local test checks

Launch profile, run JS probes locally:

- `navigator.webdriver`
- userAgent/appVersion
- platform
- languages/language
- hardwareConcurrency
- deviceMemory
- maxTouchPoints
- plugins/mimeTypes length
- `window.chrome`
- permissions behavior
- timezone
- screen/inner/outer dimensions
- WebGL vendor/renderer
- canvas hash
- audio hash optional
- WebRTC candidate IP optional

Output:

```bash
cm stealth test Gmail-US

Score: 96/100 PASS
Checks:
  ✓ navigator.webdriver false
  ✓ plugins present
  ✓ timezone matches profile
  ✓ locale matches profile
  ✓ WebGL present
  ! proxy not configured
```

JSON output supported by top-level `--json`.

### E3. Proxy test

If profile has proxy:

- launch with proxy
- navigate to simple IP endpoint, e.g. `https://api.ipify.org?format=json`
- detect proxy connection failure separately
- optional GeoIP compare if installed

Report:

- proxy reachable
- public IP
- timezone/locale mismatch warnings

### E4. External test mode

Optional external checks:

- default URL: `https://bot.sannysoft.com/`
- save artifacts:
  - `.cloakbrowser-manager/reports/<profile-id>/<timestamp>/sannysoft.txt`
  - screenshot PNG
  - raw JSON local probe

Do not depend on external test for normal pass/fail because proxy/network may fail.

### E5. Cleanup

Always stop profile after test unless `--keep-open`.

Options:

```bash
--keep-open
--timeout 60
--headless/--headed
--artifact-dir PATH
```

---

## Phase F — Runtime Reconciliation

### F1. Improve stale running detection

Current PID may be `None`. Add CDP-based reconciliation:

- If status running and PID missing/dead:
  - check `cdp_port` HTTP `/json/version`
  - if CDP alive: keep running
  - if CDP dead: set stopped

### F2. Add commands

```bash
cm status --reconcile
cm profile reset-status PROFILE
cm profile reset-status --all
```

### F3. TUI integration

Auto-refresh should call reconcile periodically but avoid cursor resets:

- every 10s reconcile running profiles
- rebuild list only if signature changes

---

## Phase G — Tests

### G1. Unit tests

- DB migrations for new columns
- model validation
- browser arg construction
- profile create/edit options
- stealth scoring function
- status reconciliation CDP alive/dead mocked

### G2. CLI tests

- `cm profile create` with advanced flags
- `cm profile edit` with advanced flags
- `cm stealth test --help`
- `cm profile reset-status`

### G3. Optional integration tests

Marked slow/manual:

```bash
pytest -m browser
```

Actually launches CloakBrowser and runs local probe.

---

## Implementation Order

Recommended order:

1. **A + B**: schema/model + BrowserManager mapping.
2. **C**: CLI create/edit/show/info support.
3. **F**: runtime reconciliation and reset-status.
4. **E**: stealth test command.
5. **D**: TUI advanced screen.
6. **G**: tests after each phase, not only at end.

---

## Acceptance Criteria

- `python -m pytest tests/ -q` passes.
- Existing profiles auto-migrate without data loss.
- `cm profile create test --device-memory 8 --webrtc-ip auto --allow-3p-cookies` works.
- `cm profile show test` displays advanced options.
- Launch includes correct CloakBrowser kwargs/flags.
- `cm stealth test PROFILE` launches, probes, reports, and stops cleanly.
- If browser manually closes, status is reconciled to stopped.
- TUI cursor does not reset during reconcile/refresh.
