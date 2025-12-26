"""Log browser screen for viewing and editing QSOs."""

from datetime import datetime
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
)

from ..database import Database
from ..models import Mode, QSO


class QSOEditModal(ModalScreen[Optional[QSO]]):
    """Modal dialog for editing a QSO."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
    ]

    CSS = """
    QSOEditModal {
        align: center middle;
    }

    QSOEditModal > Vertical {
        width: 70;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    .modal-title {
        text-align: center;
        text-style: bold;
        height: 1;
        margin-bottom: 1;
        color: $accent;
    }

    .edit-row {
        height: 3;
        margin-bottom: 1;
    }

    .edit-row Label {
        width: 15;
        content-align: right middle;
        padding-right: 1;
    }

    .edit-row Input {
        width: 1fr;
    }

    .edit-row Select {
        width: 1fr;
    }

    .edit-row-short Input {
        width: 20;
    }

    .edit-button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .edit-button-row Button {
        margin: 0 1;
    }

    .delete-button {
        background: $error;
    }
    """

    def __init__(self, qso: QSO, db: Database) -> None:
        super().__init__()
        self.qso = qso
        self.db = db

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"Edit QSO #{self.qso.id}", classes="modal-title")

            with Horizontal(classes="edit-row"):
                yield Label("Callsign:")
                yield Input(
                    value=self.qso.callsign,
                    id="edit_callsign",
                )

            with Horizontal(classes="edit-row"):
                yield Label("Frequency:")
                yield Input(
                    value=str(self.qso.frequency),
                    id="edit_frequency",
                )

            with Horizontal(classes="edit-row"):
                yield Label("Mode:")
                yield Select(
                    [(mode.value, mode.value) for mode in Mode],
                    value=self.qso.mode.value,
                    id="edit_mode",
                )

            with Horizontal(classes="edit-row"):
                yield Label("RST Sent:")
                yield Input(
                    value=self.qso.rst_sent,
                    id="edit_rst_sent",
                    classes="edit-row-short",
                )

            with Horizontal(classes="edit-row"):
                yield Label("RST Received:")
                yield Input(
                    value=self.qso.rst_received,
                    id="edit_rst_received",
                    classes="edit-row-short",
                )

            with Horizontal(classes="edit-row"):
                yield Label("Date:")
                yield Input(
                    value=self.qso.datetime_utc.strftime("%Y-%m-%d"),
                    id="edit_date",
                )

            with Horizontal(classes="edit-row"):
                yield Label("Time (UTC):")
                yield Input(
                    value=self.qso.datetime_utc.strftime("%H:%M"),
                    id="edit_time",
                )

            with Horizontal(classes="edit-row"):
                yield Label("Notes:")
                yield Input(
                    value=self.qso.notes,
                    id="edit_notes",
                )

            with Horizontal(classes="edit-button-row"):
                yield Button("Delete", variant="error", id="delete")
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Save", variant="primary", id="save")

    @on(Button.Pressed, "#save")
    def _on_save(self) -> None:
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.action_cancel()

    @on(Button.Pressed, "#delete")
    def _on_delete(self) -> None:
        self.action_delete()

    def action_save(self) -> None:
        """Save the edited QSO."""
        try:
            # Parse frequency
            freq_str = self.query_one("#edit_frequency", Input).value.strip()
            frequency = float(freq_str)

            # Parse datetime
            date_str = self.query_one("#edit_date", Input).value.strip()
            time_str = self.query_one("#edit_time", Input).value.strip()
            try:
                datetime_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            except ValueError:
                datetime_utc = self.qso.datetime_utc

            # Update QSO
            updated_qso = QSO(
                id=self.qso.id,
                callsign=self.query_one("#edit_callsign", Input).value.strip().upper(),
                frequency=frequency,
                mode=Mode(self.query_one("#edit_mode", Select).value),
                rst_sent=self.query_one("#edit_rst_sent", Input).value.strip() or "59",
                rst_received=self.query_one("#edit_rst_received", Input).value.strip() or "59",
                datetime_utc=datetime_utc,
                notes=self.query_one("#edit_notes", Input).value.strip(),
                contest_id=self.qso.contest_id,
                exchange_sent=self.qso.exchange_sent,
                exchange_received=self.qso.exchange_received,
            )

            # Save to database
            self.db.update_qso(updated_qso)
            self.dismiss(updated_qso)

        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel editing."""
        self.dismiss(None)

    def action_delete(self) -> None:
        """Delete the QSO."""
        if self.qso.id:
            self.db.delete_qso(self.qso.id)
            # Return a special marker to indicate deletion
            self.qso.id = -1  # Mark as deleted
            self.dismiss(self.qso)


class LogBrowserScreen(Screen):
    """Screen for browsing and editing log entries."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("f10", "go_back", "Back"),
        ("enter", "edit_selected", "Edit"),
        ("e", "edit_selected", "Edit"),
        ("d", "delete_selected", "Delete"),
        ("s", "search", "Search"),
        ("/", "search", "Search"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("g", "cursor_top", "Top"),
        ("G", "cursor_bottom", "Bottom"),
    ]

    CSS = """
    LogBrowserScreen {
        background: $surface;
    }

    .browser-container {
        height: 1fr;
        padding: 1;
    }

    .search-bar {
        height: 3;
        margin-bottom: 1;
    }

    .search-bar Label {
        width: 10;
        content-align: right middle;
        padding-right: 1;
    }

    .search-bar Input {
        width: 30;
    }

    .search-bar Static {
        width: 1fr;
        content-align: right middle;
        padding-right: 1;
    }

    .log-table {
        height: 1fr;
        border: solid $primary;
    }

    DataTable {
        height: 1fr;
    }

    .status-info {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    """

    COLUMNS = [
        ("#", 5),
        ("Date", 12),
        ("Time", 7),
        ("Callsign", 12),
        ("Frequency", 12),
        ("Mode", 8),
        ("RST S", 6),
        ("RST R", 6),
        ("Notes", 25),
    ]

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self._qsos: list[QSO] = []
        self._search_term = ""
        self._page = 0
        self._page_size = 100

    def compose(self) -> ComposeResult:
        yield Header()

        with Vertical(classes="browser-container"):
            with Horizontal(classes="search-bar"):
                yield Label("Search:")
                yield Input(
                    placeholder="Filter by callsign...",
                    id="search_input",
                )
                yield Static("", id="result_count")

            yield DataTable(id="log-table", cursor_type="row", classes="log-table")

        yield Static("", id="status-info", classes="status-info")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the log browser."""
        table = self.query_one(DataTable)

        # Add columns
        for name, width in self.COLUMNS:
            table.add_column(name, width=width)

        # Load all QSOs
        self._load_qsos()

    def _load_qsos(self, search: str = "") -> None:
        """Load QSOs from database."""
        if search:
            self._qsos = self.db.search_qsos(search)
        else:
            self._qsos = self.db.get_all_qsos(limit=1000)

        self._refresh_table()
        self._update_status()

    def _refresh_table(self) -> None:
        """Refresh the table display."""
        table = self.query_one(DataTable)
        table.clear()

        for qso in self._qsos:
            table.add_row(
                str(qso.id or ""),
                qso.date_str,
                qso.time_str,
                qso.callsign,
                f"{qso.frequency:.3f}",
                qso.mode.value,
                qso.rst_sent,
                qso.rst_received,
                (qso.notes[:25] + "...") if len(qso.notes) > 25 else qso.notes,
                key=str(qso.id) if qso.id else None,
            )

    def _update_status(self) -> None:
        """Update status bar."""
        count = len(self._qsos)
        total = self.db.get_qso_count()
        status = self.query_one("#status-info", Static)

        if self._search_term:
            status.update(f"Showing {count} of {total} QSOs (filtered)")
        else:
            status.update(f"Showing {count} QSOs | j/k: Navigate | Enter/e: Edit | d: Delete | /: Search")

        result_count = self.query_one("#result_count", Static)
        result_count.update(f"{count} QSOs")

    @on(Input.Submitted, "#search_input")
    def _on_search_submitted(self, event: Input.Submitted) -> None:
        """Handle search submission."""
        self._search_term = event.value.strip()
        self._load_qsos(self._search_term)
        # Focus the table after search
        self.query_one(DataTable).focus()

    @on(Input.Changed, "#search_input")
    def _on_search_changed(self, event: Input.Changed) -> None:
        """Handle search input changes (live search)."""
        self._search_term = event.value.strip()
        self._load_qsos(self._search_term)

    @on(DataTable.RowSelected)
    def _on_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection (double-click or Enter)."""
        self._edit_qso_at_cursor()

    def _get_selected_qso(self) -> Optional[QSO]:
        """Get the currently selected QSO."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._qsos):
            return self._qsos[table.cursor_row]
        return None

    def _edit_qso_at_cursor(self) -> None:
        """Edit the QSO at the current cursor position."""
        qso = self._get_selected_qso()
        if qso:
            self._edit_qso(qso)

    def _edit_qso(self, qso: QSO) -> None:
        """Open edit modal for a QSO."""

        def handle_edit_result(result: Optional[QSO]) -> None:
            if result is not None:
                if result.id == -1:
                    # QSO was deleted
                    self.notify("QSO deleted", severity="warning")
                else:
                    self.notify(f"QSO {result.callsign} updated")
                # Reload the table
                self._load_qsos(self._search_term)

        self.app.push_screen(QSOEditModal(qso, self.db), handle_edit_result)

    def action_go_back(self) -> None:
        """Return to main screen."""
        self.app.pop_screen()

    def action_edit_selected(self) -> None:
        """Edit the selected QSO."""
        self._edit_qso_at_cursor()

    def action_delete_selected(self) -> None:
        """Delete the selected QSO."""
        qso = self._get_selected_qso()
        if qso and qso.id:
            self.db.delete_qso(qso.id)
            self.notify(f"Deleted QSO with {qso.callsign}", severity="warning")
            self._load_qsos(self._search_term)

    def action_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search_input", Input).focus()

    def action_cursor_down(self) -> None:
        """Move cursor down in table."""
        table = self.query_one(DataTable)
        table.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up in table."""
        table = self.query_one(DataTable)
        table.action_cursor_up()

    def action_cursor_top(self) -> None:
        """Move cursor to top of table."""
        table = self.query_one(DataTable)
        table.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        """Move cursor to bottom of table."""
        table = self.query_one(DataTable)
        if self._qsos:
            table.move_cursor(row=len(self._qsos) - 1)
