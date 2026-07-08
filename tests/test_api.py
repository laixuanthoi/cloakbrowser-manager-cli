"""Tests for the REST API server."""

import json
from pathlib import Path

from click.testing import CliRunner
from fastapi.testclient import TestClient

from cloakbrowser_manager_cli.api.app import create_app
from cloakbrowser_manager_cli.cli.main import cli
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import BrowserError


def test_api_status_ok():
    client = TestClient(create_app())
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["profiles_total"] == 0
    assert data["auth_enabled"] is False
    assert "cloakbrowser_manager_version" in data


def test_api_profile_crud():
    client = TestClient(create_app())

    create_response = client.post("/api/profiles", json={
        "name": "api-profile",
        "platform": "windows",
        "timezone": "America/New_York",
        "locale": "en-US",
        "tags": [{"tag": "api", "color": "#00ff00"}],
        "extension_paths": ["C:/extensions/a"],
        "device_memory": 8,
        "webrtc_ip": "auto",
    })
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["name"] == "api-profile"
    assert created["extension_paths"] == ["C:/extensions/a"]
    assert created["device_memory"] == 8
    assert created["webrtc_ip"] == "auto"

    list_response = client.get("/api/profiles")
    assert list_response.status_code == 200
    profiles = list_response.json()
    assert len(profiles) == 1
    assert profiles[0]["id"] == created["id"]

    by_name_response = client.get("/api/profiles/api-profile")
    assert by_name_response.status_code == 200
    assert by_name_response.json()["id"] == created["id"]

    prefix_response = client.get(f"/api/profiles/{created['id'][:8]}")
    assert prefix_response.status_code == 200
    assert prefix_response.json()["name"] == "api-profile"

    update_response = client.patch("/api/profiles/api-profile", json={
        "name": "api-profile-updated",
        "fingerprint_mode": "off",
        "notes": "updated over REST",
    })
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["name"] == "api-profile-updated"
    assert updated["fingerprint_mode"] == "off"
    assert updated["notes"] == "updated over REST"

    # Deletion removes user data directory by default when it exists.
    user_data_dir = Path(updated["user_data_dir"])
    user_data_dir.mkdir(parents=True, exist_ok=True)
    delete_response = client.delete(f"/api/profiles/{updated['id']}")
    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["deleted"] is True
    assert deleted["profile_id"] == updated["id"]
    assert deleted["data_deleted"] is True
    assert not user_data_dir.exists()

    missing_response = client.get(f"/api/profiles/{updated['id']}")
    assert missing_response.status_code == 404


def test_api_delete_keep_data():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "keep-data"}).json()
    user_data_dir = Path(created["user_data_dir"])
    user_data_dir.mkdir(parents=True, exist_ok=True)

    response = client.delete("/api/profiles/keep-data?keep_data=true")
    assert response.status_code == 200
    assert response.json()["data_deleted"] is False
    assert user_data_dir.exists()


