"""CLI commands for validating profile proxy configuration."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import click

from cloakbrowser_manager_cli.cli.main import cli, pass_context, CLIContext
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core import utils


@cli.group()
def proxy():
    """Check profile proxy settings."""
    pass


@proxy.command("check")
@click.argument("identifier", required=False)
@click.option("--all", "check_all", is_flag=True, help="Check every profile")
@click.option("--connect", is_flag=True, help="Make a real HTTP request through the proxy")
@click.option("--url", "test_url", default="https://api.ipify.org?format=json", show_default=True, help="URL for --connect")
@click.option("--timeout", type=float, default=5.0, show_default=True, help="Network timeout for --connect")
@pass_context
def check_proxy(ctx: CLIContext, identifier: str | None, check_all: bool, connect: bool, test_url: str, timeout: float):
    """Validate one profile proxy, or all profile proxies."""
    if check_all:
        profiles = db.list_profiles()
    else:
        if not identifier:
            click.echo("Usage: cm proxy check PROFILE or cm proxy check --all", err=True)
            raise SystemExit(1)
        profile = db.find_profile(identifier)
        if not profile:
            click.echo(f"Profile not found: {identifier}", err=True)
            raise SystemExit(1)
        profiles = [profile]

    results = [_check_profile_proxy(p, connect=connect, test_url=test_url, timeout=timeout) for p in profiles]
    ctx.output.print(results, title="Proxy Check")


def _check_profile_proxy(profile: dict[str, Any], *, connect: bool, test_url: str, timeout: float) -> dict[str, Any]:
    raw_proxy = profile.get("proxy")
    normalized = utils.normalize_proxy(raw_proxy)
    result: dict[str, Any] = {
        "profile": profile.get("name"),
        "status": "missing" if not normalized else "ok",
        "proxy": utils.redact_proxy(normalized),
        "normalized": utils.redact_proxy(normalized),
        "connect_tested": False,
        "public_ip": None,
        "error": None,
    }
    if not normalized:
        result["error"] = "No proxy configured"
        return result

    try:
        utils.validate_proxy(normalized)
    except ValueError as exc:
        result["status"] = "invalid"
        result["error"] = str(exc)
        return result

    if connect:
        result["connect_tested"] = True
        try:
            body = _probe_proxy(normalized, test_url=test_url, timeout=timeout)
        except Exception as exc:
            result["status"] = "error"
            result["error"] = f"{type(exc).__name__}: {exc}"
        else:
            result["status"] = "ok"
            result["public_ip"] = _extract_ip(body)
    return result


def _probe_proxy(proxy_url: str, *, test_url: str, timeout: float) -> str:
    proxies = {"http": proxy_url, "https": proxy_url}
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies))
    request = urllib.request.Request(test_url, headers={"User-Agent": "cloakbrowser-manager/0.1"})
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.read(4096).decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(exc.reason) from exc


def _extract_ip(body: str) -> str | None:
    text = body.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("ip"):
            return str(data["ip"])
    except json.JSONDecodeError:
        pass
    return text[:128] or None
