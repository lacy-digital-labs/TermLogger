"""Settings/Configuration screen."""


from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from ..config import AppConfig, DXClusterSource, LookupService, save_config


class SettingsScreen(Screen):
    """Configuration settings screen."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("ctrl+s", "save", "Save"),
        ("f10", "cancel", "Cancel"),
    ]

    CSS = """
    SettingsScreen {
        background: $surface;
    }

    SettingsScreen TabbedContent {
        height: 1fr;
    }

    SettingsScreen TabPane {
        padding: 1;
    }

    .settings-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        border: solid $primary;
    }

    .section-title {
        text-style: bold;
        margin-bottom: 1;
        color: $accent;
    }

    .field-row {
        height: 3;
        margin-bottom: 1;
    }

    .field-row Label {
        width: 20;
        content-align: right middle;
        padding-right: 1;
    }

    .field-row Input {
        width: 1fr;
    }

    .field-row Select {
        width: 1fr;
    }

    .field-row-short Input {
        width: 20;
    }

    .field-row-coords {
        height: 3;
    }

    .field-row-coords Label {
        width: 12;
        content-align: right middle;
        padding-right: 1;
    }

    .field-row-coords Input {
        width: 15;
        margin-right: 2;
    }

    .password-input {
        width: 1fr;
    }

    .button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    .button-row Button {
        margin: 0 1;
    }

    .help-text {
        color: $text-muted;
        text-style: italic;
        height: auto;
        margin-top: 1;
    }

    Checkbox {
        margin-left: 20;
    }
    """

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self._original_config = config.model_copy()

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent():
            # Station Info Tab
            with TabPane("Station", id="station-tab"):
                with VerticalScroll():
                    with Vertical(classes="settings-section"):
                        yield Static("Operator Information", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Callsign:")
                            yield Input(
                                value=self.config.my_callsign,
                                placeholder="W1ABC",
                                id="my_callsign",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Operator Name:")
                            yield Input(
                                value=self.config.my_name,
                                placeholder="John Smith",
                                id="my_name",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Grid Square:")
                            yield Input(
                                value=self.config.my_grid,
                                placeholder="FN42ab",
                                id="my_grid",
                            )

                    with Vertical(classes="settings-section"):
                        yield Static("Location", classes="section-title")

                        with Horizontal(classes="field-row-coords"):
                            yield Label("Latitude:")
                            yield Input(
                                value=str(self.config.my_latitude or ""),
                                placeholder="42.3601",
                                id="my_latitude",
                            )
                            yield Label("Longitude:")
                            yield Input(
                                value=str(self.config.my_longitude or ""),
                                placeholder="-71.0589",
                                id="my_longitude",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("City/QTH:")
                            yield Input(
                                value=self.config.my_qth,
                                placeholder="Boston",
                                id="my_qth",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("State/Province:")
                            yield Input(
                                value=self.config.my_state,
                                placeholder="MA",
                                id="my_state",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Country:")
                            yield Input(
                                value=self.config.my_country,
                                placeholder="USA",
                                id="my_country",
                            )

                    with Vertical(classes="settings-section"):
                        yield Static("Contest Zones", classes="section-title")

                        with Horizontal(classes="field-row-coords"):
                            yield Label("CQ Zone:")
                            yield Input(
                                value=self.config.my_cq_zone,
                                placeholder="5",
                                id="my_cq_zone",
                            )
                            yield Label("ITU Zone:")
                            yield Input(
                                value=self.config.my_itu_zone,
                                placeholder="8",
                                id="my_itu_zone",
                            )

            # Callsign Lookup Tab
            with TabPane("Lookup", id="lookup-tab"):
                with VerticalScroll():
                    with Vertical(classes="settings-section"):
                        yield Static("Callsign Lookup Service", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Service:")
                            yield Select(
                                [
                                    ("None", LookupService.NONE.value),
                                    ("QRZ.com", LookupService.QRZ.value),
                                    ("QRZ.com XML (subscription)", LookupService.QRZ_XML.value),
                                    ("HamQTH", LookupService.HAMQTH.value),
                                ],
                                value=self.config.lookup_service.value,
                                id="lookup_service",
                            )

                        yield Checkbox(
                            "Auto-lookup callsigns while typing",
                            value=self.config.auto_lookup,
                            id="auto_lookup",
                        )

                    with Vertical(classes="settings-section"):
                        yield Static("QRZ.com Credentials", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Username:")
                            yield Input(
                                value=self.config.qrz_username,
                                placeholder="Your QRZ username",
                                id="qrz_username",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Password:")
                            yield Input(
                                value=self.config.qrz_password,
                                placeholder="Your QRZ password",
                                password=True,
                                id="qrz_password",
                                classes="password-input",
                            )

                        yield Static(
                            "Note: QRZ XML API requires an XML subscription",
                            classes="help-text",
                        )

                    with Vertical(classes="settings-section"):
                        yield Static("HamQTH Credentials", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Username:")
                            yield Input(
                                value=self.config.hamqth_username,
                                placeholder="Your HamQTH username",
                                id="hamqth_username",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Password:")
                            yield Input(
                                value=self.config.hamqth_password,
                                placeholder="Your HamQTH password",
                                password=True,
                                id="hamqth_password",
                                classes="password-input",
                            )

                        yield Static(
                            "HamQTH is a free callsign lookup service",
                            classes="help-text",
                        )

            # Spots Tab
            with TabPane("Spots", id="spots-tab"):
                with VerticalScroll():
                    with Vertical(classes="settings-section"):
                        yield Static("POTA Spots", classes="section-title")

                        yield Checkbox(
                            "Enable POTA spots in POTA mode",
                            value=self.config.pota_spots_enabled,
                            id="pota_spots_enabled",
                        )

                        with Horizontal(classes="field-row"):
                            yield Label("Refresh (seconds):")
                            yield Input(
                                value=str(self.config.pota_spots_refresh_seconds),
                                placeholder="60",
                                id="pota_spots_refresh_seconds",
                            )

                        yield Static(
                            "POTA spots are fetched from pota.app API",
                            classes="help-text",
                        )

                    with Vertical(classes="settings-section"):
                        yield Static("DX Cluster", classes="section-title")

                        yield Checkbox(
                            "Enable DX cluster spots in general mode",
                            value=self.config.dx_cluster_enabled,
                            id="dx_cluster_enabled",
                        )

                        with Horizontal(classes="field-row"):
                            yield Label("Source:")
                            yield Select(
                                [
                                    ("Web API only", DXClusterSource.WEB_API.value),
                                    ("Telnet only", DXClusterSource.TELNET.value),
                                    ("Both (telnet + web)", DXClusterSource.BOTH.value),
                                ],
                                value=self.config.dx_cluster_source.value,
                                id="dx_cluster_source",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Refresh (seconds):")
                            yield Input(
                                value=str(self.config.dx_cluster_refresh_seconds),
                                placeholder="30",
                                id="dx_cluster_refresh_seconds",
                            )

                    with Vertical(classes="settings-section"):
                        yield Static("Telnet Cluster Settings", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Host:")
                            yield Input(
                                value=self.config.dx_cluster_host,
                                placeholder="dxc.nc7j.com",
                                id="dx_cluster_host",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Port:")
                            yield Input(
                                value=str(self.config.dx_cluster_port),
                                placeholder="7373",
                                id="dx_cluster_port",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Callsign:")
                            yield Input(
                                value=self.config.dx_cluster_callsign,
                                placeholder="Leave empty to use your callsign",
                                id="dx_cluster_callsign",
                            )

                        yield Static(
                            "Telnet requires a valid callsign for login",
                            classes="help-text",
                        )

            # Defaults Tab
            with TabPane("Defaults", id="defaults-tab"):
                with VerticalScroll():
                    with Vertical(classes="settings-section"):
                        yield Static("QSO Defaults", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Default Mode:")
                            yield Select(
                                [
                                    ("SSB", "SSB"),
                                    ("CW", "CW"),
                                    ("FT8", "FT8"),
                                    ("FT4", "FT4"),
                                    ("FM", "FM"),
                                    ("AM", "AM"),
                                    ("RTTY", "RTTY"),
                                    ("PSK31", "PSK31"),
                                ],
                                value=self.config.default_mode,
                                id="default_mode",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Default RST:")
                            yield Input(
                                value=self.config.default_rst,
                                placeholder="59",
                                id="default_rst",
                            )

                        with Horizontal(classes="field-row"):
                            yield Label("Default Frequency:")
                            yield Input(
                                value=str(self.config.default_frequency),
                                placeholder="14.250",
                                id="default_frequency",
                            )

                    with Vertical(classes="settings-section"):
                        yield Static("Database", classes="section-title")

                        with Horizontal(classes="field-row"):
                            yield Label("Database Path:")
                            yield Input(
                                value=self.config.db_path,
                                id="db_path",
                            )

                        yield Static(
                            "Changing the database path requires a restart",
                            classes="help-text",
                        )

        with Horizontal(classes="button-row"):
            yield Button("Cancel", variant="default", id="cancel")
            yield Button("Save", variant="primary", id="save")

        yield Footer()

    def _collect_settings(self) -> AppConfig:
        """Collect all settings from form fields."""
        # Parse latitude
        lat_str = self.query_one("#my_latitude", Input).value.strip()
        try:
            latitude = float(lat_str) if lat_str else None
        except ValueError:
            latitude = None

        # Parse longitude
        lon_str = self.query_one("#my_longitude", Input).value.strip()
        try:
            longitude = float(lon_str) if lon_str else None
        except ValueError:
            longitude = None

        # Parse frequency
        freq_str = self.query_one("#default_frequency", Input).value.strip()
        try:
            frequency = float(freq_str) if freq_str else 14.250
        except ValueError:
            frequency = 14.250

        # Get lookup service
        lookup_value = self.query_one("#lookup_service", Select).value
        lookup_service = LookupService(lookup_value) if lookup_value else LookupService.NONE

        # Parse spot refresh intervals
        pota_refresh_str = self.query_one("#pota_spots_refresh_seconds", Input).value.strip()
        try:
            pota_refresh = int(pota_refresh_str) if pota_refresh_str else 60
            pota_refresh = max(10, min(300, pota_refresh))
        except ValueError:
            pota_refresh = 60

        dx_refresh_str = self.query_one("#dx_cluster_refresh_seconds", Input).value.strip()
        try:
            dx_refresh = int(dx_refresh_str) if dx_refresh_str else 30
            dx_refresh = max(10, min(300, dx_refresh))
        except ValueError:
            dx_refresh = 30

        # Parse DX cluster port
        dx_port_str = self.query_one("#dx_cluster_port", Input).value.strip()
        try:
            dx_port = int(dx_port_str) if dx_port_str else 7373
        except ValueError:
            dx_port = 7373

        # Get DX cluster source
        dx_source_value = self.query_one("#dx_cluster_source", Select).value
        dx_source = DXClusterSource(dx_source_value) if dx_source_value else DXClusterSource.WEB_API

        return AppConfig(
            # Station info
            my_callsign=self.query_one("#my_callsign", Input).value.strip().upper(),
            my_name=self.query_one("#my_name", Input).value.strip(),
            my_grid=self.query_one("#my_grid", Input).value.strip().upper(),
            my_latitude=latitude,
            my_longitude=longitude,
            my_qth=self.query_one("#my_qth", Input).value.strip(),
            my_state=self.query_one("#my_state", Input).value.strip(),
            my_country=self.query_one("#my_country", Input).value.strip(),
            my_cq_zone=self.query_one("#my_cq_zone", Input).value.strip(),
            my_itu_zone=self.query_one("#my_itu_zone", Input).value.strip(),
            # Lookup
            lookup_service=lookup_service,
            qrz_username=self.query_one("#qrz_username", Input).value.strip(),
            qrz_password=self.query_one("#qrz_password", Input).value,
            hamqth_username=self.query_one("#hamqth_username", Input).value.strip(),
            hamqth_password=self.query_one("#hamqth_password", Input).value,
            auto_lookup=self.query_one("#auto_lookup", Checkbox).value,
            # Defaults
            default_mode=self.query_one("#default_mode", Select).value or "SSB",
            default_rst=self.query_one("#default_rst", Input).value.strip() or "59",
            default_frequency=frequency,
            # Database
            db_path=self.query_one("#db_path", Input).value.strip(),
            # POTA Spots
            pota_spots_enabled=self.query_one("#pota_spots_enabled", Checkbox).value,
            pota_spots_refresh_seconds=pota_refresh,
            # DX Cluster
            dx_cluster_enabled=self.query_one("#dx_cluster_enabled", Checkbox).value,
            dx_cluster_source=dx_source,
            dx_cluster_host=self.query_one("#dx_cluster_host", Input).value.strip(),
            dx_cluster_port=dx_port,
            dx_cluster_callsign=self.query_one("#dx_cluster_callsign", Input).value.strip().upper(),
            dx_cluster_refresh_seconds=dx_refresh,
        )

    @on(Button.Pressed, "#save")
    def _on_save(self) -> None:
        """Save settings and close."""
        self.action_save()

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        """Cancel and close."""
        self.action_cancel()

    def action_save(self) -> None:
        """Save configuration and return to main screen."""
        try:
            new_config = self._collect_settings()
            save_config(new_config)
            self.app.config = new_config
            # Update lookup service with new config
            if hasattr(self.app, "lookup_service"):
                self.app.lookup_service.update_config(new_config)
            self.notify("Settings saved", severity="information")
            self.app.pop_screen()
        except Exception as e:
            self.notify(f"Error saving settings: {e}", severity="error")

    def action_cancel(self) -> None:
        """Cancel and return to main screen."""
        self.app.pop_screen()
