"""Main logging screen."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Focus
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import Footer, Input, Select, Static
from textual.worker import Worker, WorkerState

from ..adif import export_adif_file, export_pota_adif, get_pota_filename, parse_adif_file
from ..callsign import LookupError
from ..config import DXClusterSource, RigControlType
from ..database import Database
from ..models import CallsignLookupResult, QSO, Spot, format_frequency
from ..modes import (
    ContestMode,
    FieldDayMode,
    ModeType,
    OperatingMode,
    POTAMode,
)
from ..services import (
    DXClusterService,
    FlexRadioService,
    FlexState,
    Park,
    POTAParksService,
    POTASpotService,
    RigctldService,
    RigState,
    UDPLogServer,
)
from ..widgets.qso_entry import QSOEntryForm
from ..widgets.qso_table import QSOTable
from ..widgets.spots_table import SpotsTable
from ..widgets.tune_dialog import ManualTuneModal
from .file_picker import ExportCompleteScreen, FilePickerScreen
from .log_browser import LogBrowserScreen
from .mode_setup import (
    ContestSetupScreen,
    FieldDaySetupScreen,
    ModeSelectScreen,
    POTAHunterSetupScreen,
    POTASetupScreen,
)
from .help import HelpScreen
from .log_manager import LogManagerScreen
from .settings import SettingsScreen

logger = logging.getLogger(__name__)


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

    def set_band_info(self, freq: float, mode: str, band: str, rig_error: bool = False) -> None:
        """Set the band indicator display.

        Args:
            freq: Frequency in MHz
            mode: Operating mode
            band: Band designation
            rig_error: If True, show rig control error indicator
        """
        base = f"[bold cyan]{format_frequency(freq)} MHz[/bold cyan] | [green]{mode}[/green] | [yellow]{band}[/yellow]"
        if rig_error:
            self.update(f"{base} | [red bold]⚠ RIG ERROR[/red bold]")
        else:
            self.update(base)


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


class LogStatus(Static):
    """Widget to display current active log."""

    DEFAULT_CSS = """
    LogStatus {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self, id: Optional[str] = None) -> None:
        super().__init__(id=id)
        self._log_name: Optional[str] = None
        self._qso_count: int = 0

    def set_log(self, name: Optional[str], qso_count: int = 0) -> None:
        """Set the current log display."""
        self._log_name = name
        self._qso_count = qso_count
        self._update_display()

    def _update_display(self) -> None:
        """Update the log status display."""
        if self._log_name is None:
            self.update("[dim]Log: All QSOs | F6 to manage logs[/dim]")
        else:
            self.update(f"[bold green]Log:[/bold green] {self._log_name} [dim]({self._qso_count} QSOs)[/dim] | [dim]F6 to change[/dim]")


