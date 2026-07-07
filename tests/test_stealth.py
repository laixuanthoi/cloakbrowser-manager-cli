"""Tests for stealth diagnostic helpers and CLI registration."""

import json
from pathlib import Path

from click.testing import CliRunner

from cloakbrowser_manager_cli.cli.main import cli
from cloakbrowser_manager_cli.cli.stealth import assess_local_probe


def _probe(**overrides):
    data = {
        "webdriver": False,
        "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/148.0.0.0",
        "appVersion": "5.0 (Windows NT 10.0; Win64; x64)",
        "platform": "Win32",
        "languages": ["en-US", "en"],
        "language": "en-US",
        "hardwareConcurrency": 8,
        "deviceMemory": 8,
        "maxTouchPoints": 0,
        "pluginsLength": 5,
        "mimeTypesLength": 2,
        "chromeObject": True,
        "notificationPermission": "denied",
        "timezone": "America/New_York",
        "screen": {"width": 1920, "height": 1080},
        "inner": {"width": 1920, "height": 1007, "outerWidth": 1920, "outerHeight": 1032, "devicePixelRatio": 1},
        "webgl": {"supported": True, "vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE NVIDIA"},
        "canvasHash": "12345",
    }
    data.update(overrides)
    return data


def test_stealth_group_registered():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "stealth" in result.output


def test_stealth_test_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["stealth", "test", "--help"])
    assert result.exit_code == 0
    assert "--external" in result.output
    assert "--keep-open" in result.output
    assert "--artifact-dir" in result.output


def test_stealth_report_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["stealth", "report", "--help"])
    assert result.exit_code == 0
    assert "Show the latest saved stealth report" in result.output


def test_assess_local_probe_pass():
    profile = {
        "platform": "windows",
        "timezone": "America/New_York",
        "locale": "en-US",
        "screen_width": 1920,
        "screen_height": 1080,
        "hardware_concurrency": 8,
        "device_memory": 8,
    }
    result = assess_local_probe(profile, _probe())
    assert result["verdict"] == "PASS"
    assert result["score"] == 100
    assert any(c["name"] == "navigator.webdriver" and c["status"] == "PASS" for c in result["checks"])


def test_assess_local_probe_fail_on_webdriver():
    result = assess_local_probe({"platform": "windows"}, _probe(webdriver=True))
    assert result["verdict"] == "FAIL"
    assert result["score"] < 100
    webdriver_check = [c for c in result["checks"] if c["name"] == "navigator.webdriver"][0]
    assert webdriver_check["status"] == "FAIL"


def test_stealth_report_reads_latest(temp_data_dir):
    runner = CliRunner()
    create = runner.invoke(cli, ["profile", "create", "report-profile"])
    assert create.exit_code == 0
    show = runner.invoke(cli, ["--json", "profile", "show", "report-profile"])
    profile = json.loads(show.output)

    report_dir = temp_data_dir / "reports" / profile["id"] / "20260101-000000"
    report_dir.mkdir(parents=True)
    (report_dir / "result.json").write_text(json.dumps({
        "profile_name": "report-profile",
        "score": 95,
        "verdict": "PASS",
        "artifacts": {"result": str(report_dir / "result.json")},
    }), encoding="utf-8")

    result = runner.invoke(cli, ["stealth", "report", "report-profile"])
    assert result.exit_code == 0
    assert str(report_dir) in result.output
    assert "PASS" in result.output


def test_stealth_test_requires_profile_or_all():
    runner = CliRunner()
    result = runner.invoke(cli, ["stealth", "test"])
    assert result.exit_code == 1
    assert "Usage: cm stealth test PROFILE" in result.output
