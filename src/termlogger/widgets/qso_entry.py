"""QSO entry form widget."""

from datetime import datetime, timezone
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Blur
from textual.message import Message
from textual.widgets import Button, Input, Label, Select, Static

from ..models import Mode, QSO


class QSOEntryForm(Static):
    """Widget for entering QSO data."""

    DEFAULT_CSS = """
    QSOEntryForm {
        height: auto;
        padding: 0 1;
        background: $surface;
    }

    QSOEntryForm .form-row {
        height: 4;
        margin-bottom: 0;
    }

    QSOEntryForm Label {
        width: auto;
        height: 3;
        color: $text-muted;
        padding: 1 0 0 0;
        margin-right: 0;
    }

    QSOEntryForm Input {
        background: $surface-lighten-1;
        margin-right: 2;
    }

    QSOEntryForm Input:focus {
        background: $surface-lighten-2;
    }

    QSOEntryForm Select {
        margin-right: 2;
    }

    QSOEntryForm SelectCurrent {
        background: $surface-lighten-1;
        border: solid $primary;
    }

    QSOEntryForm Select:focus SelectCurrent {
        background: $surface-lighten-2;
    }

    QSOEntryForm .callsign-input {
        width: 12;
    }

    QSOEntryForm .freq-input {
        width: 14;
    }

    QSOEntryForm .mode-select {
        width: 16;
    }

    QSOEntryForm .rst-input {
        width: 10;
    }

    QSOEntryForm .time-input {
        width: 14;
    }

    QSOEntryForm .date-input {
        width: 16;
    }

    QSOEntryForm .notes-input {
        width: 1fr;
        margin-right: 1;
    }

    QSOEntryForm .dupe-warning {
        color: $error;
        text-style: bold;
    }

    QSOEntryForm .button-row {
        height: 3;
        align: left middle;
        margin-top: 0;
    }

    QSOEntryForm .button-row Static {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }

    QSOEntryForm .log-btn {
        height: 3;
        min-width: 10;
        border: solid $primary;
        background: $primary;
    }

    QSOEntryForm .more-btn {
        height: 3;
        min-width: 8;
        border: solid $surface-lighten-2;
        background: $surface-lighten-2;
    }

    QSOEntryForm Button {
        height: 3;
        min-height: 3;
        padding: 0 1;
    }
    """

    class QSOLogged(Message):
        """Message sent when a QSO is logged."""

        def __init__(self, qso: QSO) -> None:
            self.qso = qso
            super().__init__()

    class CallsignChanged(Message):
        """Message sent when callsign changes (for lookup)."""

        def __init__(self, callsign: str) -> None:
            self.callsign = callsign
            super().__init__()

    class CallsignBlurred(Message):
        """Message sent when callsign field loses focus (for lookup)."""

        def __init__(self, callsign: str) -> None:
            self.callsign = callsign
            super().__init__()

    def __init__(self, id: Optional[str] = None) -> None:
        super().__init__(id=id)
        self._is_dupe = False
        self._extended_fields: dict = {}  # Store extended ADIF fields

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Row 1: Callsign, Frequency, Mode
        with Horizontal(classes="form-row"):
            yield Label("Callsign:")
            yield Input(
                placeholder="W1ABC",
                id="callsign",
                classes="callsign-input",
            )
            yield Label("Freq:")
            yield Input(
                placeholder="14.250",
                id="frequency",
                classes="freq-input",
            )
            yield Label("Mode:")
            yield Select(
                [(mode.value, mode.value) for mode in Mode],
                value="SSB",
                id="mode",
                classes="mode-select",
            )

        # Row 2: RST Sent/Received, Time, Date
        with Horizontal(classes="form-row"):
            yield Label("Sent:")
            yield Input(
                value="59",
                id="rst_sent",
                classes="rst-input",
            )
            yield Label("Rcvd:")
            yield Input(
                value="59",
                id="rst_received",
                classes="rst-input",
            )
            yield Label("UTC:")
            yield Input(
                id="time",
                classes="time-input",
            )
            yield Label("Date:")
            yield Input(
                id="date",
                classes="date-input",
            )

        # Row 3: Notes and More button
        with Horizontal(classes="form-row"):
            yield Label("Notes:")
            yield Input(
                placeholder="Optional notes...",
                id="notes",
                classes="notes-input",
            )
            yield Button("More...", id="more-fields", classes="more-btn", variant="default")

        # Button row
        with Horizontal(classes="button-row"):
            yield Static("", id="status")
            yield Button("Log QSO", id="log-qso", classes="log-btn", variant="primary")

    def on_mount(self) -> None:
        """Initialize form when mounted."""
        self._update_datetime()
        # Focus on callsign field
        self.query_one("#callsign", Input).focus()

    def _update_datetime(self) -> None:
        """Update time and date fields with current UTC time."""
        now = datetime.now(timezone.utc)
        self.query_one("#time", Input).value = now.strftime("%H:%M")
        self.query_one("#date", Input).value = now.strftime("%Y-%m-%d")

    @on(Input.Changed, "#callsign")
    def _on_callsign_changed(self, event: Input.Changed) -> None:
        """Handle callsign input changes."""
        callsign = event.value.upper()
        # Update input to uppercase
        event.input.value = callsign
        # Emit event for callsign lookup
        if len(callsign) >= 3:
            self.post_message(self.CallsignChanged(callsign))

    def on_blur(self, event: Blur) -> None:
        """Handle blur events - trigger lookup when callsign loses focus."""
        # Check if the blur came from the callsign input by checking widget id
        try:
            if hasattr(event.widget, 'id') and event.widget.id == "callsign":
                callsign = event.widget.value.strip().upper()
                if len(callsign) >= 3:
                    self.post_message(self.CallsignBlurred(callsign))
        except Exception:
            pass

    @on(Input.Submitted)
    def _on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in any input field."""
        self._log_qso()

    @on(Button.Pressed, "#log-qso")
    def _on_log_button(self) -> None:
        """Handle Log QSO button press."""
        self._log_qso()

    @on(Button.Pressed, "#more-fields")
    def _on_more_fields(self) -> None:
        """Show extended fields modal."""
        from .extended_fields import ExtendedFieldsModal

        def handle_result(result: dict) -> None:
            if result:
                self._extended_fields.update(result)
                # Update status to show fields are set
                count = len(self._extended_fields)
                if count > 0:
                    self.query_one("#status", Static).update(
                        f"[dim]{count} extended field(s) set[/dim]"
                    )

        self.app.push_screen(
            ExtendedFieldsModal(self._extended_fields.copy()),
            handle_result
        )

    def set_dupe_status(self, is_dupe: bool) -> None:
        """Set duplicate status for current callsign."""
        self._is_dupe = is_dupe
        status = self.query_one("#status", Static)
        if is_dupe:
            status.update("[bold red]DUPE![/bold red]")
            status.add_class("dupe-warning")
        else:
            status.update("")
            status.remove_class("dupe-warning")

    def _log_qso(self) -> None:
        """Validate and log the QSO."""
        callsign = self.query_one("#callsign", Input).value.strip().upper()
        freq_str = self.query_one("#frequency", Input).value.strip()
        mode_value = self.query_one("#mode", Select).value
        rst_sent = self.query_one("#rst_sent", Input).value.strip()
        rst_received = self.query_one("#rst_received", Input).value.strip()
        time_str = self.query_one("#time", Input).value.strip()
        date_str = self.query_one("#date", Input).value.strip()
        notes = self.query_one("#notes", Input).value.strip()

        # Validate required fields
        if not callsign:
            self.query_one("#status", Static).update("[red]Callsign required[/red]")
            self.query_one("#callsign", Input).focus()
            return

        if not freq_str:
            self.query_one("#status", Static).update("[red]Frequency required[/red]")
            self.query_one("#frequency", Input).focus()
            return

        try:
            frequency = float(freq_str)
        except ValueError:
            self.query_one("#status", Static).update("[red]Invalid frequency[/red]")
            self.query_one("#frequency", Input).focus()
            return

        # Parse datetime
        try:
            datetime_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            datetime_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        # Create QSO with extended fields
        qso = QSO(
            callsign=callsign,
            frequency=frequency,
            mode=Mode(mode_value),
            rst_sent=rst_sent or "59",
            rst_received=rst_received or "59",
            datetime_utc=datetime_utc,
            notes=notes,
            **self._extended_fields,  # Include extended fields
        )

        # Emit message
        self.post_message(self.QSOLogged(qso))

        # Clear form for next QSO
        self.clear_form()

    def clear_form(self) -> None:
        """Clear the form for a new QSO."""
        self.query_one("#callsign", Input).value = ""
        self.query_one("#notes", Input).value = ""
        self.query_one("#status", Static).update("")
        self._is_dupe = False
        self._extended_fields = {}  # Clear extended fields
        self._update_datetime()
        self.query_one("#callsign", Input).focus()

    def set_frequency(self, freq: float) -> None:
        """Set the frequency field."""
        self.query_one("#frequency", Input).value = str(freq)

    def set_mode(self, mode: str) -> None:
        """Set the mode field."""
        self.query_one("#mode", Select).value = mode
