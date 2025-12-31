"""Manual tune dialog for frequency and mode control."""

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ..models import Mode


class ManualTuneModal(ModalScreen[dict]):
    """Modal for manual frequency and mode tuning."""

    CSS = """
    ManualTuneModal {
        align: center middle;
    }

    ManualTuneModal > Vertical {
        width: 60;
        height: auto;
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

    .field-row {
        height: 3;
        align: left middle;
        margin-bottom: 1;
    }

    .field-row Label {
        width: 12;
        content-align: right middle;
        padding-right: 1;
    }

    .field-row Input, .field-row Select {
        width: 1fr;
    }

    .modal-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .modal-buttons Button {
        margin: 0 1;
    }

    .error-message {
        color: $error;
        text-align: center;
        height: 1;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        current_frequency: Optional[float] = None,
        current_mode: Optional[str] = None,
    ) -> None:
        """Initialize the manual tune modal.

        Args:
            current_frequency: Current frequency in MHz
            current_mode: Current mode string
        """
        super().__init__()
        self._current_frequency = current_frequency or 14.250
        self._current_mode = current_mode or Mode.SSB.value

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield Static("Manual Tune", classes="modal-title")
            yield Static("", id="error-message", classes="error-message")

            with Horizontal(classes="field-row"):
                yield Label("Frequency:")
                yield Input(
                    value=str(self._current_frequency),
                    placeholder="14.250",
                    id="frequency",
                )

            with Horizontal(classes="field-row"):
                yield Label("Mode:")
                yield Select(
                    [(mode.value, mode.value) for mode in Mode],
                    value=self._current_mode,
                    id="mode",
                )

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Tune", variant="primary", id="tune")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        """Handle cancel button."""
        self.dismiss({})

    @on(Button.Pressed, "#tune")
    def _on_tune(self) -> None:
        """Handle tune button."""
        # Validate frequency input
        freq_str = self.query_one("#frequency", Input).value.strip()
        try:
            frequency = float(freq_str)
            if frequency <= 0:
                raise ValueError("Frequency must be greater than 0")
        except ValueError:
            # Show error message
            error_msg = self.query_one("#error-message", Static)
            error_msg.update(f"Invalid frequency: {freq_str}")
            return

        # Get mode
        mode = self.query_one("#mode", Select).value

        # Return result
        self.dismiss({"frequency": frequency, "mode": mode})

    @on(Input.Submitted, "#frequency")
    def _on_frequency_submitted(self) -> None:
        """Handle Enter key in frequency field."""
        self._on_tune()