def test_api_duplicate_create_returns_400():
    client = TestClient(create_app())
    assert client.post("/api/profiles", json={"name": "dupe"}).status_code == 201
    response = client.post("/api/profiles", json={"name": "dupe"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_api_profile_responses_redact_secrets():
    client = TestClient(create_app())
    response = client.post("/api/profiles", json={
        "name": "secret-profile",
        "proxy": "http://user:pass@example.com:8080",
        "license_key": "cb_1234567890abcdef",
    })
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["proxy"] == "http://user:****@example.com:8080"
    assert created["license_key"] == "cb_1…cdef"
    assert "pass" not in json.dumps(created)
    assert "cb_1234567890abcdef" not in json.dumps(created)

    listed = client.get("/api/profiles").json()[0]
    assert listed["proxy"] == "http://user:****@example.com:8080"
    assert listed["license_key"] == "cb_1…cdef"

    raw = db.find_profile("secret-profile")
    assert raw["proxy"] == "http://user:pass@example.com:8080"
    assert raw["license_key"] == "cb_1234567890abcdef"


def test_api_auth_required_unauthorized_authorized():
    client = TestClient(create_app(auth_token="secret-token"))

    # Health/status remains public for uptime checks.
    status_response = client.get("/api/status")
    assert status_response.status_code == 200
    assert status_response.json()["auth_enabled"] is True

    assert client.get("/api/profiles").status_code == 401
    assert client.get("/api/profiles", headers={"Authorization": "Bearer wrong"}).status_code == 401

    authorized = client.get("/api/profiles", headers={"Authorization": "Bearer secret-token"})
    assert authorized.status_code == 200
    assert authorized.json() == []


def test_api_openapi_available():
    client = TestClient(create_app())
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "CloakBrowser Manager API"
    assert "/api/status" in data["paths"]
    assert "/api/profiles" in data["paths"]


def test_api_runtime_launch_success(monkeypatch):
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "launch-me"}).json()

    class FakeManager:
        async def launch(self, profile_id, **overrides):
            assert profile_id == created["id"]
            assert overrides == {
                "url": "https://example.com/",
                "headless": True,
                "extra_args": ["--flag"],
            }
            return {**created, "status": "running", "cdp_port": 5100, "pid": 12345}

    import cloakbrowser_manager_cli.api.routes_runtime as runtime
    monkeypatch.setattr(runtime, "get_browser_manager", lambda: FakeManager())

    response = client.post(
        f"/api/profiles/{created['id']}/launch",
        json={"url": "https://example.com/", "headless": True, "extra_args": ["--flag"]},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data == {
        "profile_id": created["id"],
        "status": "running",
        "cdp_url": "http://127.0.0.1:5100",
        "cdp_port": 5100,
        "pid": 12345,
    }


def test_api_runtime_launch_not_found():
    client = TestClient(create_app())
    response = client.post("/api/profiles/missing/launch", json={})
    assert response.status_code == 404


def test_api_runtime_launch_extra_args_bounded():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "bounded-launch"}).json()
    response = client.post(
        f"/api/profiles/{created['id']}/launch",
        json={"extra_args": ["--flag"] * 101},
    )
    assert response.status_code == 422


def test_api_runtime_launch_error(monkeypatch):
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "bad-launch"}).json()

    class FakeManager:
        async def launch(self, profile_id, **overrides):
            raise BrowserError("boom via http://user:pass@example.com:8080 with cb_1234567890abcdef")

    import cloakbrowser_manager_cli.api.routes_runtime as runtime
    monkeypatch.setattr(runtime, "get_browser_manager", lambda: FakeManager())

    response = client.post(f"/api/profiles/{created['id']}/launch", json={})
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "boom" in detail
    assert "http://user:****@example.com:8080" in detail
    assert "pass" not in detail
    assert "cb_1234567890abcdef" not in detail


def test_api_runtime_stop_status_reset_reconcile(monkeypatch):
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "runtime-profile"}).json()
    db.update_profile(created["id"], status="running", cdp_port=5101, pid=222)

    class FakeManager:
        async def stop(self, profile_id, force=False):
            assert force is True
            db.update_profile(profile_id, status="stopped", cdp_port=None, pid=None)

        def get_status(self, profile_id):
            return {
                "status": "running",
                "cdp_url": "http://127.0.0.1:5101",
                "cdp_port": 5101,
                "pid": 222,
            }

        def reset_status(self, profile_id):
            return db.update_profile(profile_id, status="stopped", cdp_port=None, pid=None)

        async def verify_running(self):
            return {created["id"]: False}

    import cloakbrowser_manager_cli.api.routes_runtime as runtime
    monkeypatch.setattr(runtime, "get_browser_manager", lambda: FakeManager())

    status_response = client.get(f"/api/profiles/{created['id']}/status")
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["profile_id"] == created["id"]
    assert status_data["name"] == "runtime-profile"
    assert status_data["status"] == "running"
    assert status_data["cdp_url"] == "http://127.0.0.1:5101"

    stop_response = client.post(f"/api/profiles/{created['id']}/stop?force=true")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"
    assert stop_response.json()["cdp_port"] is None

    db.update_profile(created["id"], status="running", cdp_port=5102, pid=333)
    reset_response = client.post(f"/api/profiles/{created['id']}/reset-status")
    assert reset_response.status_code == 200
    assert reset_response.json()["status"] == "stopped"

    reconcile_response = client.post("/api/reconcile")
    assert reconcile_response.status_code == 200
    assert reconcile_response.json() == {
        "reconciled": 1,
        "running": {created["id"]: False},
    }


def test_api_runtime_auth_required(monkeypatch):
    client = TestClient(create_app(auth_token="secret"))
    assert client.post("/api/reconcile").status_code == 401
    assert client.post("/api/reconcile", headers={"Authorization": "Bearer secret"}).status_code == 200


