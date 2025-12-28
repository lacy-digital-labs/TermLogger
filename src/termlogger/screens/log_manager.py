"""Log manager screen for creating and managing virtual logs."""

from datetime import datetime, timezone
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
        padding: 1 2;
    }

    LogCreateModal .title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        color: $primary;
    }

    LogCreateModal .form-row {
        height: 3;
        margin-bottom: 1;
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
        margin-top: 1;
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
        padding: 1 2;
    }

    LogManagerScreen .title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        color: $primary;
        height: 2;
    }

    LogManagerScreen .subtitle {
        text-align: center;
        color: $text-muted;
        height: 1;
        margin-bottom: 1;
    }

    LogManagerScreen DataTable {
        height: 1fr;
        margin-bottom: 1;
    }

    LogManagerScreen .button-row {
        height: 3;
        align: center middle;
    }

    LogManagerScreen .button-row Button {
        margin: 0 1;
    }

    LogManagerScreen .info-row {
        height: 1;
        margin-bottom: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("n", "new_log", "New Log"),
        ("enter", "select_log", "Select"),
        ("a", "archive_log", "Archive"),
    ]

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._logs: list[Log] = []
        self._active_log_id: Optional[int] = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Log Manager", classes="title")
            yield Static(
                "Select a log to make it active, or create a new one",
                classes="subtitle",
            )
            yield Static("", id="active-info", classes="info-row")
            yield DataTable(id="logs-table", cursor_type="row")
            with Horizontal(classes="button-row"):
                yield Button("New Log (N)", id="new-log", variant="primary")
                yield Button("Select (Enter)", id="select-log", variant="success")
                yield Button("View All QSOs", id="view-all")
                yield Button("Archive (A)", id="archive-log", variant="warning")
                yield Button("Close (Esc)", id="close")

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
        self._logs = self.db.get_all_logs(include_archived=False)
        active_log = self.db.get_active_log()
        self._active_log_id = active_log.id if active_log else None

        # Update info row
        info = self.query_one("#active-info", Static)
        if active_log:
            info.update(
                f"[bold]Active Log:[/bold] {active_log.display_name} ({active_log.qso_count} QSOs)"
            )
        else:
            info.update("[dim]No active log - QSOs will be logged without a log association[/dim]")

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
        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._logs):
            log = self._logs[table.cursor_row]
            self.db.set_active_log(log.id)
            self._refresh_logs()
            self.notify(f"Activated log: {log.name}")

    @on(Button.Pressed, "#view-all")
    def _on_view_all(self) -> None:
        """Clear active log to view all QSOs."""
        self.db.set_active_log(None)
        self._refresh_logs()
        self.notify("Cleared active log - viewing all QSOs")

    @on(Button.Pressed, "#archive-log")
    def action_archive_log(self) -> None:
        """Archive the selected log."""
        table = self.query_one("#logs-table", DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._logs):
            log = self._logs[table.cursor_row]
            self.db.archive_log(log.id)
            self._refresh_logs()
            self.notify(f"Archived log: {log.name}")

    @on(Button.Pressed, "#close")
    def action_close(self) -> None:
        """Close the screen."""
        self.dismiss(self._active_log_id)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(self._active_log_id)
