"""QSO entry form widget."""

import logging
from datetime import datetime, timezone
from typing import Optional

from rich.console import RenderableType
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.events import Blur, Focus, Key, MouseDown
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select, Static

from ..models import Mode, QSO

logger = logging.getLogger(__name__)


class ClickableLabel(Widget):
    """Clickable label widget for form fields that can trigger actions."""

    DEFAULT_CSS = """
    ClickableLabel {
        width: auto;
        height: 3;
        color: $text-muted;
        padding: 1 0 0 0;
        margin-right: 0;
    }

    ClickableLabel:hover {
        color: $accent;
        text-style: bold;
    }
    """

    class Clicked(Message):
        """Message sent when label is clicked."""

        def __init__(self, action_id: str) -> None:
            self.action_id = action_id
            super().__init__()

    def __init__(self, label: str, action_id: str, **kwargs) -> None:
        """Initialize clickable label.

        Args:
            label: Display text (e.g., "Freq:")
            action_id: Action identifier (e.g., "read-rig")
        """
        super().__init__(**kwargs)
        self.label = label
        self.action_id = action_id

    def render(self) -> RenderableType:
        """Render the label as clickable text."""
        return Text(self.label, style="")

    def on_mouse_down(self, event: MouseDown) -> None:
        """Handle click by posting message."""
        self.post_message(self.Clicked(self.action_id))
        event.stop()


class SmartInput(Input):
    """Input widget that intercepts +/- keys for increment/decrement."""

    class IncrementRequest(Message):
        """Message sent when +/- key is pressed."""

        def __init__(self, field_id: str, increment: int) -> None:
            self.field_id = field_id
            self.increment = increment
            super().__init__()

    def on_key(self, event: Key) -> None:
        """Intercept +/- keys before Input processes them (only for numeric/date fields)."""
        # Only intercept +/- for specific fields (not callsign, notes, etc.)
        numeric_fields = {"frequency", "rst_sent", "rst_received", "time", "date"}

        if self.id not in numeric_fields:
            # Let +/- type normally in text fields
            return

        # Check for +/- keys FIRST before Input can insert them
        # Handle various key names: +, plus, minus, -, equals_sign (Shift+=)
        if event.key in ("+", "plus", "minus", "-", "equals_sign"):
            # Check if it's really a + (could be Shift+= or just +)
            is_plus = event.key in ("+", "plus") or (event.key == "equals_sign" and event.character == "+")

            # Prevent Input from inserting the character
            event.prevent_default()
            event.stop()

            # Determine increment direction
            increment = 1 if is_plus or event.key == "equals_sign" else -1

            # Post message to parent with field ID and increment
            if self.id:
                self.post_message(self.IncrementRequest(self.id, increment))

        # For all other keys, don't prevent - let them bubble normally


