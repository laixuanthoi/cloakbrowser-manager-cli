"""CLI health checks for profile runtime/report state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import get_browser_manager
from cloakbrowser_manager_cli.core.cdp_manager import get_cdp_manager


@cli.command("health")
@click.argument("identifier", required=False)
@click.option("--all", "check_all", is_flag=True, help="Check every profile")
@click.option("--skip-cdp", is_flag=True, help="Do not probe local CDP endpoints")
@pass_context
def health(ctx: CLIContext, identifier: str | None, check_all: bool, skip_cdp: bool):
    """Show basic profile health based on DB, PID/CDP, and latest stealth report."""
    if check_all or not identifier:
        profiles = db.list_profiles()
    else:
        profile = db.find_profile(identifier)
        if not profile:
            click.echo(f"Profile not found: {identifier}", err=True)
            raise SystemExit(1)
        profiles = [profile]

    results = [_profile_health(p, check_cdp=not skip_cdp) for p in profiles]
    ctx.output.print(results, title="Health")


def _profile_health(profile: dict[str, Any], *, check_cdp: bool = True) -> dict[str, Any]:
    issues: list[str] = []
    status = profile.get("status", "stopped")
    pid = profile.get("pid")
    cdp_port = profile.get("cdp_port")
    pid_alive = None
    cdp_alive = None

    if status == "running":
        if pid:
            pid_alive = get_browser_manager()._is_process_alive(pid)  # noqa: SLF001 - small CLI health probe
            if not pid_alive:
                issues.append("status is running but PID is not alive")
        elif not cdp_port:
            issues.append("status is running but PID and CDP port are missing")
        if cdp_port and check_cdp:
            cdp_alive = get_cdp_manager().health_check_sync(int(cdp_port), timeout=1.0)
            if not cdp_alive:
                issues.append("status is running but CDP endpoint is not responding")
    else:
        if pid or cdp_port:
            issues.append("runtime fields are set while status is not running")

    latest_report = _latest_stealth_report(profile["id"])
    if latest_report and latest_report.get("verdict") in {"WARN", "FAIL", "ERROR"}:
        issues.append(f"latest stealth verdict is {latest_report.get('verdict')}")

    overall = "ok" if not issues else ("error" if status == "running" and any("not" in i for i in issues) else "warn")
    return {
        "profile": profile.get("name"),
        "status": status,
        "health": overall,
        "pid_alive": pid_alive,
        "cdp_alive": cdp_alive,
        "latest_stealth_verdict": latest_report.get("verdict") if latest_report else None,
        "latest_stealth_score": latest_report.get("score") if latest_report else None,
        "issues": issues,
    }


def _latest_stealth_report(profile_id: str) -> dict[str, Any] | None:
    report_root = db.get_data_dir() / "reports" / profile_id
    if not report_root.exists():
        return None
    report_dirs = sorted([p for p in report_root.iterdir() if p.is_dir()])
    for report_dir in reversed(report_dirs):
        result_path = report_dir / "result.json"
        if not result_path.exists():
            continue
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        data["report_dir"] = str(report_dir)
        return data
    return None
