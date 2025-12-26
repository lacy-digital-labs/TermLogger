"""Main logging screen."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Input, Static
from textual.worker import Worker, get_current_worker

from ..adif import export_adif_file, parse_adif_file
from ..callsign import CallsignLookupService, LookupError
from ..database import Database
from ..models import CallsignLookupResult, QSO
from ..modes import (
    ContestMode,
    FieldDayMode,
    ModeType,
    OperatingMode,
    POTAMode,
)
from ..widgets.qso_entry import QSOEntryForm
from ..widgets.qso_table import QSOTable
from .file_picker import ExportCompleteScreen, FilePickerScreen
from .log_browser import LogBrowserScreen
from .mode_setup import (
    ContestSetupScreen,
    FieldDaySetupScreen,
    ModeSelectScreen,
    POTASetupScreen,
)
from .settings import SettingsScreen


class CallsignInfo(Static):
    """Widget to display callsign lookup information."""

    DEFAULT_CSS = """
    CallsignInfo {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, id: Optional[str] = None) -> None:
        super().__init__(id=id)
        self._info = ""

    def set_info(self, info: str) -> None:
        """Set the callsign info text."""
        self._info = info
        self.update(f"[bold]Callsign Info:[/bold] {info}")

    def clear(self) -> None:
        """Clear the callsign info."""
        self._info = ""
        self.update("[dim]Callsign lookup: Enter a callsign to search...[/dim]")


