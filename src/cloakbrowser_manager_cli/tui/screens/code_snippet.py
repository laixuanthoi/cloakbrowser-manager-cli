"""Code snippet display screen — shows Playwright/Puppeteer connection code."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Select


class CodeSnippetScreen(ModalScreen[None]):
    """Show connection code for a running profile."""

    def __init__(self, profile: dict):
        super().__init__()
        self._profile = profile
        self._lang = "python"

    def compose(self) -> ComposeResult:
        cdp_url = f"http://127.0.0.1:{self._profile['cdp_port']}"

        with Container(id="modal"):
            yield Static(f"[bold]Connect to: {self._profile['name']}[/bold]", id="modal-title")
            yield Static(f"CDP URL: {cdp_url}")

            yield Select(
                [("Python (Playwright)", "python"),
                 ("JavaScript (Playwright)", "javascript"),
                 ("JavaScript (Puppeteer)", "puppeteer")],
                value="python",
                id="code-lang",
            )

            code = self._generate_code("python", cdp_url)
            yield Static(code, id="code-block")

            with Horizontal(id="modal-buttons"):
                yield Button("Close", variant="default", id="btn-close")

    def on_select_changed(self, event: Select.Changed) -> None:
        self._lang = str(event.value)
        cdp_url = f"http://127.0.0.1:{self._profile['cdp_port']}"
        code = self._generate_code(self._lang, cdp_url)
        self.query_one("#code-block", Static).update(code)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    def _generate_code(self, lang: str, cdp_url: str) -> str:
        if lang == "python":
            return f'''from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp("{cdp_url}")
    page = browser.contexts[0].pages[0]
    page.goto("https://example.com")'''
        elif lang == "javascript":
            return f'''const {{ chromium }} = require('playwright');

const browser = await chromium.connectOverCDP('{cdp_url}');
const page = browser.contexts()[0].pages()[0];
await page.goto('https://example.com');'''
        else:
            return f'''const puppeteer = require('puppeteer-core');

const browser = await puppeteer.connect({{
    browserURL: '{cdp_url}',
    defaultViewport: null,
}});
const pages = await browser.pages();
const page = pages[0];
await page.goto('https://example.com');'''