# ── CDP endpoints ────────────────────────────────────────────────────────────


def test_api_cdp_running_profile_url_and_list():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "cdp-running"}).json()
    db.update_profile(created["id"], status="running", cdp_port=5100, pid=111)

    response = client.get(f"/api/profiles/{created['id']}/cdp")
    assert response.status_code == 200
    assert response.json() == {
        "profile_id": created["id"],
        "name": "cdp-running",
        "status": "running",
        "cdp_url": "http://127.0.0.1:5100",
        "cdp_port": 5100,
    }

    list_response = client.get("/api/cdp")
    assert list_response.status_code == 200
    assert list_response.json() == [response.json()]


def test_api_cdp_stopped_profile_gives_sensible_status():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "cdp-stopped"}).json()

    response = client.get(f"/api/profiles/{created['id']}/cdp")
    assert response.status_code == 409
    assert "not running" in response.json()["detail"]

    check_response = client.get(f"/api/cdp/check/{created['id']}")
    assert check_response.status_code == 200
    data = check_response.json()
    assert data["profile_id"] == created["id"]
    assert data["status"] == "stopped"
    assert data["healthy"] is False
    assert data["cdp_url"] is None


def test_api_cdp_code_generation_all_languages():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "cdp-code"}).json()
    db.update_profile(created["id"], status="running", cdp_port=5102, pid=222)

    expectations = {
        "python": "connect_over_cdp",
        "javascript": "connectOverCDP",
        "puppeteer": "puppeteer.connect",
    }
    for lang, marker in expectations.items():
        response = client.get(f"/api/profiles/{created['id']}/cdp/code?lang={lang}")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["profile_id"] == created["id"]
        assert data["lang"] == lang
        assert data["cdp_url"] == "http://127.0.0.1:5102"
        assert marker in data["code"]
        assert "http://127.0.0.1:5102" in data["code"]


def test_api_cdp_invalid_lang_rejected():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "bad-lang"}).json()
    db.update_profile(created["id"], status="running", cdp_port=5103, pid=333)

    response = client.get(f"/api/profiles/{created['id']}/cdp/code?lang=ruby")
    assert response.status_code == 422


def test_api_cdp_check_uses_cdp_manager(monkeypatch):
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "cdp-check"}).json()
    db.update_profile(created["id"], status="running", cdp_port=5104, pid=444)

    calls = []

    class FakeCDPManager:
        async def health_check(self, port, timeout=5.0):
            calls.append((port, timeout))
            return True

    import cloakbrowser_manager_cli.api.routes_cdp as routes_cdp
    monkeypatch.setattr(routes_cdp, "get_cdp_manager", lambda: FakeCDPManager())

    response = client.get(f"/api/cdp/check/{created['id']}?timeout=1.5")
    assert response.status_code == 200
    data = response.json()
    assert data["healthy"] is True
    assert data["detail"] == "CDP is healthy"
    assert data["cdp_url"] == "http://127.0.0.1:5104"
    assert calls == [(5104, 1.5)]


def test_api_cdp_auth_required():
    client = TestClient(create_app(auth_token="secret"))
    created = db.create_profile("cdp-auth")
    db.update_profile(created["id"], status="running", cdp_port=5105, pid=555)

    assert client.get(f"/api/profiles/{created['id']}/cdp").status_code == 401
    authorized = client.get(
        f"/api/profiles/{created['id']}/cdp",
        headers={"Authorization": "Bearer secret"},
    )
    assert authorized.status_code == 200


# ── Stealth endpoints ────────────────────────────────────────────────────────


