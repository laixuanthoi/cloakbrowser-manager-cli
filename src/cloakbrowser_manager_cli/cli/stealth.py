"""CLI commands for stealth and proxy diagnostics."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from cloakbrowser_manager_cli.cli.main import CLIContext, cli, pass_context
from cloakbrowser_manager_cli.core import database as db
from cloakbrowser_manager_cli.core.browser_manager import BrowserError, get_browser_manager

DEFAULT_EXTERNAL_URL = "https://bot.sannysoft.com/"
IP_CHECK_URL = "https://api.ipify.org?format=json"

LOCAL_PROBE_JS = r"""
async () => {
  const glInfo = (() => {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) return {supported: false};
      const dbg = gl.getExtension('WEBGL_debug_renderer_info');
      return {
        supported: true,
        vendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
        renderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
      };
    } catch (e) {
      return {supported: false, error: String(e)};
    }
  })();

  const permissionState = async (name) => {
    try {
      return (await navigator.permissions.query({name})).state;
    } catch (e) {
      return 'error:' + String(e).slice(0, 120);
    }
  };

  let canvasHash = null;
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 300;
    canvas.height = 80;
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '16px Arial';
    ctx.fillStyle = '#f60';
    ctx.fillRect(0, 0, 300, 80);
    ctx.fillStyle = '#069';
    ctx.fillText('CloakBrowser stealth audit 👋 𝌆', 2, 2);
    const data = canvas.toDataURL();
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      hash = ((hash << 5) - hash) + data.charCodeAt(i);
      hash |= 0;
    }
    canvasHash = String(hash);
  } catch (e) {
    canvasHash = 'error:' + String(e);
  }

  return {
    webdriver: navigator.webdriver,
    userAgent: navigator.userAgent,
    appVersion: navigator.appVersion,
    platform: navigator.platform,
    languages: Array.from(navigator.languages || []),
    language: navigator.language,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory ?? null,
    maxTouchPoints: navigator.maxTouchPoints,
    pluginsLength: navigator.plugins ? navigator.plugins.length : null,
    mimeTypesLength: navigator.mimeTypes ? navigator.mimeTypes.length : null,
    chromeObject: typeof window.chrome !== 'undefined',
    notificationPermission: await permissionState('notifications'),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    screen: {
      width: screen.width,
      height: screen.height,
      availWidth: screen.availWidth,
      availHeight: screen.availHeight,
      colorDepth: screen.colorDepth,
      pixelDepth: screen.pixelDepth,
    },
    inner: {
      width: innerWidth,
      height: innerHeight,
      outerWidth: outerWidth,
      outerHeight: outerHeight,
      devicePixelRatio: devicePixelRatio,
    },
    webgl: glInfo,
    canvasHash,
  };
}
"""


@cli.group()
def stealth() -> None:
    """Run stealth, fingerprint, and proxy diagnostics."""
    pass


@stealth.command("test")
@click.argument("identifier", required=False)
@click.option("--all", "test_all", is_flag=True, help="Test all profiles")
@click.option("--external", is_flag=True, help=f"Run external detector test (default: {DEFAULT_EXTERNAL_URL})")
@click.option("--url", "external_url", help="External detector URL to visit and capture")
@click.option("--keep-open", is_flag=True, help="Leave browser open after testing")
@click.option("--timeout", type=float, default=60.0, show_default=True, help="Per-navigation timeout in seconds")
@click.option("--headless/--headed", default=None, help="Override profile headless mode for this test")
@click.option("--artifact-dir", type=click.Path(path_type=Path), help="Directory for stealth test artifacts")
@pass_context
def test_command(
    ctx: CLIContext,
    identifier: str | None,
    test_all: bool,
    external: bool,
    external_url: str | None,
    keep_open: bool,
    timeout: float,
    headless: bool | None,
    artifact_dir: Path | None,
) -> None:
    """Launch profile(s), run local stealth probes, and optionally capture an external detector."""
    if test_all:
        profiles = db.list_profiles()
    else:
        if not identifier:
            click.echo("Usage: cm stealth test PROFILE  or  cm stealth test --all", err=True)
            raise SystemExit(1)
        profile = db.find_profile(identifier)
        if not profile:
            click.echo(f"Profile not found: {identifier}", err=True)
            raise SystemExit(1)
        profiles = [profile]

    if not profiles:
        click.echo("No profiles to test.")
        return

    run_external = bool(external or external_url)
    url = external_url or (DEFAULT_EXTERNAL_URL if external else None)
    results = asyncio.run(_run_stealth_tests(
        profiles,
        run_external=run_external,
        external_url=url,
        keep_open=keep_open,
        timeout=timeout,
        headless=headless,
        artifact_base=artifact_dir,
    ))

    if ctx.output.format in ("json", "yaml"):
        ctx.output.print(results if test_all else results[0])
    else:
        _print_results(results)


@stealth.command("report")
@click.argument("identifier")
@click.option("--artifact-dir", type=click.Path(path_type=Path), help="Custom artifact root to inspect")
@pass_context
def report(ctx: CLIContext, identifier: str, artifact_dir: Path | None) -> None:
    """Show the latest saved stealth report for a profile."""
    profile = db.find_profile(identifier)
    if not profile:
        click.echo(f"Profile not found: {identifier}", err=True)
        raise SystemExit(1)

    root = artifact_dir or (db.get_data_dir() / "reports")
    report_root = root / profile["id"]
    if not report_root.exists():
        click.echo(f"No stealth reports found for {profile['name']}.", err=True)
        raise SystemExit(1)

    reports = sorted([p for p in report_root.iterdir() if p.is_dir()])
    if not reports:
        click.echo(f"No stealth reports found for {profile['name']}.", err=True)
        raise SystemExit(1)

    latest = reports[-1]
    result_path = latest / "result.json"
    data: dict[str, Any] = {"profile": profile["name"], "report_dir": str(latest)}
    if result_path.exists():
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data["warning"] = "result.json could not be parsed"

    if ctx.output.format in ("json", "yaml"):
        ctx.output.print(data)
    else:
        click.echo(f"Latest report for {profile['name']}:")
        click.echo(str(latest))
        if result_path.exists():
            click.echo(f"Score: {data.get('score')}  Verdict: {data.get('verdict')}")


async def _run_stealth_tests(
    profiles: list[dict[str, Any]],
    *,
    run_external: bool,
    external_url: str | None,
    keep_open: bool,
    timeout: float,
    headless: bool | None,
    artifact_base: Path | None,
) -> list[dict[str, Any]]:
    mgr = get_browser_manager()
    results = []
    for profile in profiles:
        result = await _run_one_stealth_test(
            mgr,
            profile,
            run_external=run_external,
            external_url=external_url,
            keep_open=keep_open,
            timeout=timeout,
            headless=headless,
            artifact_base=artifact_base,
        )
        results.append(result)
    return results


async def _run_one_stealth_test(
    mgr: Any,
    profile: dict[str, Any],
    *,
    run_external: bool,
    external_url: str | None,
    keep_open: bool,
    timeout: float,
    headless: bool | None,
    artifact_base: Path | None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "profile_id": profile["id"],
        "profile_name": profile["name"],
        "score": None,
        "verdict": "ERROR",
        "checks": [],
        "errors": [],
        "artifacts": {},
    }
    artifact_dir = _artifact_dir(profile, artifact_base)
    launched = False

    try:
        overrides: dict[str, Any] = {"url": "about:blank"}
        if headless is not None:
            overrides["headless"] = headless

        launched_profile = await mgr.launch(profile["id"], **overrides)
        launched = True
        result["cdp_port"] = launched_profile.get("cdp_port")

        context = getattr(mgr, "_contexts", {}).get(profile["id"])
        if context is None:
            raise BrowserError("Browser context unavailable after launch")

        page = context.pages[0] if getattr(context, "pages", None) else await context.new_page()
        timeout_ms = max(int(timeout * 1000), 1000)

        await page.goto("data:text/html,<title>stealth audit</title><body>audit</body>", timeout=timeout_ms)
        local_probe = await page.evaluate(LOCAL_PROBE_JS)
        result["local_probe"] = local_probe
        _write_json(artifact_dir / "local_probe.json", local_probe)
        result["artifacts"]["local_probe"] = str(artifact_dir / "local_probe.json")

        assessment = assess_local_probe(profile, local_probe)
        result.update(assessment)

        if profile.get("proxy"):
            result["proxy"] = await _run_proxy_probe(page, timeout_ms)

        if run_external:
            external_capture = await _run_external_capture(
                page,
                external_url or DEFAULT_EXTERNAL_URL,
                timeout_ms,
                artifact_dir,
            )
            result["external"] = external_capture
            result["artifacts"].update(external_capture.get("artifacts", {}))

    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        result["verdict"] = "ERROR"
    finally:
        if launched and not keep_open:
            try:
                await mgr.stop(profile["id"], force=True)
            except Exception as exc:
                result.setdefault("errors", []).append(f"stop failed: {type(exc).__name__}: {exc}")
        result["artifacts"]["result"] = str(artifact_dir / "result.json")
        _write_json(artifact_dir / "result.json", result)

    return result


async def _run_proxy_probe(page: Any, timeout_ms: int) -> dict[str, Any]:
    proxy: dict[str, Any] = {"url": IP_CHECK_URL, "status": "unknown"}
    try:
        await page.goto(IP_CHECK_URL, wait_until="domcontentloaded", timeout=min(timeout_ms, 15000))
        text = await page.locator("body").inner_text(timeout=5000)
        proxy["raw"] = text.strip()
        try:
            parsed = json.loads(text)
            proxy["ip"] = parsed.get("ip")
        except json.JSONDecodeError:
            pass
        proxy["status"] = "pass"
    except Exception as exc:
        proxy["status"] = "fail"
        proxy["error"] = f"{type(exc).__name__}: {exc}"
    return proxy


async def _run_external_capture(page: Any, url: str, timeout_ms: int, artifact_dir: Path) -> dict[str, Any]:
    capture: dict[str, Any] = {"url": url, "status": "unknown", "artifacts": {}}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 30000))
        except Exception:
            pass
        try:
            await page.wait_for_timeout(3000)
        except Exception:
            pass

        text = await page.locator("body").inner_text(timeout=10000)
        text_path = artifact_dir / "external_text.txt"
        text_path.write_text(text, encoding="utf-8")
        capture["artifacts"]["external_text"] = str(text_path)

        screenshot_path = artifact_dir / "external_screenshot.png"
        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            capture["artifacts"]["external_screenshot"] = str(screenshot_path)
        except Exception as exc:
            capture["screenshot_error"] = f"{type(exc).__name__}: {exc}"

        capture["status"] = "captured"
        capture["title"] = await page.title()
        capture["text_excerpt"] = text[:1000]
    except Exception as exc:
        capture["status"] = "error"
        capture["error"] = f"{type(exc).__name__}: {exc}"
    return capture


def assess_local_probe(profile: dict[str, Any], probe: dict[str, Any]) -> dict[str, Any]:
    """Score local stealth probe output against profile settings."""
    checks: list[dict[str, Any]] = []
    score = 100

    def add(name: str, status: str, message: str, penalty: int = 0, value: Any = None) -> None:
        nonlocal score
        if status in ("WARN", "FAIL"):
            score -= penalty
        checks.append({
            "name": name,
            "status": status,
            "message": message,
            "value": value,
        })

    webdriver = probe.get("webdriver")
    add(
        "navigator.webdriver",
        "PASS" if webdriver is False else "FAIL",
        "webdriver is false" if webdriver is False else f"webdriver is {webdriver!r}",
        penalty=35,
        value=webdriver,
    )

    plugins = probe.get("pluginsLength")
    add(
        "plugins",
        "PASS" if isinstance(plugins, int) and plugins > 0 else "WARN",
        f"plugins length: {plugins}",
        penalty=10,
        value=plugins,
    )

    chrome_obj = probe.get("chromeObject")
    add(
        "window.chrome",
        "PASS" if chrome_obj else "WARN",
        "window.chrome present" if chrome_obj else "window.chrome missing",
        penalty=8,
        value=chrome_obj,
    )

    webgl = probe.get("webgl") or {}
    add(
        "webgl",
        "PASS" if webgl.get("supported") else "WARN",
        f"{webgl.get('vendor')} / {webgl.get('renderer')}" if webgl.get("supported") else "WebGL unavailable",
        penalty=8,
        value=webgl,
    )

    expected_tz = profile.get("timezone")
    actual_tz = probe.get("timezone")
    if expected_tz:
        add(
            "timezone",
            "PASS" if actual_tz == expected_tz else "WARN",
            f"expected {expected_tz}, got {actual_tz}",
            penalty=15,
            value=actual_tz,
        )
    else:
        add("timezone", "PASS", f"actual {actual_tz}", value=actual_tz)

    expected_locale = profile.get("locale")
    actual_lang = probe.get("language")
    actual_langs = probe.get("languages") or []
    if expected_locale:
        locale_ok = expected_locale == actual_lang or expected_locale in actual_langs
        add(
            "locale",
            "PASS" if locale_ok else "WARN",
            f"expected {expected_locale}, got {actual_lang}/{actual_langs}",
            penalty=10,
            value={"language": actual_lang, "languages": actual_langs},
        )
    else:
        add("locale", "PASS", f"actual {actual_lang}/{actual_langs}", value={"language": actual_lang, "languages": actual_langs})

    platform_status, platform_message = _assess_platform(profile.get("platform"), probe)
    add("platform", platform_status, platform_message, penalty=15, value=probe.get("platform"))

    screen = probe.get("screen") or {}
    expected_w = profile.get("screen_width")
    expected_h = profile.get("screen_height")
    if expected_w and expected_h:
        screen_ok = screen.get("width") == expected_w and screen.get("height") == expected_h
        add(
            "screen",
            "PASS" if screen_ok else "WARN",
            f"expected {expected_w}x{expected_h}, got {screen.get('width')}x{screen.get('height')}",
            penalty=5,
            value=screen,
        )

    expected_hw = profile.get("hardware_concurrency")
    actual_hw = probe.get("hardwareConcurrency")
    if expected_hw is not None:
        add(
            "hardwareConcurrency",
            "PASS" if actual_hw == expected_hw else "WARN",
            f"expected {expected_hw}, got {actual_hw}",
            penalty=5,
            value=actual_hw,
        )
    else:
        add("hardwareConcurrency", "PASS", f"actual {actual_hw}", value=actual_hw)

    expected_mem = profile.get("device_memory")
    actual_mem = probe.get("deviceMemory")
    if expected_mem is not None:
        add(
            "deviceMemory",
            "PASS" if actual_mem == expected_mem else "WARN",
            f"expected {expected_mem}, got {actual_mem}",
            penalty=5,
            value=actual_mem,
        )

    add("canvas", "PASS" if probe.get("canvasHash") else "WARN", f"hash {probe.get('canvasHash')}", penalty=4, value=probe.get("canvasHash"))

    score = max(score, 0)
    has_fail = any(c["status"] == "FAIL" for c in checks)
    if has_fail or score < 70:
        verdict = "FAIL"
    elif score < 85 or any(c["status"] == "WARN" for c in checks):
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {"score": score, "verdict": verdict, "checks": checks}


def _assess_platform(expected: str | None, probe: dict[str, Any]) -> tuple[str, str]:
    if not expected:
        return "PASS", f"actual {probe.get('platform')}"
    nav_platform = str(probe.get("platform") or "").lower()
    ua = str(probe.get("userAgent") or "").lower()
    expected = expected.lower()
    if expected == "windows":
        ok = "win" in nav_platform or "windows" in ua
    elif expected == "macos":
        ok = "mac" in nav_platform or "mac os" in ua
    elif expected == "linux":
        ok = "linux" in nav_platform or "linux" in ua or "x11" in ua
    else:
        ok = True
    return ("PASS" if ok else "WARN", f"expected {expected}, got platform={probe.get('platform')} ua={probe.get('userAgent')}")


def _artifact_dir(profile: dict[str, Any], artifact_base: Path | None) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    root = artifact_base or (db.get_data_dir() / "reports")
    path = root / profile["id"] / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _print_results(results: list[dict[str, Any]]) -> None:
    console = Console()
    table = Table(title="Stealth Test Results", show_header=True, header_style="bold cyan")
    table.add_column("Profile")
    table.add_column("Verdict")
    table.add_column("Score")
    table.add_column("Proxy")
    table.add_column("Artifacts")

    for result in results:
        verdict = result.get("verdict", "ERROR")
        style = {"PASS": "green", "WARN": "yellow", "FAIL": "red", "ERROR": "red"}.get(verdict, "white")
        proxy = result.get("proxy", {})
        proxy_status = proxy.get("status", "—") if proxy else "—"
        table.add_row(
            result.get("profile_name", "—"),
            f"[{style}]{verdict}[/{style}]",
            str(result.get("score") if result.get("score") is not None else "—"),
            proxy_status,
            result.get("artifacts", {}).get("result", "—"),
        )
    console.print(table)

    for result in results:
        console.print(f"\n[bold]{result.get('profile_name')}[/bold]")
        for check in result.get("checks", []):
            status = check.get("status")
            icon = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}.get(status, "?")
            console.print(f"  {icon} {check.get('name')}: {check.get('message')}")
        for error in result.get("errors", []):
            console.print(f"  [red]error:[/red] {error}")