class QSOEntryForm(Static):
    """Widget for entering QSO data."""

    DEFAULT_CSS = """
    QSOEntryForm {
        height: auto;
        padding: 0 1;
        background: $surface;
    }

    QSOEntryForm .form-row {
        height: 5;
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
        width: 16;
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

    QSOEntryForm .park-input {
        width: 14;
    }

    QSOEntryForm .pota-row {
        height: 5;
        margin-bottom: 0;
    }

    QSOEntryForm .pota-row.hidden {
        display: none;
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
            yield SmartInput(
                placeholder="W1ABC",
                id="callsign",
                classes="callsign-input",
            )
            yield ClickableLabel("Freq:", "read-rig")
            yield SmartInput(
                placeholder="14.250",
                id="frequency",
                classes="freq-input",
            )
            yield ClickableLabel("Mode:", "read-rig")
            yield Select(
                [(mode.value, mode.value) for mode in Mode],
                value="SSB",
                id="mode",
                classes="mode-select",
            )

        # Row 2: RST Sent/Received, Time, Date
        with Horizontal(classes="form-row"):
            yield Label("Sent:")
            yield SmartInput(
                value="59",
                id="rst_sent",
                classes="rst-input",
            )
            yield Label("Rcvd:")
            yield SmartInput(
                value="59",
                id="rst_received",
                classes="rst-input",
            )
            yield ClickableLabel("UTC:", "read-time")
            yield SmartInput(
                id="time",
                classes="time-input",
            )
            yield ClickableLabel("Date:", "read-time")
            yield SmartInput(
                id="date",
                classes="date-input",
            )

        # POTA Row: Their park reference (for P2P contacts) - hidden by default
        with Horizontal(classes="pota-row hidden", id="pota-row"):
            yield Label("Their Park:")
            yield SmartInput(
                placeholder="K-1234",
                id="their_park",
                classes="park-input",
            )
            yield Label("Name:")
            yield SmartInput(
                placeholder="Operator name",
                id="op_name",
                classes="notes-input",
            )

        # Row 3: Notes and More button
        with Horizontal(classes="form-row"):
            yield Label("Notes:")
            yield SmartInput(
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
        self.update_datetime()
        # Focus on callsign field
        self.query_one("#callsign", SmartInput).focus()

    def update_datetime(self) -> None:
        """Update time and date fields with current UTC time."""
        now = datetime.now(timezone.utc)
        self.query_one("#time", SmartInput).value = now.strftime("%H:%M")
        self.query_one("#date", SmartInput).value = now.strftime("%Y-%m-%d")

    def on_focus(self, event: Focus) -> None:
        """Select all text when any input field receives focus."""
        # Only select all if the focused widget is a SmartInput
        if isinstance(event.widget, SmartInput):
            event.widget.select_all()

    def on_smart_input_increment_request(self, event: SmartInput.IncrementRequest) -> None:
        """Handle increment/decrement requests from SmartInput widgets."""
        field_id = event.field_id
        increment = event.increment

        # Find the input widget by ID
        try:
            input_widget = self.query_one(f"#{field_id}", SmartInput)

            if field_id == "frequency":
                self._increment_frequency(input_widget, increment)
            elif field_id in ("rst_sent", "rst_received"):
                self._increment_rst(input_widget, increment)
            elif field_id == "time":
                self._increment_time(input_widget, increment)
            elif field_id == "date":
                self._increment_date(input_widget, increment)
        except Exception as e:
            logger.debug(f"Failed to increment field {field_id}: {e}")

    def _increment_frequency(self, input_widget: Input, increment: int) -> None:
        """Increment frequency based on cursor position."""
        value = input_widget.value.strip()
        if not value:
            return

        try:
            freq = float(value)
            cursor_pos = input_widget.cursor_position

            # Determine increment amount based on cursor position
            # Format: "14.250" - positions 0,1 = MHz, 3,4,5 = decimal places
            if "." in value:
                decimal_pos = value.index(".")
                if cursor_pos <= decimal_pos:
                    # On integer part (MHz)
                    delta = 1.0
                else:
                    # On decimal part - determine which decimal place
                    decimals_after = cursor_pos - decimal_pos - 1
                    if decimals_after == 0:
                        delta = 0.1
                    elif decimals_after == 1:
                        delta = 0.01
                    else:
                        delta = 0.001
            else:
                # No decimal, increment by 1 MHz
                delta = 1.0

            new_freq = freq + (delta * increment)
            # Keep frequency positive and reasonable (1-1000 MHz)
            new_freq = max(1.0, min(1000.0, new_freq))

            # Format with 3 decimal places
            input_widget.value = f"{new_freq:.3f}"
            # Restore cursor position
            input_widget.cursor_position = cursor_pos
        except ValueError:
            pass

    def _increment_rst(self, input_widget: Input, increment: int) -> None:
        """Increment RST based on cursor position."""
        value = input_widget.value.strip()
        if not value or not value.isdigit():
            return

        cursor_pos = input_widget.cursor_position

        # Convert to list for easy modification
        digits = list(value)

        # Determine which digit to increment (cursor position or last digit)
        if cursor_pos > 0:
            digit_idx = min(cursor_pos - 1, len(digits) - 1)
        else:
            digit_idx = 0

        # Increment the digit
        current = int(digits[digit_idx])
        new_digit = (current + increment) % 10
        if new_digit < 0:
            new_digit = 9

        digits[digit_idx] = str(new_digit)
        input_widget.value = "".join(digits)
        input_widget.cursor_position = cursor_pos

    def _increment_time(self, input_widget: Input, increment: int) -> None:
        """Increment time (HH:MM) with rollover to next day."""
        value = input_widget.value.strip()
        if not value or ":" not in value:
            return

        try:
            parts = value.split(":")
            if len(parts) != 2:
                return

            hours = int(parts[0])
            minutes = int(parts[1])
            cursor_pos = input_widget.cursor_position

            # Determine if cursor is on hours or minutes
            colon_pos = value.index(":")
            if cursor_pos <= colon_pos:
                # Increment hours
                hours = (hours + increment) % 24
                if hours < 0:
                    hours = 23
            else:
                # Increment minutes
                minutes += increment
                # Handle rollover
                if minutes >= 60:
                    minutes = 0
                    hours = (hours + 1) % 24
                elif minutes < 0:
                    minutes = 59
                    hours = (hours - 1) % 24
                    if hours < 0:
                        hours = 23

            input_widget.value = f"{hours:02d}:{minutes:02d}"
            input_widget.cursor_position = cursor_pos
        except (ValueError, IndexError):
            pass

    def _increment_date(self, input_widget: Input, increment: int) -> None:
        """Increment date (YYYY-MM-DD) with proper month/year rollover."""
        from datetime import datetime, timedelta

        value = input_widget.value.strip()
        if not value:
            return

        try:
            # Parse the date
            date_obj = datetime.strptime(value, "%Y-%m-%d")
            cursor_pos = input_widget.cursor_position

            # Determine which part to increment based on cursor position
            # Format: "2026-01-01" positions 0-3=year, 5-6=month, 8-9=day
            if cursor_pos <= 4:
                # Year - add/subtract 365 days (approximate)
                date_obj = date_obj + timedelta(days=365 * increment)
            elif cursor_pos <= 7:
                # Month - add/subtract ~30 days then adjust to same day of month
                current_day = date_obj.day
                # Move to first of month, then add months
                date_obj = date_obj.replace(day=1)

                new_month = date_obj.month + increment
                new_year = date_obj.year

                # Handle year rollover
                while new_month > 12:
                    new_month -= 12
                    new_year += 1
                while new_month < 1:
                    new_month += 12
                    new_year -= 1

                date_obj = date_obj.replace(year=new_year, month=new_month)

                # Try to restore the day, but handle month-end cases
                try:
                    date_obj = date_obj.replace(day=current_day)
                except ValueError:
                    # Day doesn't exist in new month (e.g., Jan 31 -> Feb)
                    # Use last day of month
                    if new_month == 12:
                        date_obj = date_obj.replace(year=new_year + 1, month=1, day=1)
                    else:
                        date_obj = date_obj.replace(month=new_month + 1, day=1)
                    date_obj = date_obj - timedelta(days=1)
            else:
                # Day
                date_obj = date_obj + timedelta(days=increment)

            input_widget.value = date_obj.strftime("%Y-%m-%d")
            input_widget.cursor_position = cursor_pos
        except (ValueError, OverflowError):
            pass

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
        logger.info(f"Input submitted event received from field: {event.input.id}")
        self._log_qso()

    @on(Button.Pressed, "#log-qso")
    def _on_log_button(self) -> None:
        """Handle Log QSO button press."""
        logger.info("Log QSO button pressed - calling _log_qso()")
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
        logger.info("_log_qso called - starting QSO validation")

        try:
            callsign = self.query_one("#callsign", SmartInput).value.strip().upper()
            freq_str = self.query_one("#frequency", SmartInput).value.strip()
            mode_value = self.query_one("#mode", Select).value
            rst_sent = self.query_one("#rst_sent", SmartInput).value.strip()
            rst_received = self.query_one("#rst_received", SmartInput).value.strip()
            time_str = self.query_one("#time", SmartInput).value.strip()
            date_str = self.query_one("#date", SmartInput).value.strip()
            notes = self.query_one("#notes", SmartInput).value.strip()

            logger.debug(f"QSO data: callsign={callsign}, freq={freq_str}, mode={mode_value}")

            # Get POTA fields (may be hidden but still accessible)
            their_park = self.query_one("#their_park", SmartInput).value.strip().upper()
            op_name = self.query_one("#op_name", SmartInput).value.strip()

            # Validate required fields
            if not callsign:
                logger.warning("Validation failed: Callsign required")
                self.query_one("#status", Static).update("[red]Callsign required[/red]")
                self.query_one("#callsign", SmartInput).focus()
                return

            if not freq_str:
                logger.warning("Validation failed: Frequency required")
                self.query_one("#status", Static).update("[red]Frequency required[/red]")
                self.query_one("#frequency", SmartInput).focus()
                return

            try:
                frequency = float(freq_str)
                logger.debug(f"Frequency parsed: {frequency}")
            except ValueError:
                logger.warning(f"Validation failed: Invalid frequency '{freq_str}'")
                self.query_one("#status", Static).update("[red]Invalid frequency[/red]")
                self.query_one("#frequency", SmartInput).focus()
                return

            # Parse datetime
            try:
                datetime_utc = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                logger.debug(f"Datetime parsed: {datetime_utc}")
            except ValueError as e:
                logger.debug(f"Datetime parse failed, using current time: {e}")
                datetime_utc = datetime.now(timezone.utc).replace(tzinfo=None)

            # Build QSO fields
            qso_fields = {
                "callsign": callsign,
                "frequency": frequency,
                "mode": Mode(mode_value),
                "rst_sent": rst_sent or "59",
                "rst_received": rst_received or "59",
                "datetime_utc": datetime_utc,
                "notes": notes,
            }

            # Add POTA fields if present
            if their_park:
                qso_fields["pota_ref"] = their_park
            if op_name:
                qso_fields["name"] = op_name

            # Include extended fields
            qso_fields.update(self._extended_fields)

            logger.debug(f"Creating QSO object with fields: {qso_fields.keys()}")
            # Create QSO
            qso = QSO(**qso_fields)

            # Emit message
            logger.info(f"Posting QSOLogged message for {callsign}")
            self.post_message(self.QSOLogged(qso))

            # Clear form for next QSO
            logger.debug("Clearing form")
            self.clear_form()
            logger.info("QSO logging completed successfully")

        except Exception as e:
            logger.error(f"Exception in _log_qso: {e}", exc_info=True)
            self.query_one("#status", Static).update(f"[red]Error: {e}[/red]")

    def clear_form(self) -> None:
        """Clear the form for a new QSO."""
        self.query_one("#callsign", SmartInput).value = ""
        self.query_one("#notes", SmartInput).value = ""
        self.query_one("#their_park", SmartInput).value = ""
        self.query_one("#op_name", SmartInput).value = ""
        self.query_one("#status", Static).update("")
        self._is_dupe = False
        self._extended_fields = {}  # Clear extended fields
        self.update_datetime()
        self.query_one("#callsign", SmartInput).focus()

    def set_frequency(self, freq: float) -> None:
        """Set the frequency field."""
        self.query_one("#frequency", SmartInput).value = str(freq)

    def set_mode(self, mode: str) -> None:
        """Set the mode field."""
        self.query_one("#mode", Select).value = mode

    def set_pota_mode(self, enabled: bool) -> None:
        """Show or hide POTA-specific fields.

        Args:
            enabled: True to show POTA fields, False to hide
        """
        pota_row = self.query_one("#pota-row")
        if enabled:
            pota_row.remove_class("hidden")
        else:
            pota_row.add_class("hidden")
            # Clear values when hiding
            self.query_one("#their_park", SmartInput).value = ""
            self.query_one("#op_name", SmartInput).value = ""

    def set_their_park(self, park_ref: str) -> None:
        """Set the 'their park' field (for P2P contacts).

        Args:
            park_ref: Park reference like K-1234
        """
        self.query_one("#their_park", SmartInput).value = park_ref.upper() if park_ref else ""

    def set_op_name(self, name: str) -> None:
        """Set the operator name field.

        Args:
            name: Operator name
        """
        self.query_one("#op_name", SmartInput).value = name or ""
