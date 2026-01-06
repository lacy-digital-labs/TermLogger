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
| **F2** | New mode / End mode (toggle) |
| **F3** | Clear form |
| **F5** | Lookup callsign |
| **F6** | Log manager (export/import/archive) |
| **F7** | Browse log |
| **F9** | Settings |
| **F10** | Exit |
| **Ctrl+E** | Export ADIF (current mode) |
| **Ctrl+I** | Import ADIF |
| **Ctrl+P** | Export POTA log |
| **Ctrl+F** | Manual tune (frequency/mode) |
| **Ctrl+R** | Refresh current field (from rig or PC time/date) |
| **F8** | Read frequency/mode from radio |

### Field Shortcuts

When focused in a field, you can use these shortcuts:

| Key | Action |
|-----|--------|
| **+** / **-** | Increment/decrement value based on cursor position |
| **Ctrl+R** | Refresh from rig (freq/mode) or PC (time/date) |

**Increment/Decrement Behavior:**

- **Frequency**: Cursor on MHz → ±1 MHz, cursor on decimals → ±0.1/0.01/0.001 MHz
- **RST (Sent/Rcvd)**: Cursor on digit → increment/decrement that digit (0-9 with rollover)
- **UTC Time**: Cursor on hours → ±1 hour, cursor on minutes → ±1 minute (rolls over to next/prev day)
- **Date**: Cursor on year → ±1 year, month → ±1 month, day → ±1 day (handles month boundaries)

**Clickable Labels:**

- Click **Freq:** or **Mode:** → Read from radio
- Click **UTC:** or **Date:** → Read current time/date from computer

---

## Logging QSOs

1. Enter the **callsign** (auto-converts to uppercase)
2. Enter the **frequency** in MHz (e.g., 14.250)
3. Select the **mode** from dropdown
4. Adjust **RST** if needed (defaults to 59)
5. Press **Enter** to log

The form clears automatically after logging.
QSOs display most recent first.

---

## Operating Modes

Press **F2** to select a mode. Press **F2** again to end the current mode.

- **General Logging** - Everyday QSO logging
- **POTA Activation** - Activate a park (tracks 10-contact requirement)
- **POTA Hunter** - Hunt park activators (tracks unique parks)
- **Contest** - Contest logging with serial numbers
- **Field Day** - ARRL Field Day with class/section

---

## Log Manager (F6)

Manage virtual logs for different activations and events.

**Features:**
- **Active/Archived tabs** - Switch between current and archived logs
- **New log** - Create a new log for an activation or event
- **Select log** - Set the active log for QSO entry
- **Export** - Export log as ADIF, POTA, or Cabrillo format
- **Exp All** - Export ALL QSOs to ADIF for full backup
- **Import** - Import ADIF file into a new log
- **QRZ Upload** - Upload QSOs to QRZ Logbook
- **QRZ Download** - Download QSOs from QRZ Logbook
- **Club Log** - Upload QSOs to Club Log
- **Archive** - Archive old logs to keep them organized

---

## QRZ Logbook Sync

Sync your QSOs with QRZ.com Logbook for backup and sharing.

**Requirements:**
- QRZ Logbook API key (requires QRZ subscription)
- Configure API key in **Settings** (F9) → **Lookup** tab

**Upload:**
1. Open Log Manager (F6)
2. Select the log to upload
3. Click **QRZ Upload**
4. Only new QSOs (not previously uploaded) are sent

**Download:**
1. Open Log Manager (F6)
2. Select the log to import into
3. Click **QRZ Download**
4. Duplicate QSOs are automatically skipped

---

## Club Log Upload

Upload your QSOs to Club Log for DXCC tracking and statistics.

**Requirements:**
- Club Log API key (request from helpdesk)
- Email, application password, and callsign
- Configure in **Settings** (F9) → **Lookup** tab

**Upload:**
1. Open Log Manager (F6)
2. Select the log to upload
3. Click **Club Log**
4. Only new QSOs (not previously uploaded) are sent

---

## Spots Table

The spots table shows real-time DX and POTA activity.
Spots are sorted by frequency for easy band scanning.

**Filtering:**
- Click **Band** button to filter by band
- Click **Mode** button to filter by mode
- Active filter shown in bold

**Using Spots:**
- Click any spot to fill callsign/frequency in QSO form
- For POTA spots: park info (name, location, grid) is displayed
- Auto-QSY: radio changes frequency when clicking spot (if enabled)

---

## Callsign Lookup

Automatic lookup triggers when you tab out of the callsign field.

Configure credentials in **Settings** (F9):
- **QRZ.com** - Requires XML subscription
- **HamQTH** - Free registration

---

## Rig Control

Connect TermLogger to your radio for automatic tracking and QSY control.

**Supported Backends:**
- **Hamlib (rigctld)** - 200+ radios via TCP
- **Flex Radio** - SmartSDR API via network

**Features:**
- Band indicator shows current frequency/band
- Frequency updates when tabbing to frequency field
- Auto-QSY: click a spot to change radio frequency
- Manual tune: press **Ctrl+F** to change frequency/mode

**Setup:**
1. Go to **Settings** (F9) → **Rig** tab
2. Select control type (rigctld or Flex Radio)
3. Enter host/port settings
4. Enable Auto-QSY if desired

**rigctld Example:**
```
rigctld -m 3073 -r /dev/ttyUSB0
```

---

## Tips

- Keep hands on keyboard for fast logging
- RST defaults to 59 - only change when needed
- Use spots table to quickly tune to active frequencies
- Check the status bar for mode information
- Use Log Manager (F6) to organize different activations

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
        padding: 0 2;
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
    }

    SplashScreen .tagline {
        width: 100%;
        text-align: center;
        color: $text;
    }

    SplashScreen .attribution {
        width: 100%;
        text-align: center;
        color: $text-muted;
    }

    SplashScreen .company {
        width: 100%;
        text-align: center;
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }

    SplashScreen .hint {
        width: 100%;
        text-align: center;
        color: $text-disabled;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(LOGO, classes="logo")
            yield Static("Version 26.01.02", classes="version")
            yield Static("Terminal-Based Amateur Radio Logging", classes="tagline")
            yield Static("Lacy Digital Labs, LLC", classes="company")
            yield Static("Created by Stacy Lacy, NQ0S", classes="attribution")
            yield Static("Contributor: Jon Lacy, KD5RYN", classes="attribution")
            yield Static("Press any key to continue...", classes="hint")

    def on_key(self, event) -> None:
        """Dismiss on any key press."""
        self.dismiss(None)

    def on_click(self, event) -> None:
        """Dismiss on click."""
        self.dismiss(None)
