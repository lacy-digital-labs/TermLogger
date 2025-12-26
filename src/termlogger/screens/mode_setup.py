"""Mode selection and setup screens."""

from datetime import datetime
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
)

from ..modes import (
    ContestConfig,
    ContestMode,
    FieldDayConfig,
    FieldDayMode,
    ModeType,
    OperatingMode,
    POTAConfig,
    POTAMode,
)
from ..modes.fieldday import ARRL_SECTIONS


class ModeSelectScreen(ModalScreen[Optional[ModeType | str]]):
    """Screen for selecting an operating mode."""

    CSS = """
    ModeSelectScreen {
        align: center middle;
    }

    ModeSelectScreen > Vertical {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    .mode-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    .mode-list {
        height: auto;
        max-height: 20;
        border: solid $primary;
        margin-bottom: 1;
    }

    .mode-description {
        height: auto;
        padding: 1;
        background: $surface-darken-1;
        margin-bottom: 1;
    }

    .mode-buttons {
        height: 3;
        align: center middle;
    }

    .mode-buttons Button {
        margin: 0 1;
    }
    """

    MODES = [
        (ModeType.GENERAL, "General Logging", "Standard QSO logging without special modes"),
        (ModeType.CONTEST, "Contest", "Contest logging with serial numbers and scoring"),
        (ModeType.POTA, "POTA Activation", "Activate a park - you're at the park making contacts"),
        ("pota_hunter", "POTA Hunter", "Hunt park activators - log contacts with stations at parks"),
        (ModeType.FIELDDAY, "ARRL Field Day", "Field Day with class/section exchange"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._selected_mode: Optional[ModeType | str] = ModeType.GENERAL

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Select Operating Mode", classes="mode-title")

            items = []
            for mode_type, name, _ in self.MODES:
                # Handle both ModeType enum and string values
                mode_value = mode_type.value if isinstance(mode_type, ModeType) else mode_type
                items.append(ListItem(Label(f"{name}"), id=f"mode_{mode_value}"))

            yield ListView(*items, id="mode-list", classes="mode-list")

            yield Static(self.MODES[0][2], id="mode-desc", classes="mode-description")

            with Horizontal(classes="mode-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Select", variant="primary", id="select")

    def on_mount(self) -> None:
        """Focus the list."""
        self.query_one(ListView).focus()

    @on(ListView.Highlighted)
    def _on_highlighted(self, event: ListView.Highlighted) -> None:
        """Update description when selection changes."""
        if event.item:
            item_id = event.item.id or ""
            mode_value = item_id.replace("mode_", "")
            for mode_type, name, desc in self.MODES:
                # Handle both ModeType enum and string values
                check_value = mode_type.value if isinstance(mode_type, ModeType) else mode_type
                if check_value == mode_value:
                    self._selected_mode = mode_type
                    self.query_one("#mode-desc", Static).update(desc)
                    break

    @on(ListView.Selected)
    def _on_selected(self, event: ListView.Selected) -> None:
        """Handle double-click selection."""
        self.dismiss(self._selected_mode)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#select")
    def _on_select(self) -> None:
        self.dismiss(self._selected_mode)


class ContestSetupScreen(ModalScreen[Optional[ContestMode]]):
    """Screen for setting up a contest."""

    CSS = """
    ContestSetupScreen {
        align: center middle;
    }

    ContestSetupScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    .setup-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    .setup-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $secondary;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .setup-row {
        height: 3;
        margin-bottom: 1;
    }

    .setup-row Label {
        width: 18;
        content-align: right middle;
        padding-right: 1;
    }

    .setup-row Input, .setup-row Select {
        width: 1fr;
    }

    .setup-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .setup-buttons Button {
        margin: 0 1;
    }
    """

    EXCHANGE_FORMATS = [
        ("RST + Serial", "RST+SERIAL"),
        ("RST + Zone", "RST+ZONE"),
        ("RST + State/Province", "RST+STATE"),
        ("RST + Name", "RST+NAME"),
        ("RST + Serial + Zone", "RST+SERIAL+ZONE"),
        ("RST + Name + State", "RST+NAME+STATE"),
    ]

    def __init__(self, my_callsign: str = "", my_exchange: str = "") -> None:
        super().__init__()
        self._my_callsign = my_callsign
        self._my_exchange = my_exchange

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Contest Setup", classes="setup-title")

            with VerticalScroll():
                with Vertical(classes="setup-section"):
                    yield Static("Contest Information", classes="section-title")

                    with Horizontal(classes="setup-row"):
                        yield Label("Contest Name:")
                        yield Input(placeholder="e.g., CQ WW DX SSB", id="contest_name")

                    with Horizontal(classes="setup-row"):
                        yield Label("Contest ID:")
                        yield Input(placeholder="e.g., CQ-WW-SSB", id="contest_id")

                    with Horizontal(classes="setup-row"):
                        yield Label("Exchange Format:")
                        yield Select(
                            [(name, value) for name, value in self.EXCHANGE_FORMATS],
                            value="RST+SERIAL",
                            id="exchange_format",
                        )

                with Vertical(classes="setup-section"):
                    yield Static("My Station", classes="section-title")

                    with Horizontal(classes="setup-row"):
                        yield Label("My Callsign:")
                        yield Input(value=self._my_callsign, id="my_callsign")

                    with Horizontal(classes="setup-row"):
                        yield Label("My Exchange:")
                        yield Input(
                            value=self._my_exchange,
                            placeholder="e.g., 05 (zone) or NJ (state)",
                            id="my_exchange",
                        )

                    with Horizontal(classes="setup-row"):
                        yield Label("Starting Serial:")
                        yield Input(value="1", id="starting_serial")

                    with Horizontal(classes="setup-row"):
                        yield Label("Power:")
                        yield Select(
                            [("High (>150W)", "HIGH"), ("Low (<=150W)", "LOW"), ("QRP (<=5W)", "QRP")],
                            value="HIGH",
                            id="power",
                        )

            with Horizontal(classes="setup-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Start Contest", variant="primary", id="start")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#start")
    def _on_start(self) -> None:
        try:
            config = ContestConfig(
                name=self.query_one("#contest_name", Input).value.strip(),
                contest_name=self.query_one("#contest_name", Input).value.strip(),
                contest_id=self.query_one("#contest_id", Input).value.strip(),
                exchange_format=self.query_one("#exchange_format", Select).value or "RST+SERIAL",
                my_callsign=self.query_one("#my_callsign", Input).value.strip().upper(),
                my_exchange=self.query_one("#my_exchange", Input).value.strip(),
                starting_serial=int(self.query_one("#starting_serial", Input).value or "1"),
                power=self.query_one("#power", Select).value or "HIGH",
            )
            mode = ContestMode(config)
            self.dismiss(mode)
        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")


class POTASetupScreen(ModalScreen[Optional[POTAMode]]):
    """Screen for setting up a POTA activation."""

    CSS = """
    POTASetupScreen {
        align: center middle;
    }

    POTASetupScreen > Vertical {
        width: 65;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    .setup-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    .setup-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $secondary;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .setup-row {
        height: 3;
        margin-bottom: 1;
    }

    .setup-row Label {
        width: 18;
        content-align: right middle;
        padding-right: 1;
    }

    .setup-row Input, .setup-row Select {
        width: 1fr;
    }

    .setup-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .setup-buttons Button {
        margin: 0 1;
    }

    .help-text {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(self, my_callsign: str = "", my_state: str = "", my_grid: str = "") -> None:
        super().__init__()
        self._my_callsign = my_callsign
        self._my_state = my_state
        self._my_grid = my_grid

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Parks on the Air Setup", classes="setup-title")

            with Vertical(classes="setup-section"):
                yield Static("Activator Information", classes="section-title")

                with Horizontal(classes="setup-row"):
                    yield Label("My Callsign:")
                    yield Input(value=self._my_callsign, id="my_callsign")

                with Horizontal(classes="setup-row"):
                    yield Label("Park Reference:")
                    yield Input(placeholder="e.g., K-1234", id="my_park")

                with Horizontal(classes="setup-row"):
                    yield Label("Additional Parks:")
                    yield Input(placeholder="e.g., K-5678, K-9012 (for 2-fer)", id="additional_parks")

                with Horizontal(classes="setup-row"):
                    yield Label("State/Province:")
                    yield Input(value=self._my_state, id="my_state")

                with Horizontal(classes="setup-row"):
                    yield Label("Grid Square:")
                    yield Input(value=self._my_grid, id="my_grid")

                yield Static(
                    "Minimum 10 contacts required for a valid activation",
                    classes="help-text",
                )

            with Horizontal(classes="setup-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Start Activation", variant="primary", id="start")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#start")
    def _on_start(self) -> None:
        try:
            additional = self.query_one("#additional_parks", Input).value.strip()
            additional_parks = [p.strip().upper() for p in additional.split(",") if p.strip()]

            config = POTAConfig(
                name="POTA Activation",
                my_callsign=self.query_one("#my_callsign", Input).value.strip().upper(),
                my_park=self.query_one("#my_park", Input).value.strip().upper(),
                additional_parks=additional_parks,
                my_state=self.query_one("#my_state", Input).value.strip().upper(),
                my_grid=self.query_one("#my_grid", Input).value.strip().upper(),
                is_activator=True,
            )
            mode = POTAMode(config)
            self.dismiss(mode)
        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")


class POTAHunterSetupScreen(ModalScreen[Optional[POTAMode]]):
    """Screen for setting up POTA hunting mode."""

    CSS = """
    POTAHunterSetupScreen {
        align: center middle;
    }

    POTAHunterSetupScreen > Vertical {
        width: 65;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    .setup-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    .setup-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $secondary;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .setup-row {
        height: 3;
        margin-bottom: 1;
    }

    .setup-row Label {
        width: 18;
        content-align: right middle;
        padding-right: 1;
    }

    .setup-row Input, .setup-row Select {
        width: 1fr;
    }

    .setup-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .setup-buttons Button {
        margin: 0 1;
    }

    .help-text {
        color: $text-muted;
        text-style: italic;
        margin-top: 1;
    }
    """

    def __init__(self, my_callsign: str = "", my_state: str = "", my_grid: str = "") -> None:
        super().__init__()
        self._my_callsign = my_callsign
        self._my_state = my_state
        self._my_grid = my_grid

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("POTA Hunter Setup", classes="setup-title")

            with Vertical(classes="setup-section"):
                yield Static("Hunter Information", classes="section-title")

                with Horizontal(classes="setup-row"):
                    yield Label("My Callsign:")
                    yield Input(value=self._my_callsign, id="my_callsign")

                with Horizontal(classes="setup-row"):
                    yield Label("State/Province:")
                    yield Input(value=self._my_state, id="my_state")

                with Horizontal(classes="setup-row"):
                    yield Label("Grid Square:")
                    yield Input(value=self._my_grid, id="my_grid")

                yield Static(
                    "As a hunter, you'll log contacts with park activators. "
                    "Enter their park reference in the exchange.",
                    classes="help-text",
                )

            with Horizontal(classes="setup-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Start Hunting", variant="primary", id="start")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#start")
    def _on_start(self) -> None:
        try:
            config = POTAConfig(
                name="POTA Hunter",
                my_callsign=self.query_one("#my_callsign", Input).value.strip().upper(),
                my_park="",  # Hunters don't have a park
                additional_parks=[],
                my_state=self.query_one("#my_state", Input).value.strip().upper(),
                my_grid=self.query_one("#my_grid", Input).value.strip().upper(),
                is_activator=False,  # This is hunter mode
            )
            mode = POTAMode(config)
            self.dismiss(mode)
        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")


class FieldDaySetupScreen(ModalScreen[Optional[FieldDayMode]]):
    """Screen for setting up Field Day."""

    CSS = """
    FieldDaySetupScreen {
        align: center middle;
    }

    FieldDaySetupScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 90%;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    .setup-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    .setup-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $secondary;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
    }

    .setup-row {
        height: 3;
        margin-bottom: 1;
    }

    .setup-row Label {
        width: 18;
        content-align: right middle;
        padding-right: 1;
    }

    .setup-row Input, .setup-row Select {
        width: 1fr;
    }

    .checkbox-row {
        height: 2;
    }

    .setup-buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .setup-buttons Button {
        margin: 0 1;
    }
    """

    FD_CLASSES = [
        "1A", "2A", "3A", "4A", "5A", "6A", "7A", "8A", "9A", "10A",
        "1B", "2B", "1C", "1D", "2D", "1E", "2E", "1F",
    ]

    def __init__(self, my_callsign: str = "") -> None:
        super().__init__()
        self._my_callsign = my_callsign

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("ARRL Field Day Setup", classes="setup-title")

            with VerticalScroll():
                with Vertical(classes="setup-section"):
                    yield Static("Station Information", classes="section-title")

                    with Horizontal(classes="setup-row"):
                        yield Label("Callsign:")
                        yield Input(value=self._my_callsign, id="my_callsign")

                    with Horizontal(classes="setup-row"):
                        yield Label("Club Name:")
                        yield Input(placeholder="e.g., Example ARC", id="club_name")

                    with Horizontal(classes="setup-row"):
                        yield Label("Class:")
                        yield Select(
                            [(c, c) for c in self.FD_CLASSES],
                            value="3A",
                            id="my_class",
                        )

                    with Horizontal(classes="setup-row"):
                        yield Label("ARRL Section:")
                        yield Select(
                            [(s, s) for s in sorted(ARRL_SECTIONS)],
                            value="SNJ",
                            id="my_section",
                        )

                    with Horizontal(classes="setup-row"):
                        yield Label("Power Level:")
                        yield Select(
                            [("High (>150W)", "HIGH"), ("Low (<=150W)", "LOW"), ("QRP (<=5W)", "QRP")],
                            value="LOW",
                            id="power_level",
                        )

                with Vertical(classes="setup-section"):
                    yield Static("Bonus Points", classes="section-title")

                    yield Checkbox("100% Emergency Power", id="emergency_power")
                    yield Checkbox("Media Publicity", id="media_publicity")
                    yield Checkbox("Public Location", id="public_location")
                    yield Checkbox("Public Information Table", id="public_info_table")
                    yield Checkbox("Youth Participation", id="youth_participation")
                    yield Checkbox("Web Submission", value=True, id="web_submission")
                    yield Checkbox("Educational Activity", id="educational_activity")
                    yield Checkbox("Safety Officer", id="safety_officer")

            with Horizontal(classes="setup-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Start Field Day", variant="primary", id="start")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#start")
    def _on_start(self) -> None:
        try:
            config = FieldDayConfig(
                name="ARRL Field Day",
                my_callsign=self.query_one("#my_callsign", Input).value.strip().upper(),
                club_name=self.query_one("#club_name", Input).value.strip(),
                my_class=self.query_one("#my_class", Select).value or "3A",
                my_section=self.query_one("#my_section", Select).value or "SNJ",
                power_level=self.query_one("#power_level", Select).value or "LOW",
                emergency_power=self.query_one("#emergency_power", Checkbox).value,
                media_publicity=self.query_one("#media_publicity", Checkbox).value,
                public_location=self.query_one("#public_location", Checkbox).value,
                public_info_table=self.query_one("#public_info_table", Checkbox).value,
                youth_participation=self.query_one("#youth_participation", Checkbox).value,
                web_submission=self.query_one("#web_submission", Checkbox).value,
                educational_activity=self.query_one("#educational_activity", Checkbox).value,
                safety_officer=self.query_one("#safety_officer", Checkbox).value,
            )
            mode = FieldDayMode(config)
            self.dismiss(mode)
        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")
