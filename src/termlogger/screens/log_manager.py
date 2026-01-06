"""Log manager screen for creating and managing virtual logs."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Label, Select, Static

from ..database import Database
from ..models import Log, LogType


class LogCreateModal(ModalScreen[Optional[Log]]):
    """Modal screen for creating a new log."""

    CSS = """
    LogCreateModal {
        align: center middle;
    }

    LogCreateModal > Vertical {
        width: 60;
        height: auto;
        background: $surface;
        border: heavy $primary;
        padding: 0 1;
    }

    LogCreateModal .title {
        text-align: center;
        text-style: bold;
        color: $primary;
    }

    LogCreateModal .form-row {
        height: 3;
    }

    LogCreateModal Label {
        width: 15;
        height: 3;
        padding: 1 0 0 0;
    }

    LogCreateModal Input {
        width: 1fr;
    }

    LogCreateModal Select {
        width: 1fr;
    }

    LogCreateModal .button-row {
        height: 3;
        align: center middle;
    }

    LogCreateModal Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        my_callsign: str = "",
        my_grid: str = "",
    ) -> None:
        super().__init__()
        self._my_callsign = my_callsign
        self._my_grid = my_grid

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Create New Log", classes="title")

            with Horizontal(classes="form-row"):
                yield Label("Name:")
                yield Input(placeholder="e.g., POTA K-1234 Activation", id="name")

            with Horizontal(classes="form-row"):
                yield Label("Type:")
                yield Select(
                    [(t.value.replace("_", " ").title(), t.value) for t in LogType],
                    value=LogType.GENERAL.value,
                    id="log_type",
                )

            with Horizontal(classes="form-row"):
                yield Label("Description:")
                yield Input(placeholder="Optional description", id="description")

            with Horizontal(classes="form-row"):
                yield Label("POTA Ref:")
                yield Input(placeholder="e.g., K-1234", id="pota_ref")

            with Horizontal(classes="form-row"):
                yield Label("My Callsign:")
                yield Input(value=self._my_callsign, id="my_callsign")

            with Horizontal(classes="form-row"):
                yield Label("My Grid:")
                yield Input(value=self._my_grid, id="my_grid")

            with Horizontal(classes="form-row"):
                yield Label("Location:")
                yield Input(placeholder="e.g., Smith State Park, NC", id="location")

            with Horizontal(classes="button-row"):
                yield Button("Create", id="create", variant="primary")
                yield Button("Cancel", id="cancel")

    @on(Button.Pressed, "#create")
    def _on_create(self) -> None:
        """Create the log."""
        name = self.query_one("#name", Input).value.strip()
        if not name:
            self.notify("Log name is required", severity="error")
            return

        log_type_value = self.query_one("#log_type", Select).value
        log_type = LogType(log_type_value) if log_type_value else LogType.GENERAL

        log = Log(
            name=name,
            description=self.query_one("#description", Input).value.strip(),
            log_type=log_type,
            pota_ref=self.query_one("#pota_ref", Input).value.strip() or None,
            my_callsign=self.query_one("#my_callsign", Input).value.strip() or None,
            my_gridsquare=self.query_one("#my_grid", Input).value.strip() or None,
            location=self.query_one("#location", Input).value.strip() or None,
            start_time=datetime.now(timezone.utc),
        )
        self.dismiss(log)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        """Cancel log creation."""
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)


