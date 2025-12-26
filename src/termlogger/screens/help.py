"""Help and splash screens."""

from textual import on
from textual.app import ComposeResult
from textual.containers import Center, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown, Static


HELP_TEXT = """
# TermLogger Help

## Quick Reference

### Key Bindings

| Key | Action |
|-----|--------|
| **Tab** / **Shift+Tab** | Navigate fields |
| **Enter** | Log QSO |
| **F1** | This help screen |
| **F2** | Import ADIF |
| **F3** | Export ADIF |
| **F5** | Lookup callsign |
| **F10** | Exit |
| **Ctrl+N** | Start new operating mode |
| **Ctrl+E** | End current mode |
| **Ctrl+S** | Settings |
| **Ctrl+L** | Log browser |
| **Ctrl+Q** | Quit |

---

## Logging QSOs

1. Enter the **callsign** (auto-converts to uppercase)
2. Enter the **frequency** in MHz (e.g., 14.250)
3. Select the **mode** from dropdown
4. Adjust **RST** if needed (defaults to 59)
5. Press **Enter** to log

The form clears automatically after logging.

---

## Operating Modes

Press **Ctrl+N** to select a mode:

- **General Logging** - Everyday QSO logging
- **POTA Activation** - Activate a park (tracks 10-contact requirement)
- **POTA Hunter** - Hunt park activators (tracks unique parks)
- **Contest** - Contest logging with serial numbers
- **Field Day** - ARRL Field Day with class/section

---

## Spots Table

The spots table shows real-time DX activity.

**Filtering:**
- Click **Band** header to filter by band
- Click **Mode** header to filter by mode
- Active filter shown in bold

**Using Spots:**
- Click any spot to fill frequency/mode in QSO form

---

## Callsign Lookup

Automatic lookup triggers when you tab out of the callsign field.

Configure credentials in **Settings** (Ctrl+S):
- **QRZ.com** - Requires XML subscription
- **HamQTH** - Free registration

---

## Tips

- Keep hands on keyboard for fast logging
- RST defaults to 59 - only change when needed
- Use spots table to quickly tune to active frequencies
- Check the status bar for mode information

---

*Press Escape or click Close to return*
"""


class HelpScreen(ModalScreen[None]):
    """Help screen with documentation."""

    CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 80;
        height: 90%;
        border: thick $primary;
        background: $surface;
    }

    HelpScreen .help-title {
        dock: top;
        height: 3;
        background: $primary;
        color: $text;
        text-align: center;
        text-style: bold;
        padding: 1;
    }

    HelpScreen VerticalScroll {
        height: 1fr;
        padding: 1 2;
    }

    HelpScreen .help-footer {
        dock: bottom;
        height: 3;
        align: center middle;
        padding: 0 1;
    }

    HelpScreen Markdown {
        margin: 0;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("TermLogger Help", classes="help-title")
            with VerticalScroll():
                yield Markdown(HELP_TEXT)
            with Center(classes="help-footer"):
                yield Button("Close", variant="primary", id="close")

    @on(Button.Pressed, "#close")
    def _on_close(self) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)


# ASCII art logo for splash screen
LOGO = r"""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   ████████╗███████╗██████╗ ███╗   ███╗                        ║
║   ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║                        ║
║      ██║   █████╗  ██████╔╝██╔████╔██║                        ║
║      ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║                        ║
║      ██║   ███████╗██║  ██║██║ ╚═╝ ██║                        ║
║      ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝                        ║
║                                                                ║
║   ██╗      ██████╗  ██████╗  ██████╗ ███████╗██████╗          ║
║   ██║     ██╔═══██╗██╔════╝ ██╔════╝ ██╔════╝██╔══██╗         ║
║   ██║     ██║   ██║██║  ███╗██║  ███╗█████╗  ██████╔╝         ║
║   ██║     ██║   ██║██║   ██║██║   ██║██╔══╝  ██╔══██╗         ║
║   ███████╗╚██████╔╝╚██████╔╝╚██████╔╝███████╗██║  ██║         ║
║   ╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚═╝  ╚═╝         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
"""


class SplashScreen(ModalScreen[None]):
    """Splash screen shown on startup."""

    CSS = """
    SplashScreen {
        align: center middle;
        background: $surface 80%;
    }

    SplashScreen > Vertical {
        width: 72;
        height: auto;
        background: $surface;
        border: heavy $primary;
        padding: 1 2;
    }

    SplashScreen .logo {
        width: 100%;
        height: auto;
        color: $primary;
        text-style: bold;
    }

    SplashScreen .version {
        width: 100%;
        text-align: center;
        color: $accent;
        margin-top: 1;
    }

    SplashScreen .tagline {
        width: 100%;
        text-align: center;
        color: $text;
        margin-top: 1;
    }

    SplashScreen .attribution {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-top: 2;
    }

    SplashScreen .company {
        width: 100%;
        text-align: center;
        color: $text-muted;
        text-style: italic;
    }

    SplashScreen .hint {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        margin-top: 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(LOGO, classes="logo")
            yield Static("Version 25.12.01", classes="version")
            yield Static("Terminal-Based Amateur Radio Logging", classes="tagline")
            yield Static("Created by Stacy Lacy", classes="attribution")
            yield Static("Lacy Digital Labs, LLC", classes="company")
            yield Static("Press any key to continue...", classes="hint")

    def on_key(self, event) -> None:
        """Dismiss on any key press."""
        self.dismiss(None)

    def on_click(self, event) -> None:
        """Dismiss on click."""
        self.dismiss(None)