class MainScreen(Screen):
    """Main logging screen."""

    BINDINGS = [
        ("f1", "show_help", "Help"),
        ("f2", "toggle_mode", "Mode"),
        ("f3", "clear_form", "Clear"),
        ("f5", "lookup_callsign", "Lookup"),
        ("f6", "manage_logs", "Logs"),
        ("f7", "browse_log", "Browse"),
        ("f8", "read_from_rig", "Read Rig"),
        ("f9", "show_settings", "Settings"),
        ("f10", "quit", "Exit"),
        ("ctrl+e", "export_adif", "Export ADIF"),
        ("ctrl+i", "import_adif", "Import ADIF"),
        ("ctrl+p", "export_pota", "Export POTA"),
        ("ctrl+f", "manual_tune", "Tune"),
        ("ctrl+r", "refresh_current_field", "Refresh"),
        ("b", "cycle_band_filter", "Cycle Band"),
        ("m", "cycle_mode_filter", "Cycle Mode"),
        ("c", "clear_spot_filters", "Clear Filters"),
    ]

    CSS = """
    MainScreen {
        layout: vertical;
    }

    .main-container {
        height: 1fr;
        padding: 0 1;
    }

    #tables-container {
        height: 1fr;
        min-height: 10;
        width: 100%;
    }

    #spots-table {
        width: 2fr;
    }

    #qso-table {
        width: 3fr;
    }
    """

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._current_mode: Optional[OperatingMode] = None
        self._active_log_id: Optional[int] = None
        self._spot_timer: Optional[Timer] = None
        self._pota_spot_service: Optional[POTASpotService] = None
        self._pota_parks_service: Optional[POTAParksService] = None
        self._dx_cluster_service: Optional[DXClusterService] = None
        self._rigctld_service: Optional[RigctldService] = None
        self._flexradio_service: Optional[FlexRadioService] = None
        self._rig_poll_timer: Optional[Timer] = None
        self._rig_has_error = False  # Track if rig control is failing
        self._udp_log_server: Optional[UDPLogServer] = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield AppHeader(id="app-header")

        with Vertical(classes="main-container"):
            # Band/mode indicator
            yield BandIndicator(id="band-indicator")

            # Current log status
            yield LogStatus(id="log-status")

            # Operating mode status
            yield ModeStatus(id="mode-status")

            # QSO entry form
            yield QSOEntryForm(id="qso-form")

            # Callsign lookup info
            yield CallsignInfo(id="callsign-info")

            # Tables container (Spots table + QSO table)
            with Horizontal(id="tables-container"):
                yield SpotsTable(id="spots-table", title="DX Spots")
                yield QSOTable(id="qso-table")

        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize screen when mounted."""
        # Load active log
        self._load_active_log()

        # Load recent QSOs (filtered by active log if set)
        self._refresh_qso_table()

        # Initialize callsign info
        self.query_one(CallsignInfo).clear()

        # Set initial band indicator from form
        self._update_band_indicator_from_form()

        # Initialize spot services
        self._pota_spot_service = POTASpotService()
        self._pota_parks_service = POTAParksService()
        self._dx_cluster_service = DXClusterService(
            host=self.app.config.dx_cluster_host,
            port=self.app.config.dx_cluster_port,
            callsign=self.app.config.dx_cluster_callsign or self.app.config.my_callsign,
        )

        # Start spot refresh based on current mode
        self._start_spot_refresh()

        # Initialize rig control service based on type
        rig_type = self.app.config.rig_control_type
        if rig_type == RigControlType.RIGCTLD:
            self._rigctld_service = RigctldService(
                host=self.app.config.rigctld_host,
                port=self.app.config.rigctld_port,
                on_state_change=self._on_rig_state_change,
            )
            self._start_rig_polling()
        elif rig_type == RigControlType.FLEXRADIO:
            self._flexradio_service = FlexRadioService(
                host=self.app.config.flexradio_host,
                port=self.app.config.flexradio_port,
                on_state_change=self._on_flex_state_change,
            )
            self._start_rig_polling()

        # Initialize UDP log server if enabled
        if self.app.config.udp_log_server_enabled:
            self._udp_log_server = UDPLogServer(
                host=self.app.config.udp_log_server_host,
                port=self.app.config.udp_log_server_port,
                on_qso_received=self._on_udp_qso_received,
            )
            # Start the server
            self.run_worker(self._start_udp_server(), exclusive=False, name="udp_server")

    def _load_active_log(self) -> None:
        """Load the active log from database."""
        active_log = self.db.get_active_log()
        if active_log:
            self._active_log_id = active_log.id
            self.query_one(LogStatus).set_log(active_log.display_name, active_log.qso_count)
        else:
            self._active_log_id = None
            self.query_one(LogStatus).set_log(None)

    def _refresh_qso_table(self) -> None:
        """Refresh the QSO table with current log filter."""
        qsos = self.db.get_recent_qsos(50, log_id=self._active_log_id)
        self.query_one(QSOTable).load_qsos(qsos)

        # Update status bar with count
        count = self.db.get_qso_count(log_id=self._active_log_id)
        self.query_one(StatusBar).set_qso_count(count)

    # Rig control methods
    def _start_rig_polling(self) -> None:
        """Start polling the rig for frequency/mode changes."""
        self._stop_rig_polling()
        rig_type = self.app.config.rig_control_type
        if rig_type != RigControlType.NONE and (self._rigctld_service or self._flexradio_service):
            interval = self.app.config.rig_poll_interval
            self._rig_poll_timer = self.set_interval(interval, self._poll_rig)
            # Do initial poll
            self.run_worker(self._do_rig_poll(), exclusive=True, name="rig_poll", group="rig")

    def _stop_rig_polling(self) -> None:
        """Stop rig polling."""
        if self._rig_poll_timer:
            self._rig_poll_timer.stop()
            self._rig_poll_timer = None

    def _poll_rig(self) -> None:
        """Trigger a rig poll."""
        self.run_worker(self._do_rig_poll(), exclusive=True, name="rig_poll", group="rig")

    async def _do_rig_poll(self) -> None:
        """Async worker to poll rig state."""
        state = None

        if self._rigctld_service:
            state = await self._rigctld_service.poll()
        elif self._flexradio_service:
            state = await self._flexradio_service.poll()

        # Handle rig errors - fall back to form display
        if state is None:
            # Rig poll failed - show form data with error indicator
            if not self._rig_has_error:
                # First error - log it
                logger.warning("Rig control poll failed - falling back to form display")
                self._rig_has_error = True
            # Update display from form with error indicator (thread-safe)
            self.app.call_later(self._update_band_indicator_from_form, True)
        else:
            # Rig poll succeeded - clear error flag if it was set
            if self._rig_has_error:
                logger.info("Rig control recovered")
                self._rig_has_error = False
            # Callbacks will handle display update with rig data

    def _on_rig_state_change(self, state: RigState) -> None:
        """Handle rigctld state change callback - update UI."""
        # Use call_later for thread-safe UI update
        self.app.call_later(self._update_rigctld_display, state)

    def _on_flex_state_change(self, state: FlexState) -> None:
        """Handle Flex Radio state change callback - update UI."""
        logger.debug(f"Flex state change: {state.frequency_mhz:.3f} MHz {state.mode}")
        # Use call_later for thread-safe UI update
        self.app.call_later(self._update_flex_display, state)

    def _update_rigctld_display(self, state: RigState) -> None:
        """Update UI with new rigctld state."""
        try:
            # Update band indicator only - don't overwrite QSO form
            # User-initiated actions (spot clicks) should control the form
            band_indicator = self.query_one(BandIndicator)
            band_str = state.band or "?"
            mapped_mode = RigctldService.map_mode_from_rigctld(state.mode)
            band_indicator.set_band_info(state.frequency_mhz, mapped_mode, band_str)
        except Exception as e:
            logger.warning(f"Failed to update rig display: {e}")

    def _update_flex_display(self, state: FlexState) -> None:
        """Update UI with new Flex Radio state."""
        try:
            # Update band indicator only - don't overwrite QSO form
            # User-initiated actions (spot clicks) should control the form
            band_indicator = self.query_one(BandIndicator)
            band_str = state.band or "?"
            mapped_mode = FlexRadioService.map_mode_from_flex(state.mode)
            logger.debug(f"Flex display update: {state.frequency_mhz:.3f} MHz {mapped_mode} ({band_str})")
            band_indicator.set_band_info(state.frequency_mhz, mapped_mode, band_str)
        except Exception as e:
            logger.warning(f"Failed to update Flex display: {e}")

    def _update_band_indicator_from_form(self, show_error: bool = False) -> None:
        """Update band indicator from QSO form values (fallback when rig fails).

        Args:
            show_error: If True, show rig control error indicator
        """
        try:
            # Read frequency from form
            freq_input = self.query_one("#frequency", Input)
            freq_str = freq_input.value.strip()
            freq = float(freq_str) if freq_str else 14.250

            # Read mode from form
            form = self.query_one(QSOEntryForm)
            mode_select = form.query_one("#mode", Select)
            mode = mode_select.value if mode_select.value else "SSB"

            # Calculate band from frequency
            from ..models import frequency_to_band
            band_enum = frequency_to_band(freq)
            band_str = band_enum.value if band_enum else "?"

            # Update display with error flag if needed
            band_indicator = self.query_one(BandIndicator)
            band_indicator.set_band_info(freq, mode, band_str, rig_error=show_error)
            logger.debug(f"Updated band indicator from form: {freq:.3f} MHz {mode} ({band_str}){' [ERROR]' if show_error else ''}")
        except Exception as e:
            logger.warning(f"Failed to update band indicator from form: {e}")

    def on_focus(self, event: Focus) -> None:
        """Handle focus events - update frequency from rig when frequency field focused."""
        # Check if the focused widget is the frequency input
        # Try multiple ways to get the focused widget ID
        widget_id = None
        if hasattr(event, "widget"):
            widget_id = getattr(event.widget, "id", None)
        elif hasattr(event, "control"):
            widget_id = getattr(event.control, "id", None)

        if widget_id == "frequency":
            self._update_frequency_from_rig()

    def _update_frequency_from_rig(self) -> None:
        """Update the frequency field from the current rig state."""
        rig_type = self.app.config.rig_control_type
        freq_mhz = 0.0
        mode = None

        if rig_type == RigControlType.RIGCTLD and self._rigctld_service:
            state = self._rigctld_service.last_state
            if state:
                freq_mhz = state.frequency_mhz
                mode = RigctldService.map_mode_from_rigctld(state.mode)
        elif rig_type == RigControlType.FLEXRADIO and self._flexradio_service:
            state = self._flexradio_service.last_state
            if state and state.frequency > 0:
                freq_mhz = state.frequency_mhz
                mode = FlexRadioService.map_mode_from_flex(state.mode)

        if freq_mhz > 0:
            try:
                form = self.query_one(QSOEntryForm)
                form.set_frequency(freq_mhz)
                logger.debug(f"Updated frequency from rig: {freq_mhz:.3f} MHz")
                if mode:
                    try:
                        form.set_mode(mode)
                    except (ValueError, KeyError):
                        pass
            except Exception as e:
                logger.warning(f"Failed to update frequency from rig: {e}")

    async def on_unmount(self) -> None:
        """Clean up when screen is unmounted."""
        self._stop_spot_refresh()
        self._stop_rig_polling()
        if self._pota_spot_service:
            await self._pota_spot_service.close()
        if self._pota_parks_service:
            await self._pota_parks_service.close()
        if self._dx_cluster_service:
            await self._dx_cluster_service.close()
        if self._rigctld_service:
            await self._rigctld_service.close()
        if self._flexradio_service:
            await self._flexradio_service.close()
        if self._udp_log_server:
            await self._udp_log_server.stop()

    # UDP Log Server methods
    async def _start_udp_server(self) -> None:
        """Start the UDP log server."""
        if self._udp_log_server:
            try:
                await self._udp_log_server.start()
                logger.info(
                    f"UDP log server started on {self.app.config.udp_log_server_host}:"
                    f"{self.app.config.udp_log_server_port}"
                )
            except Exception as e:
                logger.error(f"Failed to start UDP log server: {e}")
                self.notify(
                    f"UDP log server failed to start: {e}",
                    severity="error",
                    timeout=10,
                )

    def _on_udp_qso_received(self, qso: QSO, source: str) -> None:
        """Handle QSO received from UDP log server.

        Args:
            qso: The QSO record received
            source: Source description (e.g., "WSJT-X", "ADIF")
        """
        try:
            # Set log_id if we have an active log
            if self._active_log_id:
                qso.log_id = self._active_log_id

            # Add to database
            qso_id = self.db.add_qso(qso)
            logger.info(f"Added UDP QSO from {source}: {qso.callsign} (ID: {qso_id})")

            # Refresh QSO table
            self._refresh_qso_table()

            # Show notification if enabled
            if self.app.config.udp_log_server_notify:
                self.notify(
                    f"Logged {qso.callsign} from {source} on {format_frequency(qso.frequency)} MHz",
                    severity="information",
                    timeout=5,
                )

        except Exception as e:
            logger.error(f"Failed to add UDP QSO: {e}", exc_info=True)
            self.notify(f"Failed to log UDP QSO: {e}", severity="error", timeout=10)

    def _start_spot_refresh(self) -> None:
        """Start the spot refresh timer based on current mode."""
        self._stop_spot_refresh()

        # Determine refresh interval based on mode
        spots_table = self.query_one(SpotsTable)
        if self._current_mode and self._current_mode.mode_type == ModeType.POTA:
            if self.app.config.pota_spots_enabled:
                interval = self.app.config.pota_spots_refresh_seconds
                self._spot_timer = self.set_interval(interval, self._refresh_pota_spots)
                spots_table.set_title("POTA Spots")
                spots_table.reset_filters()  # Reset filters when switching sources
                # Do initial fetch
                self.run_worker(self._fetch_pota_spots(), exclusive=True)
        else:
            if self.app.config.dx_cluster_enabled:
                interval = self.app.config.dx_cluster_refresh_seconds
                self._spot_timer = self.set_interval(interval, self._refresh_dx_spots)
                spots_table.set_title("DX Spots")
                spots_table.reset_filters()  # Reset filters when switching sources
                # Do initial fetch
                self.run_worker(self._fetch_dx_spots(), exclusive=True)

    def _stop_spot_refresh(self) -> None:
        """Stop the spot refresh timer."""
        if self._spot_timer:
            self._spot_timer.stop()
            self._spot_timer = None

    def _refresh_pota_spots(self) -> None:
        """Trigger POTA spots refresh."""
        self.run_worker(self._fetch_pota_spots(), exclusive=True)

    def _refresh_dx_spots(self) -> None:
        """Trigger DX cluster spots refresh."""
        self.run_worker(self._fetch_dx_spots(), exclusive=True)

    async def _fetch_pota_spots(self) -> list[Spot]:
        """Fetch POTA spots asynchronously."""
        try:
            if self._pota_spot_service:
                spots = await self._pota_spot_service.get_spots(limit=50)
                # Use call_later to safely update UI from async worker
                self.app.call_later(self._update_spots_table, spots)
                return spots
        except Exception as e:
            logger.error(f"Error fetching POTA spots: {e}")
            self.notify(f"POTA spots error: {e}", severity="warning", timeout=3)
        return []

    async def _fetch_dx_spots(self) -> list[Spot]:
        """Fetch DX cluster spots asynchronously."""
        try:
            if self._dx_cluster_service:
                source = self.app.config.dx_cluster_source
                use_telnet = source in (DXClusterSource.TELNET, DXClusterSource.BOTH)
                use_web = source in (DXClusterSource.WEB_API, DXClusterSource.BOTH)
                spots = await self._dx_cluster_service.get_spots(
                    limit=50,
                    use_telnet=use_telnet,
                    use_web=use_web,
                )
                # Use call_later to safely update UI from async worker
                self.app.call_later(self._update_spots_table, spots)
                return spots
        except Exception as e:
            logger.error(f"Error fetching DX spots: {e}")
            self.notify(f"DX spots error: {e}", severity="warning", timeout=3)
        return []

    def _update_spots_table(self, spots: list[Spot]) -> None:
        """Update the spots table with new spots."""
        try:
            spots_table = self.query_one(SpotsTable)
            spots_table.load_spots(spots)
            logger.info(f"Updated spots table with {len(spots)} spots")
        except Exception as e:
            logger.error(f"Failed to update spots table: {e}")

    def on_spots_table_spot_selected(self, event: SpotsTable.SpotSelected) -> None:
        """Handle spot selection - auto-fill the QSO form and optionally QSY radio."""
        spot = event.spot
        logger.info(f"Spot selected: {spot.callsign} {spot.frequency:.3f} MHz {spot.mode}")
        form = self.query_one(QSOEntryForm)

        # Set callsign
        try:
            callsign_input = self.query_one("#callsign", Input)
            callsign_input.value = spot.callsign
            logger.debug(f"Set callsign to {spot.callsign}")
        except Exception as e:
            logger.warning(f"Failed to set callsign: {e}")

        # Set frequency and mode
        try:
            form.set_frequency(spot.frequency)
            logger.debug(f"Set frequency to {spot.frequency}")
            if spot.mode:
                form.set_mode(spot.mode)
                logger.debug(f"Set mode to {spot.mode}")
        except Exception as e:
            logger.warning(f"Failed to set frequency/mode: {e}")

        # QSY radio if enabled
        rig_type = self.app.config.rig_control_type
        if rig_type != RigControlType.NONE and self.app.config.rig_auto_qsy:
            if (rig_type == RigControlType.RIGCTLD and self._rigctld_service) or (
                rig_type == RigControlType.FLEXRADIO and self._flexradio_service
            ):
                self.run_worker(
                    self._qsy_to_spot(spot),
                    exclusive=True,
                    name="qsy",
                    group="rig",
                )

        # For POTA spots, look up park info and display, and fill in park ref
        if spot.park_reference:
            # Fill in their park reference in the form (for P2P contacts)
            form.set_their_park(spot.park_reference)
            # Look up park info to display
            self.run_worker(
                self._lookup_park(spot.park_reference),
                exclusive=False,
                name=f"park_{spot.park_reference}",
            )
        elif spot.callsign:
            # For DX spots, do regular callsign lookup
            self._do_lookup(spot.callsign)

        self.notify(f"Selected {spot.callsign} on {spot.frequency:.3f} MHz", timeout=2)

    def on_spots_table_spot_aged_out(self, event: SpotsTable.SpotAgedOut) -> None:
        """Handle notification when a selected spot ages out."""
        self.notify(
            f"Selected spot {event.callsign} aged out - pinned to top",
            severity="information",
            timeout=5,
        )

    async def _lookup_park(self, park_reference: str) -> Optional[Park]:
        """Look up POTA park information."""
        if not self._pota_parks_service:
            return None

        try:
            park = await self._pota_parks_service.get_park(park_reference)
            if park:
                # Update callsign info with park details
                self.app.call_later(self._display_park_info, park)
            return park
        except Exception as e:
            logger.warning(f"Park lookup failed: {e}")
            return None

    def _display_park_info(self, park: Park) -> None:
        """Display park information in the callsign info area."""
        try:
            callsign_info = self.query_one(CallsignInfo)
            info_parts = [f"[bold cyan]{park.reference}[/bold cyan]: {park.name}"]
            if park.parktype:
                info_parts.append(f"[dim]({park.parktype})[/dim]")
            if park.location_name:
                info_parts.append(f"[green]{park.location_name}[/green]")
            if park.grid6:
                info_parts.append(f"[yellow]{park.grid6}[/yellow]")
            callsign_info.set_info(" | ".join(info_parts))
        except Exception as e:
            logger.warning(f"Failed to display park info: {e}")

    async def _qsy_to_spot(self, spot: Spot) -> None:
        """QSY the radio to a spot's frequency and mode."""
        try:
            rig_type = self.app.config.rig_control_type
            if rig_type == RigControlType.RIGCTLD and self._rigctld_service:
                # Set mode FIRST to avoid auto-offset issues when mode changes
                if spot.mode:
                    rig_mode = RigctldService.map_mode_to_rigctld(
                        spot.mode, spot.frequency
                    )
                    await self._rigctld_service.set_mode(rig_mode)
                # Then set frequency (overrides any auto-offset from mode change)
                await self._rigctld_service.set_frequency_mhz(spot.frequency)
                logger.info(f"QSY to {spot.frequency:.3f} MHz {spot.mode or ''}")
            elif rig_type == RigControlType.FLEXRADIO and self._flexradio_service:
                # Set mode FIRST to avoid auto-offset issues when mode changes
                if spot.mode:
                    flex_mode = FlexRadioService.map_mode_to_flex(
                        spot.mode, spot.frequency
                    )
                    await self._flexradio_service.set_mode(flex_mode)
                # Then set frequency (overrides any auto-offset from mode change)
                await self._flexradio_service.set_frequency_mhz(spot.frequency)
                logger.info(f"QSY to {spot.frequency:.3f} MHz {spot.mode or ''}")
        except Exception as e:
            logger.error(f"QSY failed: {e}")
            self.app.call_later(
                self.notify,
                f"QSY failed: {e}",
                severity="warning",
            )

    @on(QSOEntryForm.QSOLogged)
    def on_qso_entry_form_qso_logged(self, event: QSOEntryForm.QSOLogged) -> None:
        """Handle QSO logged event."""
        try:
            logger.info(f"QSO logging handler called for {event.qso.callsign} on {event.qso.frequency:.3f} MHz")

            # If in a mode, set exchange sent
            if self._current_mode:
                logger.debug(f"Setting exchange sent for mode: {self._current_mode}")
                event.qso.exchange_sent = self._current_mode.format_exchange_sent()

            # Save to database with active log
            logger.debug(f"Saving QSO to database (log_id={self._active_log_id})")
            qso_id = self.db.add_qso(event.qso, log_id=self._active_log_id)
            logger.info(f"QSO saved to database with ID: {qso_id}")

            event.qso.id = qso_id
            event.qso.log_id = self._active_log_id

            # Add to current mode if active
            if self._current_mode:
                logger.debug("Adding QSO to current mode")
                self._current_mode.add_qso(event.qso)
                self.query_one(ModeStatus).refresh_status()

            # Add to table
            logger.debug("Adding QSO to table")
            self.query_one(QSOTable).add_qso(event.qso)

            # Update status bar with log-filtered count
            logger.debug("Updating status bar")
            count = self.db.get_qso_count(log_id=self._active_log_id)
            self.query_one(StatusBar).set_qso_count(count)

            # Update log status with new count
            if self._active_log_id:
                logger.debug("Updating log status")
                active_log = self.db.get_active_log()
                if active_log:
                    self.query_one(LogStatus).set_log(active_log.display_name, active_log.qso_count)

            # Clear callsign info
            logger.debug("Clearing callsign info")
            self.query_one(CallsignInfo).clear()

            logger.info(f"QSO logging completed successfully for {event.qso.callsign}")
            self.notify(f"Logged {event.qso.callsign}", timeout=2)

        except Exception as e:
            logger.error(f"QSO logging failed: {e}", exc_info=True)
            self.notify(f"Failed to log QSO: {e}", severity="error", timeout=5)

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

    def on_qso_entry_form_callsign_blurred(
        self, event: QSOEntryForm.CallsignBlurred
    ) -> None:
        """Handle callsign field blur - trigger lookup when tabbing out."""
        if event.callsign:
            self._do_lookup(event.callsign)

    def on_clickable_label_clicked(self, event) -> None:
        """Handle clickable label clicks from QSO entry form."""
        # Import here to avoid circular dependency
        from ..widgets.qso_entry import ClickableLabel

        if isinstance(event, ClickableLabel.Clicked):
            if event.action_id == "read-rig":
                self._update_frequency_from_rig()
            elif event.action_id == "read-time":
                form = self.query_one(QSOEntryForm)
                form.update_datetime()

    def _do_lookup(self, callsign: str) -> None:
        """Perform async callsign lookup."""
        callsign_info = self.query_one(CallsignInfo)
        callsign_info.set_info(f"Looking up {callsign}...")

        # Cancel any pending lookup
        self._cancel_lookup()

        # Start new lookup worker (non-exclusive to not block QSY)
        self._lookup_worker = self.run_worker(
            self._lookup_callsign_async(callsign),
            name=f"lookup_{callsign}",
            exclusive=False,
        )

    async def _lookup_callsign_async(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Async worker to perform callsign lookup."""
        try:
            result = await self.app.lookup_service.lookup(callsign)
            return result
        except LookupError:
            return None

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        """Handle lookup worker completion."""
        if event.worker.name and event.worker.name.startswith("lookup_"):
            if event.state == WorkerState.SUCCESS:
                result = event.worker.result
                callsign_info = self.query_one(CallsignInfo)
                if result:
                    callsign_info.set_info(result.display_str)
                else:
                    callsign_info.set_info("No information found")
            elif event.state == WorkerState.ERROR:
                self.query_one(CallsignInfo).set_info("Lookup failed")

    def _cancel_lookup(self) -> None:
        """Cancel any pending lookup."""
        if hasattr(self, "_lookup_worker") and self._lookup_worker:
            self._lookup_worker.cancel()

    def action_show_help(self) -> None:
        """Show help screen."""
        self.app.push_screen(HelpScreen())

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

    def action_manage_logs(self) -> None:
        """Show log manager screen."""

        def on_log_manager_close(log_id: Optional[int]) -> None:
            # Refresh the active log and QSO table
            self._load_active_log()
            self._refresh_qso_table()

        self.app.push_screen(LogManagerScreen(self.db), on_log_manager_close)

    def action_browse_log(self) -> None:
        """Show log browser screen."""

        def on_browser_close() -> None:
            # Refresh the table when returning from browser (respecting log filter)
            self._refresh_qso_table()

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
                # Show POTA activation setup
                self.app.push_screen(
                    POTASetupScreen(
                        my_callsign=self.app.config.my_callsign,
                        my_state=self.app.config.my_state or "",
                        my_grid=self.app.config.my_grid or "",
                    ),
                    handle_pota_setup,
                )
            elif mode_type == "pota_hunter":
                # Show POTA hunter setup
                self.app.push_screen(
                    POTAHunterSetupScreen(
                        my_callsign=self.app.config.my_callsign,
                        my_state=self.app.config.my_state or "",
                        my_grid=self.app.config.my_grid or "",
                    ),
                    handle_pota_hunter_setup,
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
                # Enable POTA fields in QSO form
                self.query_one(QSOEntryForm).set_pota_mode(True)
                # Switch to POTA spots
                self._start_spot_refresh()

        def handle_pota_hunter_setup(mode: Optional[POTAMode]) -> None:
            if mode:
                self._current_mode = mode
                self.query_one(ModeStatus).set_mode(mode)
                self.notify("Started POTA hunting mode")
                # Enable POTA fields in QSO form
                self.query_one(QSOEntryForm).set_pota_mode(True)
                # Switch to POTA spots (hunters want to see activators)
                self._start_spot_refresh()

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
        # Check if it was a POTA mode before clearing
        was_pota_mode = isinstance(self._current_mode, POTAMode)
        self._current_mode = None
        self.query_one(ModeStatus).set_mode(None)
        self.notify(f"Ended {mode_name} - Final score: {score.total_score}")
        # Disable POTA fields in QSO form if we were in POTA mode
        if was_pota_mode:
            self.query_one(QSOEntryForm).set_pota_mode(False)
        # Switch back to DX cluster spots
        self._start_spot_refresh()

    def action_toggle_mode(self) -> None:
        """Toggle operating mode - start new mode if none active, end mode if active."""
        if self._current_mode is None:
            # No active mode - start new mode
            self.action_new_contest()
        else:
            # Active mode - end it
            self.action_end_mode()

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

    def action_export_pota(self) -> None:
        """Export log in POTA format for upload to pota.app."""
        # Check if in POTA mode
        if not isinstance(self._current_mode, POTAMode):
            self.notify("Start a POTA activation first (Ctrl+N)", severity="warning")
            return

        pota_mode = self._current_mode
        if not pota_mode.config.my_park:
            self.notify("No park reference configured", severity="warning")
            return

        # Get QSOs from this activation
        qsos = pota_mode._qsos
        if not qsos:
            self.notify("No QSOs to export", severity="warning")
            return

        # Generate POTA filename
        default_filename = get_pota_filename(
            pota_mode.config.my_callsign,
            pota_mode.config.my_park,
        )

        def handle_export(path: Optional[Path]) -> None:
            if path is None:
                return

            try:
                count = export_pota_adif(
                    qsos,
                    path,
                    my_callsign=pota_mode.config.my_callsign,
                    my_park_ref=pota_mode.config.my_park,
                    my_state=pota_mode.config.my_state,
                    my_grid=pota_mode.config.my_grid,
                )
                score = pota_mode.calculate_score()
                self.app.push_screen(
                    ExportCompleteScreen(
                        f"Exported {count} QSOs for POTA to:\n{path}\n\n"
                        f"Park: {pota_mode.config.my_park}\n"
                        f"P2P Contacts: {score.multipliers}\n\n"
                        f"Upload at: pota.app → My Log Uploads"
                    )
                )
            except Exception as e:
                self.notify(f"POTA export failed: {e}", severity="error")

        self.app.push_screen(
            FilePickerScreen(
                title="Export for POTA",
                start_path=Path.home(),
                extensions=[".adi", ".adif"],
                save_mode=True,
                default_filename=default_filename,
            ),
            handle_export,
        )

    def action_manual_tune(self) -> None:
        """Open manual tune dialog for frequency and mode control."""
        # Get current frequency and mode
        current_freq = None
        current_mode = None

        # Try to get from rig if connected
        rig_type = self.app.config.rig_control_type
        if rig_type == RigControlType.RIGCTLD and self._rigctld_service:
            state = self._rigctld_service.last_state
            if self._rigctld_service.is_connected and state:
                current_freq = state.frequency_mhz
                # Map rigctld mode back to our Mode enum
                rig_mode = state.mode
                if rig_mode in ["USB", "LSB"]:
                    current_mode = "SSB"
                elif rig_mode in ["CW", "CWR"]:
                    current_mode = "CW"
                elif rig_mode in ["PKTUSB", "DIGU", "DIGL"]:
                    current_mode = "FT8"
                else:
                    current_mode = rig_mode
        elif rig_type == RigControlType.FLEXRADIO and self._flexradio_service:
            state = self._flexradio_service.last_state
            if self._flexradio_service.is_connected and state:
                current_freq = state.frequency_mhz
                # Map Flex mode back to our Mode enum
                flex_mode = state.mode
                if flex_mode in ["USB", "LSB"]:
                    current_mode = "SSB"
                elif flex_mode in ["CW", "CWL"]:
                    current_mode = "CW"
                elif flex_mode in ["DIGU", "DIGL"]:
                    current_mode = "FT8"
                else:
                    current_mode = flex_mode

        # Fall back to QSO form values if rig not available
        if current_freq is None:
            try:
                freq_str = self.query_one("#frequency", Input).value.strip()
                if freq_str:
                    current_freq = float(freq_str)
            except (ValueError, Exception):
                current_freq = 14.250  # Default

        if current_mode is None:
            try:
                from ..widgets.qso_entry import QSOEntryForm
                form = self.query_one(QSOEntryForm)
                current_mode = form.query_one("#mode").value
            except Exception:
                current_mode = "SSB"  # Default

        def handle_tune(result: dict) -> None:
            """Handle the tune dialog result."""
            if not result:
                return  # User cancelled

            frequency = result.get("frequency")
            mode = result.get("mode")

            if frequency is None or mode is None:
                return

            # Update QSO form
            try:
                form = self.query_one(QSOEntryForm)
                form.set_frequency(frequency)
                form.set_mode(mode)
            except Exception as e:
                logger.error(f"Failed to update QSO form: {e}")

            # Send to rig if configured
            rig_type = self.app.config.rig_control_type
            if rig_type == RigControlType.RIGCTLD and self._rigctld_service:
                if self._rigctld_service.is_connected:
                    self.run_worker(
                        self._tune_rigctld(frequency, mode),
                        name="tune_rigctld",
                        exclusive=True,
                        group="rig",
                    )
            elif rig_type == RigControlType.FLEXRADIO and self._flexradio_service:
                if self._flexradio_service.is_connected:
                    self.run_worker(
                        self._tune_flexradio(frequency, mode),
                        name="tune_flexradio",
                        exclusive=True,
                        group="rig",
                    )

        # Show the modal
        self.app.push_screen(
            ManualTuneModal(current_frequency=current_freq, current_mode=current_mode),
            handle_tune,
        )

    async def _tune_rigctld(self, frequency: float, mode: str) -> None:
        """Tune rigctld radio to frequency and mode."""
        try:
            if self._rigctld_service:
                # Set mode FIRST to avoid auto-offset issues when mode changes
                rig_mode = RigctldService.map_mode_to_rigctld(mode, frequency)
                await self._rigctld_service.set_mode(rig_mode)

                # Then set frequency (overrides any auto-offset from mode change)
                await self._rigctld_service.set_frequency_mhz(frequency)

                logger.info(f"Tuned rigctld to {frequency:.3f} MHz {mode}")
                self.app.call_later(
                    self.notify,
                    f"Tuned to {frequency:.3f} MHz {mode}",
                    timeout=2,
                )
        except Exception as e:
            logger.error(f"Failed to tune rigctld: {e}")
            self.app.call_later(
                self.notify,
                f"Tune failed: {e}",
                severity="warning",
                timeout=3,
            )

    async def _tune_flexradio(self, frequency: float, mode: str) -> None:
        """Tune Flex Radio to frequency and mode."""
        try:
            if self._flexradio_service:
                # Set mode FIRST to avoid auto-offset issues when mode changes
                flex_mode = FlexRadioService.map_mode_to_flex(mode, frequency)
                await self._flexradio_service.set_mode(flex_mode)

                # Then set frequency (overrides any auto-offset from mode change)
                await self._flexradio_service.set_frequency_mhz(frequency)

                logger.info(f"Tuned Flex Radio to {frequency:.3f} MHz {mode}")
                self.app.call_later(
                    self.notify,
                    f"Tuned to {frequency:.3f} MHz {mode}",
                    timeout=2,
                )
        except Exception as e:
            logger.error(f"Failed to tune Flex Radio: {e}")
            self.app.call_later(
                self.notify,
                f"Tune failed: {e}",
                severity="warning",
                timeout=3,
            )

    def action_read_from_rig(self) -> None:
        """Read frequency and mode from radio and update QSO form."""
        self._update_frequency_from_rig()

    def action_refresh_current_field(self) -> None:
        """Context-aware refresh - update current field from rig or computer."""
        try:
            # Get the currently focused widget
            focused = self.app.focused
            if not focused or not hasattr(focused, 'id'):
                return

            field_id = focused.id

            # Context-aware behavior based on focused field
            if field_id in ("frequency", "mode"):
                # Read from rig
                self._update_frequency_from_rig()
            elif field_id in ("time", "date"):
                # Read current time/date from computer
                form = self.query_one(QSOEntryForm)
                form.update_datetime()
            # For any other field, do nothing

        except Exception as e:
            logger.debug(f"Refresh field failed: {e}")

    def action_cycle_band_filter(self) -> None:
        """Cycle through band filters for spots table."""
        try:
            spots_table = self.query_one("#spots-table", SpotsTable)
            spots_table._cycle_band_filter()
        except Exception:
            pass

    def action_cycle_mode_filter(self) -> None:
        """Cycle through mode filters for spots table."""
        try:
            spots_table = self.query_one("#spots-table", SpotsTable)
            spots_table._cycle_mode_filter()
        except Exception:
            pass

    def action_clear_spot_filters(self) -> None:
        """Clear all spot filters for spots table."""
        try:
            spots_table = self.query_one("#spots-table", SpotsTable)
            spots_table.reset_filters()
        except Exception:
            pass

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