def _write_report(profile_id: str, timestamp: str, payload: dict) -> Path:
    report_dir = db.get_data_dir() / "reports" / profile_id / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "result.json").write_text(json.dumps(payload), encoding="utf-8")
    for artifact_path in payload.get("artifacts", {}).values():
        path = Path(artifact_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("artifact", encoding="utf-8")
    return report_dir


def test_api_stealth_test_success(monkeypatch):
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "stealth-api"}).json()
    calls = []

    async def fake_run_one(mgr, profile, **kwargs):
        calls.append((profile["id"], kwargs))
        return {
            "profile_id": profile["id"],
            "profile_name": profile["name"],
            "score": 100,
            "verdict": "PASS",
            "checks": [],
            "errors": [],
            "artifacts": {"result": str(db.get_data_dir() / "reports" / profile["id"] / "r" / "result.json")},
        }

    import cloakbrowser_manager_cli.api.routes_stealth as routes_stealth
    monkeypatch.setattr(routes_stealth, "_run_one_stealth_test", fake_run_one)

    response = client.post(
        f"/api/profiles/{created['id']}/stealth-test",
        json={
            "external": True,
            "url": "https://bot.sannysoft.com/",
            "headless": True,
            "keep_open": False,
            "timeout": 12,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["verdict"] == "PASS"
    assert data["score"] == 100
    assert calls[0][0] == created["id"]
    assert calls[0][1]["run_external"] is True
    assert calls[0][1]["external_url"] == "https://bot.sannysoft.com/"
    assert calls[0][1]["headless"] is True
    assert calls[0][1]["keep_open"] is False
    assert calls[0][1]["timeout"] == 12


def test_api_stealth_test_not_found():
    client = TestClient(create_app())
    response = client.post("/api/profiles/missing/stealth-test", json={})
    assert response.status_code == 404


def test_api_stealth_test_error(monkeypatch):
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "stealth-error"}).json()

    async def fake_run_one(mgr, profile, **kwargs):
        raise RuntimeError("probe exploded")

    import cloakbrowser_manager_cli.api.routes_stealth as routes_stealth
    monkeypatch.setattr(routes_stealth, "_run_one_stealth_test", fake_run_one)

    response = client.post(f"/api/profiles/{created['id']}/stealth-test", json={})
    assert response.status_code == 500
    assert "probe exploded" in response.json()["detail"]


def test_api_stealth_reports_list_latest_and_timestamp():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "report-profile"}).json()
    artifact = db.get_data_dir() / "reports" / created["id"] / "20260707-010101" / "local_probe.json"
    _write_report(created["id"], "20260707-010101", {
        "profile_id": created["id"],
        "score": 90,
        "verdict": "WARN",
        "artifacts": {"local_probe": str(artifact)},
    })
    _write_report(created["id"], "20260707-020202", {
        "profile_id": created["id"],
        "score": 100,
        "verdict": "PASS",
        "artifacts": {},
    })

    list_response = client.get(f"/api/profiles/{created['id']}/reports")
    assert list_response.status_code == 200
    reports = list_response.json()
    assert [r["timestamp"] for r in reports] == ["20260707-010101", "20260707-020202"]
    assert reports[0]["score"] == 90
    assert reports[0]["artifacts"]["local_probe"]["exists"] is True
    assert "size" in reports[0]["artifacts"]["local_probe"]

    latest_response = client.get(f"/api/profiles/{created['id']}/reports/latest")
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["timestamp"] == "20260707-020202"
    assert latest["result"]["verdict"] == "PASS"

    timestamp_response = client.get(f"/api/profiles/{created['id']}/reports/20260707-010101")
    assert timestamp_response.status_code == 200
    by_timestamp = timestamp_response.json()
    assert by_timestamp["timestamp"] == "20260707-010101"
    assert by_timestamp["result"]["score"] == 90
    assert by_timestamp["artifacts"]["local_probe"]["exists"] is True

    missing_response = client.get(f"/api/profiles/{created['id']}/reports/nope")
    assert missing_response.status_code == 404


def test_api_stealth_reports_latest_not_found():
    client = TestClient(create_app())
    created = client.post("/api/profiles", json={"name": "no-report"}).json()
    response = client.get(f"/api/profiles/{created['id']}/reports/latest")
    assert response.status_code == 404


def test_api_stealth_auth_required(monkeypatch):
    client = TestClient(create_app(auth_token="secret"))
    created = db.create_profile("stealth-auth")

    assert client.post(f"/api/profiles/{created['id']}/stealth-test", json={}).status_code == 401
    assert client.get(f"/api/profiles/{created['id']}/reports").status_code == 401

    async def fake_run_one(mgr, profile, **kwargs):
        return {"profile_id": profile["id"], "verdict": "PASS", "score": 100}

    import cloakbrowser_manager_cli.api.routes_stealth as routes_stealth
    monkeypatch.setattr(routes_stealth, "_run_one_stealth_test", fake_run_one)

    authorized = client.post(
        f"/api/profiles/{created['id']}/stealth-test",
        json={},
        headers={"Authorization": "Bearer secret"},
    )
    assert authorized.status_code == 200


