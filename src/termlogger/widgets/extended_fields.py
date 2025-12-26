"""Extended QSO fields modal."""

from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TabbedContent, TabPane


class ExtendedFieldsModal(ModalScreen[dict]):
    """Modal for editing extended ADIF fields."""

    CSS = """
    ExtendedFieldsModal {
        align: center middle;
    }

    ExtendedFieldsModal > Vertical {
        width: 80;
        height: 85%;
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
    }

    .field-row Label {
        width: 16;
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
        dock: bottom;
    }

    .modal-buttons Button {
        margin: 0 1;
    }

    TabPane {
        padding: 1;
    }
    """

    def __init__(self, current_values: Optional[dict] = None) -> None:
        super().__init__()
        self._values = current_values or {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Extended QSO Fields", classes="modal-title")

            with TabbedContent():
                # Station Info Tab
                with TabPane("Station", id="station-tab"):
                    with VerticalScroll():
                        with Horizontal(classes="field-row"):
                            yield Label("Name:")
                            yield Input(
                                value=self._values.get("name", ""),
                                placeholder="Operator name",
                                id="name",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("QTH:")
                            yield Input(
                                value=self._values.get("qth", ""),
                                placeholder="City/Location",
                                id="qth",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("State:")
                            yield Input(
                                value=self._values.get("state", ""),
                                placeholder="State/Province",
                                id="state",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Country:")
                            yield Input(
                                value=self._values.get("country", ""),
                                placeholder="Country",
                                id="country",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Grid Square:")
                            yield Input(
                                value=self._values.get("gridsquare", ""),
                                placeholder="e.g., FN20",
                                id="gridsquare",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("CQ Zone:")
                            yield Input(
                                value=str(self._values.get("cq_zone", "")),
                                placeholder="1-40",
                                id="cq_zone",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("ITU Zone:")
                            yield Input(
                                value=str(self._values.get("itu_zone", "")),
                                placeholder="1-90",
                                id="itu_zone",
                            )

                # Power/Equipment Tab
                with TabPane("Power", id="power-tab"):
                    with VerticalScroll():
                        with Horizontal(classes="field-row"):
                            yield Label("TX Power (W):")
                            yield Input(
                                value=str(self._values.get("tx_pwr", "")),
                                placeholder="Watts",
                                id="tx_pwr",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Antenna Az:")
                            yield Input(
                                value=str(self._values.get("ant_az", "")),
                                placeholder="Degrees",
                                id="ant_az",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Antenna El:")
                            yield Input(
                                value=str(self._values.get("ant_el", "")),
                                placeholder="Degrees",
                                id="ant_el",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Prop Mode:")
                            yield Select(
                                [
                                    ("", ""),
                                    ("Sporadic E", "ES"),
                                    ("F2 Layer", "F2"),
                                    ("Tropospheric", "TR"),
                                    ("Satellite", "SAT"),
                                    ("Earth-Moon-Earth", "EME"),
                                    ("Meteor Scatter", "MS"),
                                    ("Aurora", "AUR"),
                                    ("Ionospheric Scatter", "ION"),
                                ],
                                value=self._values.get("prop_mode", ""),
                                id="prop_mode",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Satellite:")
                            yield Input(
                                value=self._values.get("sat_name", ""),
                                placeholder="Satellite name",
                                id="sat_name",
                            )

                # Activity Tab (SOTA, POTA, etc.)
                with TabPane("Activity", id="activity-tab"):
                    with VerticalScroll():
                        with Horizontal(classes="field-row"):
                            yield Label("POTA Ref:")
                            yield Input(
                                value=self._values.get("pota_ref", ""),
                                placeholder="e.g., K-1234",
                                id="pota_ref",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("SOTA Ref:")
                            yield Input(
                                value=self._values.get("sota_ref", ""),
                                placeholder="e.g., W4C/CM-001",
                                id="sota_ref",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("WWFF Ref:")
                            yield Input(
                                value=self._values.get("wwff_ref", ""),
                                placeholder="e.g., KFF-1234",
                                id="wwff_ref",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("IOTA:")
                            yield Input(
                                value=self._values.get("iota", ""),
                                placeholder="e.g., NA-001",
                                id="iota",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Special Activity:")
                            yield Input(
                                value=self._values.get("sig", ""),
                                placeholder="e.g., POTA, SOTA",
                                id="sig",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("Activity Info:")
                            yield Input(
                                value=self._values.get("sig_info", ""),
                                placeholder="Activity details",
                                id="sig_info",
                            )

                # QSL Tab
                with TabPane("QSL", id="qsl-tab"):
                    with VerticalScroll():
                        with Horizontal(classes="field-row"):
                            yield Label("QSL Sent:")
                            yield Select(
                                [
                                    ("", ""),
                                    ("Yes", "Y"),
                                    ("No", "N"),
                                    ("Requested", "R"),
                                    ("Ignore", "I"),
                                    ("Queued", "Q"),
                                ],
                                value=self._values.get("qsl_sent", ""),
                                id="qsl_sent",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("QSL Received:")
                            yield Select(
                                [
                                    ("", ""),
                                    ("Yes", "Y"),
                                    ("No", "N"),
                                    ("Requested", "R"),
                                    ("Ignore", "I"),
                                ],
                                value=self._values.get("qsl_rcvd", ""),
                                id="qsl_rcvd",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("QSL Via:")
                            yield Input(
                                value=self._values.get("qsl_via", ""),
                                placeholder="Direct, Bureau, or manager call",
                                id="qsl_via",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("LoTW Sent:")
                            yield Select(
                                [("", ""), ("Yes", "Y"), ("No", "N")],
                                value=self._values.get("lotw_qsl_sent", ""),
                                id="lotw_qsl_sent",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("LoTW Rcvd:")
                            yield Select(
                                [("", ""), ("Yes", "Y"), ("No", "N")],
                                value=self._values.get("lotw_qsl_rcvd", ""),
                                id="lotw_qsl_rcvd",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("eQSL Sent:")
                            yield Select(
                                [("", ""), ("Yes", "Y"), ("No", "N")],
                                value=self._values.get("eqsl_qsl_sent", ""),
                                id="eqsl_qsl_sent",
                            )
                        with Horizontal(classes="field-row"):
                            yield Label("eQSL Rcvd:")
                            yield Select(
                                [("", ""), ("Yes", "Y"), ("No", "N")],
                                value=self._values.get("eqsl_qsl_rcvd", ""),
                                id="eqsl_qsl_rcvd",
                            )

                # Comment Tab
                with TabPane("Comment", id="comment-tab"):
                    with VerticalScroll():
                        with Horizontal(classes="field-row"):
                            yield Label("Comment:")
                            yield Input(
                                value=self._values.get("comment", ""),
                                placeholder="Extended comment",
                                id="comment",
                            )

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Apply", variant="primary", id="apply")

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss({})

    @on(Button.Pressed, "#apply")
    def _on_apply(self) -> None:
        result = {}

        # Collect all field values
        text_fields = [
            "name", "qth", "state", "country", "gridsquare",
            "pota_ref", "sota_ref", "wwff_ref", "iota", "sig", "sig_info",
            "qsl_via", "sat_name", "comment"
        ]
        for field_id in text_fields:
            try:
                value = self.query_one(f"#{field_id}", Input).value.strip()
                if value:
                    result[field_id] = value
            except Exception:
                pass

        # Numeric fields
        numeric_fields = ["cq_zone", "itu_zone", "tx_pwr", "ant_az", "ant_el"]
        for field_id in numeric_fields:
            try:
                value = self.query_one(f"#{field_id}", Input).value.strip()
                if value:
                    if field_id in ["cq_zone", "itu_zone"]:
                        result[field_id] = int(value)
                    else:
                        result[field_id] = float(value)
            except (ValueError, Exception):
                pass

        # Select fields
        select_fields = [
            "prop_mode", "qsl_sent", "qsl_rcvd",
            "lotw_qsl_sent", "lotw_qsl_rcvd", "eqsl_qsl_sent", "eqsl_qsl_rcvd"
        ]
        for field_id in select_fields:
            try:
                value = self.query_one(f"#{field_id}", Select).value
                if value:
                    result[field_id] = value
            except Exception:
                pass

        self.dismiss(result)
