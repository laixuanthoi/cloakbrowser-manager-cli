# T16: TUI Modal Screens

## Goal
Modal overlay screens for Create Profile, Edit Profile, Confirm Dialog, and Code Snippet display.

## Files
- `src/cloakbrowser_manager_cli/tui/screens/create_profile.py`
- `src/cloakbrowser_manager_cli/tui/screens/edit_profile.py`
- `src/cloakbrowser_manager_cli/tui/screens/confirm.py`
- `src/cloakbrowser_manager_cli/tui/screens/code_snippet.py`

## create_profile.py

```python
"""Create profile modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch


class CreateProfileScreen(ModalScreen[dict | None]):
    """Modal form for creating a new profile."""

    def __init__(self):
        super().__init__()
        self._result: dict | None = None

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static("[bold]Create Profile[/bold]", id="modal-title")

            yield Label("Name")
            yield Input(placeholder="Profile name", id="name")

            with Horizontal():
                with Vertical():
                    yield Label("Platform")
                    yield Select(
                        [("Windows", "windows"), ("macOS", "macos"), ("Linux", "linux")],
                        value="windows",
                        id="platform",
                    )
                with Vertical():
                    yield Label("Screen")
                    yield Input(placeholder="1920", value="1920", id="screen_width")

            yield Label("Proxy")
            yield Input(placeholder="http://user:pass@host:port or host:port", id="proxy")

            with Horizontal():
                with Vertical():
                    yield Label("Timezone")
                    yield Input(placeholder="America/New_York", id="timezone")
                with Vertical():
                    yield Label("Locale")
                    yield Input(placeholder="en-US", id="locale")

            with Horizontal():
                yield Label("Humanize")
                yield Switch(value=False, id="humanize")
                yield Label("Headless")
                yield Switch(value=False, id="headless")
                yield Label("GeoIP")
                yield Switch(value=False, id="geoip")

            yield Label("Tags (comma-separated)")
            yield Input(placeholder="gmail, work, production", id="tags")

            yield Label("Notes")
            yield Input(placeholder="Optional notes...", id="notes")

            with Horizontal(id="modal-buttons"):
                yield Button("Create", variant="primary", id="btn-create")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            self._result = {
                "name": self.query_one("#name", Input).value.strip(),
                "platform": self.query_one("#platform", Select).value,
                "screen_width": int(self.query_one("#screen_width", Input).value or "1920"),
                "screen_height": 1080,  # fixed for simplicity
                "proxy": self.query_one("#proxy", Input).value.strip() or None,
                "timezone": self.query_one("#timezone", Input).value.strip() or None,
                "locale": self.query_one("#locale", Input).value.strip() or None,
                "humanize": self.query_one("#humanize", Switch).value,
                "headless": self.query_one("#headless", Switch).value,
                "geoip": self.query_one("#geoip", Switch).value,
                "tags": _parse_tags(self.query_one("#tags", Input).value),
                "notes": self.query_one("#notes", Input).value.strip() or None,
            }
            if not self._result["name"]:
                self.notify("Name is required", severity="error")
                return
            self.dismiss(self._result)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


def _parse_tags(raw: str) -> list[dict]:
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    return [{"tag": t} for t in tags]
```

## edit_profile.py

```python
"""Edit profile modal screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, Switch


class EditProfileScreen(ModalScreen[dict | None]):
    """Modal form for editing an existing profile."""

    def __init__(self, profile: dict):
        super().__init__()
        self._profile = profile

    def compose(self) -> ComposeResult:
        p = self._profile
        with Container(id="modal"):
            yield Static(f"[bold]Edit: {p['name']}[/bold]", id="modal-title")

            yield Label("Name")
            yield Input(value=p["name"], id="name")

            with Horizontal():
                with Vertical():
                    yield Label("Platform")
                    yield Select(
                        [("Windows", "windows"), ("macOS", "macos"), ("Linux", "linux")],
                        value=p.get("platform", "windows"),
                        id="platform",
                    )
                with Vertical():
                    yield Label("Screen Width")
                    yield Input(value=str(p.get("screen_width", 1920)), id="screen_width")

            yield Label("Proxy")
            yield Input(value=p.get("proxy") or "", id="proxy", placeholder="http://proxy:8080")

            with Horizontal():
                with Vertical():
                    yield Label("Timezone")
                    yield Input(value=p.get("timezone") or "", id="timezone")
                with Vertical():
                    yield Label("Locale")
                    yield Input(value=p.get("locale") or "", id="locale")

            with Horizontal():
                yield Label("Humanize")
                yield Switch(value=bool(p.get("humanize")), id="humanize")
                yield Label("Headless")
                yield Switch(value=bool(p.get("headless")), id="headless")
                yield Label("GeoIP")
                yield Switch(value=bool(p.get("geoip")), id="geoip")

            yield Label("Notes")
            yield Input(value=p.get("notes") or "", id="notes", placeholder="Optional notes...")

            with Horizontal(id="modal-buttons"):
                yield Button("Save", variant="primary", id="btn-save")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            result = {
                "name": self.query_one("#name", Input).value.strip(),
                "platform": self.query_one("#platform", Select).value,
                "screen_width": int(self.query_one("#screen_width", Input).value or "1920"),
                "proxy": self.query_one("#proxy", Input).value.strip() or None,
                "timezone": self.query_one("#timezone", Input).value.strip() or None,
                "locale": self.query_one("#locale", Input).value.strip() or None,
                "humanize": self.query_one("#humanize", Switch).value,
                "headless": self.query_one("#headless", Switch).value,
                "geoip": self.query_one("#geoip", Switch).value,
                "notes": self.query_one("#notes", Input).value.strip() or None,
            }
            if not result["name"]:
                self.notify("Name is required", severity="error")
                return
            self.dismiss(result)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
```

## confirm.py

```python
"""Confirmation dialog modal."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """Yes/No confirmation dialog."""

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Container(id="modal"):
            yield Static(self._message, id="confirm-message")
            with Horizontal(id="modal-buttons"):
                yield Button("Yes", variant="error", id="btn-yes")
                yield Button("No", variant="default", id="btn-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
```

## code_snippet.py

```python
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
```

## CSS additions (append to styles.css)

```css
#modal {
    width: 60;
    height: auto;
    max-height: 90%;
    background: $surface;
    border: thick $primary;
    padding: 1 2;
    margin: 2 4;
}

#modal-title {
    text-align: center;
    padding-bottom: 1;
    border-bottom: solid $panel;
}

#modal-buttons {
    margin-top: 1;
    align: center middle;
}

#code-block {
    background: $surface-darken-1;
    padding: 1;
    margin: 1 0;
    border: solid $panel;
    overflow: auto;
}

#confirm-message {
    padding: 2;
    text-align: center;
}

Switch {
    margin-right: 2;
}
```

## Notes
- All modal screens extend `ModalScreen` — they overlay on top of the dashboard.
- `CreateProfileScreen` returns `dict` data on success, `None` on cancel.
- `EditProfileScreen` pre-fills form with existing profile data.
- `ConfirmScreen` is a simple yes/no dialog returning `bool`.
- `CodeSnippetScreen` lets user switch between Python/JS/Puppeteer code snippets.
- Escape key dismisses all modals (via `on_key`).

## Verification
```bash
cm tui
# Press 'n' — create profile form appears, fill fields, create
# Press 'e' — edit form appears with existing data
# Press 'd' — confirmation dialog appears
# Press 'c' on a running profile — code snippet screen appears
```