def test_serve_command_registered():
    result = CliRunner().invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--host" in result.output
    assert "--auth-token" in result.output
    assert "--reload" in result.output


# ── REST-5 info/config/auth endpoints ────────────────────────────────────────


def test_api_info_ok():
    client = TestClient(create_app())
    response = client.get("/api/info")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "system" in data
    assert "manager" in data
    assert "os" in data["system"]
    assert "profiles_total" in data["manager"]


def test_api_config_get_patch_redacts_license():
    client = TestClient(create_app())

    get_response = client.get("/api/config")
    assert get_response.status_code == 200
    config_data = get_response.json()
    assert config_data["cdp_port_start"] == 5100
    assert config_data["license_key"] is None
    assert config_data["license_key_present"] is False

    patch_response = client.patch("/api/config", json={
        "cdp_port_start": 6200,
        "cdp_port_range": 50,
        "log_level": "debug",
        "license_key": "cb_1234567890abcdef",
    })
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["cdp_port_start"] == 6200
    assert patched["cdp_port_range"] == 50
    assert patched["log_level"] == "debug"
    assert patched["license_key_present"] is True
    assert patched["license_key"] == "cb_1…cdef"
    assert patched["license_key"] != "cb_1234567890abcdef"

    # Persisted config is readable through the existing config module.
    from cloakbrowser_manager_cli.core import config as cfg
    saved = cfg.load_config()
    assert saved.cdp_port_start == 6200
    assert saved.license_key == "cb_1234567890abcdef"


def test_api_config_patch_validation():
    client = TestClient(create_app())
    response = client.patch("/api/config", json={"cdp_port_start": 80})
    assert response.status_code == 422


def test_api_auth_status_public_unauth_and_authed():
    client = TestClient(create_app(auth_token="secret"))

    unauth = client.get("/api/auth/status")
    assert unauth.status_code == 200
    assert unauth.json() == {"auth_required": True, "authenticated": False}

    authed = client.get("/api/auth/status", headers={"Authorization": "Bearer secret"})
    assert authed.status_code == 200
    assert authed.json() == {"auth_required": True, "authenticated": True}

    disabled = TestClient(create_app()).get("/api/auth/status")
    assert disabled.status_code == 200
    assert disabled.json() == {"auth_required": False, "authenticated": True}


def test_api_auth_login_success_failure_logout():
    client = TestClient(create_app(auth_token="secret"))

    failure = client.post("/api/auth/login", json={"token": "wrong"})
    assert failure.status_code == 401

    success = client.post("/api/auth/login", json={"token": "secret"})
    assert success.status_code == 200
    assert success.json() == {
        "ok": True,
        "auth_required": True,
        "authenticated": True,
        "token_type": "bearer",
        "access_token": None,
    }

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}

    no_auth = TestClient(create_app()).post("/api/auth/login", json={"token": "anything"})
    assert no_auth.status_code == 200
    assert no_auth.json() == {
        "ok": True,
        "auth_required": False,
        "authenticated": True,
        "token_type": None,
        "access_token": None,
    }


def test_api_login_token_length_bound():
    client = TestClient(create_app(auth_token="secret"))
    response = client.post("/api/auth/login", json={"token": "x" * 5000})
    assert response.status_code == 422


def test_api_info_config_auth_protected_behavior():
    client = TestClient(create_app(auth_token="secret"))

    assert client.get("/api/status").status_code == 200
    assert client.get("/api/auth/status").status_code == 200
    assert client.post("/api/auth/login", json={"token": "secret"}).status_code == 200

    assert client.get("/api/info").status_code == 401
    assert client.get("/api/config").status_code == 401
    assert client.patch("/api/config", json={"log_level": "debug"}).status_code == 401

    headers = {"Authorization": "Bearer secret"}
    assert client.get("/api/info", headers=headers).status_code == 200
    assert client.get("/api/config", headers=headers).status_code == 200
    assert client.patch("/api/config", json={"log_level": "debug"}, headers=headers).status_code == 200


def test_api_stealth_test_rejects_non_http_url():
    client = TestClient(create_app())
    create_response = client.post("/api/profiles", json={"name": "stealth-url-guard"})
    assert create_response.status_code == 201, create_response.text
    profile_id = create_response.json()["id"]

    response = client.post(
        f"/api/profiles/{profile_id}/stealth-test",
        json={"external": True, "url": "file:///etc/passwd"},
    )

    assert response.status_code == 422
