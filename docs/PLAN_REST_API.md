# REST API Server Plan — CloakBrowser Manager CLI/TUI

## Goal

Add a FastAPI REST server similar to `CloakBrowser-Manager`, but adapted to this native CLI/TUI architecture:

- No Docker/VNC.
- Native browser windows.
- Direct local CDP URLs.
- Optional Bearer token auth.
- Reuse existing core DB/browser/stealth modules.
- Expose OpenAPI docs.

---

## Phase REST-1 — Server Scaffold + Status + Profile CRUD

### Dependencies

Add to `pyproject.toml`:

```toml
fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
```

### Files

```txt
src/cloakbrowser_manager_cli/api/
  __init__.py
  app.py
  auth.py
  schemas.py
  routes_status.py
  routes_profiles.py
src/cloakbrowser_manager_cli/cli/serve.py
```

### CLI

```bash
cm serve
cm serve --host 127.0.0.1 --port 8080
cm serve --auth-token TOKEN
cm serve --reload
```

### Endpoints

```txt
GET    /api/status
GET    /api/profiles
POST   /api/profiles
GET    /api/profiles/{profile_id}
PATCH  /api/profiles/{profile_id}
DELETE /api/profiles/{profile_id}
```

### Behavior

- `GET /api/status`: system status + profile counts + version info.
- CRUD uses existing `db.*` functions.
- Profile identifier path can accept UUID/name/prefix via `db.find_profile()` where appropriate.
- Delete supports query `keep_data=false`.
- Optional auth via `Authorization: Bearer <token>`.
- Auth disabled by default when no token is configured.

### Tests

Use FastAPI `TestClient`:

- status OK
- create/list/show/update/delete profile
- auth required/unauthorized/authorized
- OpenAPI available

---

## Phase REST-2 — Browser Runtime Endpoints

### Endpoints

```txt
POST   /api/profiles/{profile_id}/launch
POST   /api/profiles/{profile_id}/stop
POST   /api/profiles/{profile_id}/reset-status
GET    /api/profiles/{profile_id}/status
POST   /api/reconcile
```

### Launch request

```json
{
  "url": "https://example.com",
  "headless": false,
  "extra_args": []
}
```

### Response

```json
{
  "profile_id": "...",
  "status": "running",
  "cdp_url": "http://127.0.0.1:5100",
  "cdp_port": 5100,
  "pid": 12345
}
```

### Tests

Mock `BrowserManager` launch/stop/reconcile where possible, avoid launching real browser in normal tests.

---

## Phase REST-3 — CDP & Codegen Endpoints

### Endpoints

```txt
GET    /api/profiles/{profile_id}/cdp
GET    /api/profiles/{profile_id}/cdp/code?lang=python|javascript|puppeteer
GET    /api/cdp
GET    /api/cdp/check/{profile_id}
```

### Notes

Unlike Docker web manager, this native server returns direct CDP URL:

```json
{
  "cdp_url": "http://127.0.0.1:5100"
}
```

No VNC/CDP proxy in this phase.

---

## Phase REST-4 — Stealth Test & Reports API

### Endpoints

```txt
POST   /api/profiles/{profile_id}/stealth-test
GET    /api/profiles/{profile_id}/reports
GET    /api/profiles/{profile_id}/reports/latest
GET    /api/profiles/{profile_id}/reports/{timestamp}
```

### Request

```json
{
  "external": false,
  "url": "https://bot.sannysoft.com/",
  "headless": true,
  "keep_open": false,
  "timeout": 60
}
```

### Behavior

- Reuse `cli.stealth` helper functions initially.
- Save artifacts under existing reports dir.
- Return structured JSON result.

---

## Phase REST-5 — Config/Info/Auth Polish

### Endpoints

```txt
GET    /api/info
GET    /api/config
PATCH  /api/config
GET    /api/auth/status
POST   /api/auth/login
POST   /api/auth/logout
```

### Notes

For API clients, Bearer token is enough. Login/logout endpoints are mainly for future web UI compatibility.

---

## Phase REST-6 — Hardening & Docs

### Hardening

- CORS config, default disabled or localhost-only.
- Redact secrets in profile output where needed.
- Safe error responses.
- Request size limits for notes/clipboard-like fields.
- Graceful shutdown: optionally stop running browsers only if configured.

### Docs

- README: REST API usage.
- Examples:
  - curl create profile
  - curl launch
  - Playwright connect over returned CDP URL

---

## Acceptance Criteria

- `python -m pytest tests/ -q` passes.
- `cm serve --host 127.0.0.1 --port 8080` starts.
- `/docs` opens OpenAPI UI.
- CRUD endpoints work with and without auth depending on config.
- Browser runtime endpoints can launch/stop profiles.
- CDP endpoints return direct CDP URLs.
- Stealth test endpoint returns same structured result as CLI.

---

## Implementation Order

1. REST-1: scaffold + CRUD + auth + tests.
2. REST-2: launch/stop/status/reconcile.
3. REST-3: CDP endpoints/codegen.
4. REST-4: stealth reports.
5. REST-5: config/info/auth polish.
6. REST-6: docs/hardening.