class BandIndicator(Static):
    """Widget to display current band/mode/frequency."""

    DEFAULT_CSS = """
    BandIndicator {
        width: 100%;
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    def set_band_info(self, freq: float, mode: str, band: str) -> None:
        """Set the band indicator display."""
        self.update(f"[bold cyan]{freq:.3f} MHz[/bold cyan] | [green]{mode}[/green] | [yellow]{band}[/yellow]")


class UTCClock(Static):
    """Widget to display current UTC time."""

    DEFAULT_CSS = """
    UTCClock {
        width: auto;
        height: 1;
        padding: 0 1;
        text-align: right;
        color: $text;
        text-style: bold;
    }
    """

    def on_mount(self) -> None:
        """Start the clock update interval."""
        self._update_time()
        self.set_interval(1.0, self._update_time)

    def _update_time(self) -> None:
        """Update the displayed time."""
        now = datetime.now(timezone.utc)
        self.update(f"[yellow]UTC[/yellow] [bold white]{now.strftime('%H:%M:%S')}[/bold white] [dim]{now.strftime('%Y-%m-%d')}[/dim]")


class AppHeader(Static):
    """Custom application header with title and UTC clock."""

    DEFAULT_CSS = """
    AppHeader {
        width: 100%;
        height: 1;
        background: $primary;
        color: $text;
        layout: horizontal;
    }

    AppHeader .header-title {
        width: 1fr;
        height: 1;
        padding: 0 1;
        text-style: bold;
    }

    AppHeader .header-clock {
        width: auto;
        height: 1;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("[bold]TermLogger[/bold] - Amateur Radio Logger", classes="header-title")
        yield Static("", id="header-clock", classes="header-clock")

    def on_mount(self) -> None:
        """Start the clock update interval."""
        self._update_time()
        self.set_interval(1.0, self._update_time)

    def _update_time(self) -> None:
        """Update the displayed time."""
        now = datetime.now(timezone.utc)
        clock = self.query_one("#header-clock", Static)
        clock.update(f"[yellow]UTC {now.strftime('%H:%M:%S')}[/yellow] {now.strftime('%Y-%m-%d')}")


class StatusBar(Static):
    """Widget for status bar at bottom."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        dock: bottom;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    def set_qso_count(self, count: int) -> None:
        """Set the QSO count display."""
        self.update(f"QSOs: {count}")


class ModeStatus(Static):
    """Widget to display current operating mode status."""

    DEFAULT_CSS = """
    ModeStatus {
        height: 1;
        padding: 0 1;
        background: $surface-darken-1;
    }
    """

    def __init__(self, id: Optional[str] = None) -> None:
        super().__init__(id=id)
        self._mode: Optional[OperatingMode] = None

    def set_mode(self, mode: Optional[OperatingMode]) -> None:
        """Set the current operating mode."""
        self._mode = mode
        self._update_display()

    def _update_display(self) -> None:
        """Update the mode status display."""
        if self._mode is None:
            self.update("[dim]Mode: General Logging | Ctrl+N to start a contest/activation[/dim]")
        else:
            status = self._mode.get_status_text()
            self.update(f"[bold cyan]{status}[/bold cyan]")

    def refresh_status(self) -> None:
        """Refresh the status display."""
        self._update_display()


class MainScreen(Screen):
    """Main logging screen."""

    BINDINGS = [
        ("f1", "show_help", "Help"),
        ("f2", "export_adif", "Export"),
        ("f3", "clear_form", "Clear"),
        ("f4", "show_settings", "Settings"),
        ("f5", "lookup_callsign", "Lookup"),
        ("f7", "browse_log", "Browse"),
        ("f8", "export_cabrillo", "Cabrillo"),
        ("f9", "end_mode", "End Mode"),
        ("f10", "quit", "Exit"),
        ("ctrl+n", "new_contest", "New Contest"),
        ("ctrl+e", "export_adif", "Export ADIF"),
        ("ctrl+i", "import_adif", "Import ADIF"),
    ]

    CSS = """
    MainScreen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto auto 1fr auto;
    }

    .main-container {
        height: 100%;
        padding: 0 1;
    }
    """

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._current_mode: Optional[OperatingMode] = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield AppHeader(id="app-header")

        with Vertical(classes="main-container"):
            # Band/mode indicator
            yield BandIndicator(id="band-indicator")

            # Operating mode status
            yield ModeStatus(id="mode-status")

            # QSO entry form
            yield QSOEntryForm(id="qso-form")

            # Callsign lookup info
            yield CallsignInfo(id="callsign-info")

            # QSO table
            yield QSOTable(id="qso-table")

        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen when mounted."""
        # Load recent QSOs
        qsos = self.db.get_recent_qsos(50)
        self.query_one(QSOTable).load_qsos(qsos)

        # Update status bar
        count = self.db.get_qso_count()
        self.query_one(StatusBar).set_qso_count(count)

        # Initialize callsign info
        self.query_one(CallsignInfo).clear()

        # Set initial band indicator
        self.query_one(BandIndicator).set_band_info(14.250, "SSB", "20m")

    def on_qso_entry_form_qso_logged(self, event: QSOEntryForm.QSOLogged) -> None:
        """Handle QSO logged event."""
        # If in a mode, set exchange sent
        if self._current_mode:
            event.qso.exchange_sent = self._current_mode.format_exchange_sent()

        # Save to database
        qso_id = self.db.add_qso(event.qso)
        event.qso.id = qso_id

        # Add to current mode if active
        if self._current_mode:
            self._current_mode.add_qso(event.qso)
            self.query_one(ModeStatus).refresh_status()

        # Add to table
        self.query_one(QSOTable).add_qso(event.qso)

        # Update status
        count = self.db.get_qso_count()
        self.query_one(StatusBar).set_qso_count(count)

        # Clear callsign info
        self.query_one(CallsignInfo).clear()

        self.notify(f"Logged {event.qso.callsign}", timeout=2)

    def on_qso_entry_form_callsign_changed(
        self, event: QSOEntryForm.CallsignChanged
    ) -> None:
        """Handle callsign change for dupe checking and lookup."""
        # Check for dupes
        is_dupe = self.db.check_dupe(event.callsign)
        self.query_one(QSOEntryForm).set_dupe_status(is_dupe)

        # Trigger callsign lookup if auto-lookup is enabled
        if len(event.callsign) >= 3 and self.app.config.auto_lookup:
            self._do_lookup(event.callsign)

    def _do_lookup(self, callsign: str) -> None:
        """Perform async callsign lookup."""
        callsign_info = self.query_one(CallsignInfo)
        callsign_info.set_info(f"Looking up {callsign}...")

        # Cancel any pending lookup
        self._cancel_lookup()

        # Start new lookup worker
        self._lookup_worker = self.run_worker(
            self._lookup_callsign_async(callsign),
            name=f"lookup_{callsign}",
            exclusive=True,
        )

    async def _lookup_callsign_async(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Async worker to perform callsign lookup."""
        try:
            result = await self.app.lookup_service.lookup(callsign)
            return result
        except LookupError as e:
            return None

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle lookup worker completion."""
        if event.worker.name and event.worker.name.startswith("lookup_"):
            if event.state == event.worker.StateEnum.SUCCESS:
                result = event.worker.result
                callsign_info = self.query_one(CallsignInfo)
                if result:
                    callsign_info.set_info(result.display_str)
                else:
                    callsign_info.set_info("No information found")
            elif event.state == event.worker.StateEnum.ERROR:
                self.query_one(CallsignInfo).set_info("Lookup failed")

    def _cancel_lookup(self) -> None:
        """Cancel any pending lookup."""
        if hasattr(self, "_lookup_worker") and self._lookup_worker:
            self._lookup_worker.cancel()

    def action_show_help(self) -> None:
        """Show help screen."""
        self.notify("F1=Help F2=Export F3=Clear F4=Settings F5=Lookup F7=Browse F8=Cabrillo F9=EndMode F10=Exit | Ctrl+N=New Mode")

    def action_clear_form(self) -> None:
        """Clear the QSO entry form."""
        self.query_one(QSOEntryForm).clear_form()
        self.query_one(CallsignInfo).clear()

    def action_lookup_callsign(self) -> None:
        """Trigger manual callsign lookup."""
        # Get current callsign from form
        try:
            callsign_input = self.query_one("#callsign", Input)
            callsign = callsign_input.value.strip().upper()
            if callsign:
                self._do_lookup(callsign)
            else:
                self.notify("Enter a callsign first", severity="warning")
        except Exception:
            self.notify("Enter a callsign first", severity="warning")

    def action_show_settings(self) -> None:
        """Show settings screen."""
        self.app.push_screen(SettingsScreen(self.app.config))

    def action_browse_log(self) -> None:
        """Show log browser screen."""

        def on_browser_close() -> None:
            # Refresh the table when returning from browser
            recent_qsos = self.db.get_recent_qsos(50)
            self.query_one(QSOTable).load_qsos(recent_qsos)
            count = self.db.get_qso_count()
            self.query_one(StatusBar).set_qso_count(count)

        self.app.push_screen(LogBrowserScreen(self.db), on_browser_close)

    def action_export_adif(self) -> None:
        """Export log to ADIF."""
        # Generate default filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        default_filename = f"termlogger_export_{timestamp}.adi"

        def handle_export(path: Optional[Path]) -> None:
            if path is None:
                return

            try:
                # Get all QSOs from database
                qsos = self.db.get_all_qsos(limit=10000)
                count = export_adif_file(qsos, path)
                self.app.push_screen(
                    ExportCompleteScreen(f"Exported {count} QSOs to:\n{path}")
                )
            except Exception as e:
                self.notify(f"Export failed: {e}", severity="error")

        self.app.push_screen(
            FilePickerScreen(
                title="Export ADIF",
                start_path=Path.home(),
                extensions=[".adi", ".adif"],
                save_mode=True,
                default_filename=default_filename,
            ),
            handle_export,
        )

    def action_import_adif(self) -> None:
        """Import ADIF file."""

        def handle_import(path: Optional[Path]) -> None:
            if path is None:
                return

            try:
                qsos = parse_adif_file(path)
                imported_count = 0

                for qso in qsos:
                    self.db.add_qso(qso)
                    imported_count += 1

                # Refresh the table
                recent_qsos = self.db.get_recent_qsos(50)
                self.query_one(QSOTable).load_qsos(recent_qsos)

                # Update status
                count = self.db.get_qso_count()
                self.query_one(StatusBar).set_qso_count(count)

                self.app.push_screen(
                    ExportCompleteScreen(f"Imported {imported_count} QSOs from:\n{path}")
                )
            except FileNotFoundError:
                self.notify("File not found", severity="error")
            except Exception as e:
                self.notify(f"Import failed: {e}", severity="error")

        self.app.push_screen(
            FilePickerScreen(
                title="Import ADIF",
                start_path=Path.home(),
                extensions=[".adi", ".adif"],
                save_mode=False,
            ),
            handle_import,
        )

    def action_new_contest(self) -> None:
        """Start a new contest or operating mode."""

        def handle_mode_select(mode_type: Optional[ModeType]) -> None:
            if mode_type is None:
                return

            if mode_type == ModeType.GENERAL:
                # Clear current mode, return to general logging
                self._current_mode = None
                self.query_one(ModeStatus).set_mode(None)
                self.notify("Switched to General Logging")
            elif mode_type == ModeType.CONTEST:
                # Show contest setup
                self.app.push_screen(
                    ContestSetupScreen(
                        my_callsign=self.app.config.my_callsign,
                        my_exchange=self.app.config.my_cq_zone or "",
                    ),
                    handle_contest_setup,
                )
            elif mode_type == ModeType.POTA:
                # Show POTA setup
                self.app.push_screen(
                    POTASetupScreen(
                        my_callsign=self.app.config.my_callsign,
                        my_state=self.app.config.my_state or "",
                        my_grid=self.app.config.my_grid or "",
                    ),
                    handle_pota_setup,
                )
            elif mode_type == ModeType.FIELDDAY:
                # Show Field Day setup
                self.app.push_screen(
                    FieldDaySetupScreen(my_callsign=self.app.config.my_callsign),
                    handle_fieldday_setup,
                )

        def handle_contest_setup(mode: Optional[ContestMode]) -> None:
            if mode:
                self._current_mode = mode
                self.query_one(ModeStatus).set_mode(mode)
                self.notify(f"Started {mode.config.contest_name}")

        def handle_pota_setup(mode: Optional[POTAMode]) -> None:
            if mode:
                self._current_mode = mode
                self.query_one(ModeStatus).set_mode(mode)
                parks = ", ".join(mode.get_all_parks())
                self.notify(f"Started POTA activation: {parks}")

        def handle_fieldday_setup(mode: Optional[FieldDayMode]) -> None:
            if mode:
                self._current_mode = mode
                self.query_one(ModeStatus).set_mode(mode)
                self.notify(f"Started Field Day: {mode.config.my_class} {mode.config.my_section}")

        self.app.push_screen(ModeSelectScreen(), handle_mode_select)

    def action_end_mode(self) -> None:
        """End the current operating mode."""
        if self._current_mode is None:
            self.notify("No active mode to end", severity="warning")
            return

        mode_name = self._current_mode.name or "Mode"
        score = self._current_mode.calculate_score()
        self._current_mode = None
        self.query_one(ModeStatus).set_mode(None)
        self.notify(f"Ended {mode_name} - Final score: {score.total_score}")

    def action_export_cabrillo(self) -> None:
        """Export log in Cabrillo format."""
        if self._current_mode is None:
            self.notify("No active contest mode for Cabrillo export", severity="warning")
            return

        # Generate default filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        mode_name = self._current_mode.mode_type.value
        default_filename = f"termlogger_{mode_name}_{timestamp}.log"

        def handle_export(path: Optional[Path]) -> None:
            if path is None or self._current_mode is None:
                return

            try:
                cabrillo_content = self._current_mode.export_cabrillo()
                path.write_text(cabrillo_content)
                score = self._current_mode.calculate_score()
                self.app.push_screen(
                    ExportCompleteScreen(
                        f"Exported Cabrillo log to:\n{path}\n\n"
                        f"QSOs: {score.qso_count}\n"
                        f"Score: {score.total_score}"
                    )
                )
            except Exception as e:
                self.notify(f"Export failed: {e}", severity="error")

        self.app.push_screen(
            FilePickerScreen(
                title="Export Cabrillo",
                start_path=Path.home(),
                extensions=[".log", ".cbr"],
                save_mode=True,
                default_filename=default_filename,
            ),
            handle_export,
        )

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
