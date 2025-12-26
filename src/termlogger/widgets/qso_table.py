"""QSO table widget for displaying logged contacts."""

from typing import Optional

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DataTable, Static

from ..models import QSO


class QSOTable(Static):
    """Widget for displaying QSO log entries in a table."""

    DEFAULT_CSS = """
    QSOTable {
        height: 100%;
        width: 100%;
        border: solid $primary;
        overflow: auto;
        scrollbar-gutter: stable;
    }

    QSOTable DataTable {
        height: 1fr;
        width: 100%;
        scrollbar-gutter: stable;
    }
    """

    class QSOSelected(Message):
        """Message sent when a QSO is selected."""

        def __init__(self, qso: QSO) -> None:
            self.qso = qso
            super().__init__()

    COLUMNS = [
        ("#", 4),
        ("Time", 6),
        ("Date", 11),
        ("Callsign", 12),
        ("Freq", 10),
        ("Mode", 6),
        ("Sent", 5),
        ("Recv", 5),
        ("Notes", None),  # None = auto-expand to fill remaining space
    ]

    def __init__(self, id: Optional[str] = None) -> None:
        super().__init__(id=id)
        self._qsos: list[QSO] = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield DataTable(id="qso-table", cursor_type="row")

    def on_mount(self) -> None:
        """Initialize the table."""
        table = self.query_one(DataTable)

        # Add columns
        for name, width in self.COLUMNS:
            table.add_column(name, width=width)

    def load_qsos(self, qsos: list[QSO]) -> None:
        """Load QSOs into the table."""
        self._qsos = qsos
        self._refresh_table()

    def add_qso(self, qso: QSO) -> None:
        """Add a new QSO to the top of the table."""
        self._qsos.insert(0, qso)
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Refresh the table display."""
        table = self.query_one(DataTable)
        table.clear()

        for i, qso in enumerate(self._qsos, 1):
            table.add_row(
                str(i),
                qso.time_str,
                qso.date_str,
                qso.callsign,
                f"{qso.frequency:.3f}",
                qso.mode.value,
                qso.rst_sent,
                qso.rst_received,
                qso.notes[:20] if qso.notes else "",
                key=str(qso.id) if qso.id else str(i),
            )

    def get_selected_qso(self) -> Optional[QSO]:
        """Get the currently selected QSO."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._qsos):
            return self._qsos[table.cursor_row]
        return None

    @property
    def qso_count(self) -> int:
        """Get the number of QSOs in the table."""
        return len(self._qsos)