class LogManagerScreen(ModalScreen[Optional[int]]):
    """Screen for managing virtual logs."""

    CSS = """
    LogManagerScreen {
        align: center middle;
    }

    LogManagerScreen > Vertical {
        width: 90%;
        height: 85%;
        background: $surface;
        border: heavy $primary;
        padding: 0 1;
    }

    LogManagerScreen .title {
        text-align: center;
        text-style: bold;
        color: $primary;
        height: 1;
    }

    LogManagerScreen .tab-row {
        height: 3;
        align: center middle;
    }

    LogManagerScreen .tab-row Button {
        margin: 0 1;
        min-width: 10;
    }

    LogManagerScreen .tab-active {
        background: $primary;
        color: $text;
    }

    LogManagerScreen DataTable {
        height: 1fr;
    }

    LogManagerScreen .button-row {
        height: auto;
        align: center middle;
    }

    LogManagerScreen .button-row Button {
        margin: 0 0;
    }

    LogManagerScreen .info-row {
        height: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("n", "new_log", "New Log"),
        ("enter", "select_log", "Select"),
        ("a", "toggle_archive", "Archive/Unarchive"),
        ("e", "export_log", "Export"),
        ("i", "import_log", "Import"),
    ]

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._logs: list[Log] = []
        self._active_log_id: Optional[int] = None
        self._showing_archived = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Log Manager", classes="title")
            with Horizontal(classes="tab-row"):
                yield Button("Active Logs", id="tab-active", classes="tab-active")
                yield Button("Archived Logs", id="tab-archived")
                yield Button("New", id="new-log")
                yield Button("Select", id="select-log")
            yield Static("", id="active-info", classes="info-row")
            yield DataTable(id="logs-table", cursor_type="row")
            with Horizontal(classes="button-row"):
                yield Button("Export", id="export-log")
                yield Button("Exp All", id="export-all")
                yield Button("Import", id="import-log")
                yield Button("QRZ Up", id="qrz-upload")
                yield Button("QRZ Down", id="qrz-download")
                yield Button("ClubLog", id="clublog-upload")
                yield Button("Archive", id="archive-log")
                yield Button("Close", id="close")

    def on_mount(self) -> None:
        """Initialize the screen."""
        table = self.query_one("#logs-table", DataTable)
        table.add_column("#", width=4)
        table.add_column("Name", width=30)
        table.add_column("Type", width=15)
        table.add_column("QSOs", width=6)
        table.add_column("Date", width=12)
        table.add_column("Callsign", width=10)
        table.add_column("Active", width=6)

        self._refresh_logs()

    def _refresh_logs(self) -> None:
        """Refresh the logs table."""
        if self._showing_archived:
            self._logs = self.db.get_archived_logs()
        else:
            self._logs = self.db.get_all_logs(include_archived=False)

        active_log = self.db.get_active_log()
        self._active_log_id = active_log.id if active_log else None

        # Update info row
        info = self.query_one("#active-info", Static)
        if self._showing_archived:
            info.update(f"[dim]Showing {len(self._logs)} archived log(s)[/dim]")
        elif active_log:
            info.update(
                f"[bold]Active Log:[/bold] {active_log.display_name} ({active_log.qso_count} QSOs)"
            )
        else:
            info.update("[dim]No active log - QSOs will be logged without a log association[/dim]")

        # Update archive button text
        archive_btn = self.query_one("#archive-log", Button)
        if self._showing_archived:
            archive_btn.label = "Unarchive (A)"
        else:
            archive_btn.label = "Archive (A)"

        # Update table
        table = self.query_one("#logs-table", DataTable)
        table.clear()

        for i, log in enumerate(self._logs, 1):
            is_active = "Yes" if log.id == self._active_log_id else ""
            table.add_row(
                str(i),
                log.name[:28],
                log.log_type.value.replace("_", " ").title()[:13],
                str(log.qso_count),
                log.date_str,
                log.my_callsign or "",
                is_active,
                key=str(log.id),
            )

    @on(Button.Pressed, "#tab-active")
    def _on_tab_active(self) -> None:
        """Switch to active logs view."""
        self._showing_archived = False
        self.query_one("#tab-active", Button).add_class("tab-active")
        self.query_one("#tab-archived", Button).remove_class("tab-active")
        self._refresh_logs()

    @on(Button.Pressed, "#tab-archived")
    def _on_tab_archived(self) -> None:
        """Switch to archived logs view."""
        self._showing_archived = True
        self.query_one("#tab-archived", Button).add_class("tab-active")
        self.query_one("#tab-active", Button).remove_class("tab-active")
        self._refresh_logs()

    @on(Button.Pressed, "#new-log")
    def action_new_log(self) -> None:
        """Create a new log."""

        def handle_result(log: Optional[Log]) -> None:
            if log:
                log_id = self.db.add_log(log)
                self.db.set_active_log(log_id)
                self._refresh_logs()
                self.notify(f"Created and activated log: {log.name}")

        self.app.push_screen(
            LogCreateModal(
                my_callsign=self.app.config.my_callsign,
                my_grid=self.app.config.my_grid or "",
            ),
            handle_result,
        )

    @on(Button.Pressed, "#select-log")
    @on(DataTable.RowSelected)
    def action_select_log(self, event=None) -> None:
        """Select the highlighted log as active."""
        if self._showing_archived:
            self.notify("Unarchive the log first to select it", severity="warning")
            return
        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._logs):
            log = self._logs[table.cursor_row]
            self.db.set_active_log(log.id)
            self._refresh_logs()
            self.notify(f"Activated log: {log.name}")

    @on(Button.Pressed, "#archive-log")
    def action_toggle_archive(self) -> None:
        """Archive or unarchive the selected log."""
        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._logs):
            log = self._logs[table.cursor_row]
            if self._showing_archived:
                self.db.unarchive_log(log.id)
                self._refresh_logs()
                self.notify(f"Unarchived log: {log.name}")
            else:
                self.db.archive_log(log.id)
                self._refresh_logs()
                self.notify(f"Archived log: {log.name}")

    @on(Button.Pressed, "#export-log")
    def action_export_log(self) -> None:
        """Export the selected log."""
        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._logs):
            self.notify("Select a log to export", severity="warning")
            return

        log = self._logs[table.cursor_row]

        from .mode_setup import ExportSelectScreen

        def handle_export_select(export_type: Optional[str]) -> None:
            if export_type is None:
                return
            self._do_export(log, export_type)

        self.app.push_screen(ExportSelectScreen(), handle_export_select)

    @on(Button.Pressed, "#export-all")
    def action_export_all(self) -> None:
        """Export all QSOs to ADIF for backup."""
        from ..adif import export_adif_file
        from .file_picker import ExportCompleteScreen, FilePickerScreen

        # Get ALL QSOs (no log_id filter)
        qsos = self.db.get_all_qsos(limit=100000)
        if not qsos:
            self.notify("No QSOs to export", severity="warning")
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        default_filename = f"termlogger_backup_{timestamp}.adi"

        def handle_export(path: Optional[Path]) -> None:
            if path is None:
                return
            try:
                export_adif_file(qsos, path)
                self.app.push_screen(
                    ExportCompleteScreen(
                        f"Exported full backup to:\n{path}\n\nTotal QSOs: {len(qsos)}"
                    )
                )
            except Exception as e:
                self.notify(f"Export failed: {e}", severity="error")

        self.app.push_screen(
            FilePickerScreen(
                title="Export All QSOs (Backup)",
                start_path=Path.home(),
                extensions=[".adi", ".adif"],
                save_mode=True,
                default_filename=default_filename,
            ),
            handle_export,
        )

    def _do_export(self, log: Log, export_type: str) -> None:
        """Perform the export for the given log."""
        from ..adif import export_adif_file, export_pota_adif, get_pota_filename
        from .file_picker import ExportCompleteScreen, FilePickerScreen

        # Get QSOs for this log
        qsos = self.db.get_all_qsos(log_id=log.id, limit=10000)
        if not qsos:
            self.notify("No QSOs to export", severity="warning")
            return

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        if export_type == "adif":
            default_filename = f"{log.name.replace(' ', '_')}_{timestamp}.adi"

            def handle_adif_export(path: Optional[Path]) -> None:
                if path is None:
                    return
                try:
                    export_adif_file(qsos, path)
                    self.app.push_screen(
                        ExportCompleteScreen(
                            f"Exported ADIF log to:\n{path}\n\nQSOs: {len(qsos)}"
                        )
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
                handle_adif_export,
            )

        elif export_type == "pota":
            if not log.pota_ref:
                self.notify("Log has no POTA reference", severity="warning")
                return
            default_filename = get_pota_filename(
                log.my_callsign or self.app.config.my_callsign,
                log.pota_ref,
            )

            def handle_pota_export(path: Optional[Path]) -> None:
                if path is None:
                    return
                try:
                    export_pota_adif(
                        qsos,
                        path,
                        my_park=log.pota_ref,
                        my_state=log.location or "",
                    )
                    self.app.push_screen(
                        ExportCompleteScreen(
                            f"Exported POTA log to:\n{path}\n\nQSOs: {len(qsos)}"
                        )
                    )
                except Exception as e:
                    self.notify(f"Export failed: {e}", severity="error")

            self.app.push_screen(
                FilePickerScreen(
                    title="Export POTA ADIF",
                    start_path=Path.home(),
                    extensions=[".adi", ".adif"],
                    save_mode=True,
                    default_filename=default_filename,
                ),
                handle_pota_export,
            )

        elif export_type == "cabrillo":
            self.notify("Cabrillo export requires an active contest mode", severity="warning")

    @on(Button.Pressed, "#import-log")
    def action_import_log(self) -> None:
        """Import a log from ADIF file."""
        from ..adif import parse_adif_file
        from .file_picker import FilePickerScreen

        def handle_import(path: Optional[Path]) -> None:
            if path is None:
                return
            try:
                qsos = parse_adif_file(path)
                if not qsos:
                    self.notify("No QSOs found in file", severity="warning")
                    return

                # Create a new log for the imported QSOs
                log = Log(
                    name=f"Import: {path.stem}",
                    description=f"Imported from {path.name}",
                    log_type=LogType.GENERAL,
                    start_time=datetime.now(timezone.utc),
                )
                log_id = self.db.add_log(log)

                # Add QSOs to the log
                for qso in qsos:
                    qso.log_id = log_id
                    self.db.add_qso(qso)

                self.db.set_active_log(log_id)
                self._refresh_logs()
                self.notify(f"Imported {len(qsos)} QSOs into new log: {log.name}")
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

    @on(Button.Pressed, "#qrz-upload")
    def action_qrz_upload(self) -> None:
        """Upload QSOs to QRZ Logbook."""
        # Check API key
        if not self.app.config.qrz_api_key:
            self.notify("QRZ API key not configured - set it in Settings (F9)", severity="error")
            return

        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._logs):
            self.notify("Select a log to upload", severity="warning")
            return

        log = self._logs[table.cursor_row]

        # Get QSOs that haven't been uploaded yet
        qsos = self.db.get_qsos_without_qrz_logid(log_id=log.id)
        if not qsos:
            self.notify("All QSOs in this log have already been uploaded to QRZ", severity="information")
            return

        self.notify(f"Uploading {len(qsos)} QSOs to QRZ...", severity="information")

        # Run the upload in background
        self._run_qrz_upload(log, qsos)

    def _run_qrz_upload(self, log: Log, qsos: list) -> None:
        """Run the QRZ upload asynchronously."""
        import asyncio

        from ..services.qrz_logbook import QRZLogbookError, QRZLogbookService

        async def do_upload():
            service = QRZLogbookService(self.app.config.qrz_api_key)
            try:
                success, failed, results = await service.upload_qsos(qsos)

                # Update qrz_logid for successfully uploaded QSOs
                for qso, logid in results:
                    if logid and qso.id:
                        self.db.update_qso_qrz_logid(qso.id, logid)

                self.notify(
                    f"QRZ Upload complete: {success} uploaded, {failed} failed",
                    severity="information" if failed == 0 else "warning",
                )
            except QRZLogbookError as e:
                self.notify(f"QRZ upload error: {e}", severity="error")
            finally:
                await service.close()

        asyncio.create_task(do_upload())

    @on(Button.Pressed, "#qrz-download")
    def action_qrz_download(self) -> None:
        """Download QSOs from QRZ Logbook."""
        # Check API key
        if not self.app.config.qrz_api_key:
            self.notify("QRZ API key not configured - set it in Settings (F9)", severity="error")
            return

        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._logs):
            self.notify("Select a log to download into", severity="warning")
            return

        log = self._logs[table.cursor_row]

        self.notify("Downloading QSOs from QRZ...", severity="information")

        # Run the download in background
        self._run_qrz_download(log)

    def _run_qrz_download(self, log: Log) -> None:
        """Run the QRZ download asynchronously."""
        import asyncio

        from ..services.qrz_logbook import QRZLogbookError, QRZLogbookService

        async def do_download():
            service = QRZLogbookService(self.app.config.qrz_api_key)
            try:
                qsos = await service.fetch_all_qsos()

                if not qsos:
                    self.notify("No QSOs found in QRZ logbook", severity="information")
                    return

                # Import QSOs, skipping duplicates
                imported = 0
                skipped = 0
                for qso in qsos:
                    # Check for duplicate
                    existing = self.db.find_duplicate_qso(
                        qso.callsign,
                        qso.datetime_utc,
                        qso.frequency,
                        log_id=log.id,
                    )
                    if existing:
                        skipped += 1
                        continue

                    # Add to database with log association
                    qso.log_id = log.id
                    self.db.add_qso(qso)
                    imported += 1

                self._refresh_logs()
                self.notify(
                    f"QRZ Download complete: {imported} imported, {skipped} duplicates skipped",
                    severity="information",
                )
            except QRZLogbookError as e:
                self.notify(f"QRZ download error: {e}", severity="error")
            finally:
                await service.close()

        asyncio.create_task(do_download())

    @on(Button.Pressed, "#clublog-upload")
    def action_clublog_upload(self) -> None:
        """Upload QSOs to Club Log."""
        # Check credentials
        if not self.app.config.clublog_email or not self.app.config.clublog_api_key:
            self.notify("Club Log credentials not configured - set them in Settings (F9)", severity="error")
            return

        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is None or table.cursor_row >= len(self._logs):
            self.notify("Select a log to upload", severity="warning")
            return

        log = self._logs[table.cursor_row]

        # Get QSOs that haven't been uploaded yet
        qsos = self.db.get_qsos_not_uploaded_to_clublog(log_id=log.id)
        if not qsos:
            self.notify("All QSOs in this log have already been uploaded to Club Log", severity="information")
            return

        self.notify(f"Uploading {len(qsos)} QSOs to Club Log...", severity="information")

        # Run the upload in background
        self._run_clublog_upload(log, qsos)

    def _run_clublog_upload(self, log: Log, qsos: list) -> None:
        """Run the Club Log upload asynchronously."""
        import asyncio

        from ..services.clublog import ClubLogError, ClubLogService

        async def do_upload():
            # Use log's callsign if set, otherwise use config callsign
            callsign = log.my_callsign or self.app.config.clublog_callsign or self.app.config.my_callsign
            service = ClubLogService(
                email=self.app.config.clublog_email,
                password=self.app.config.clublog_password,
                callsign=callsign,
                api_key=self.app.config.clublog_api_key,
            )
            try:
                success, failed = await service.upload_qsos(qsos)

                # Mark all QSOs as uploaded (batch upload is all-or-nothing)
                if failed == 0:
                    for qso in qsos:
                        if qso.id:
                            self.db.update_qso_clublog_uploaded(qso.id, True)

                self.notify(
                    f"Club Log upload complete: {success} uploaded",
                    severity="information" if failed == 0 else "warning",
                )
            except ClubLogError as e:
                self.notify(f"Club Log upload error: {e}", severity="error")
            finally:
                await service.close()

        asyncio.create_task(do_upload())

    @on(Button.Pressed, "#close")
    def action_close(self) -> None:
        """Close the screen."""
        self.dismiss(self._active_log_id)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(self._active_log_id)
