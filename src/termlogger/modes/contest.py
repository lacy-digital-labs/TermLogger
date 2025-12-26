"""General contest mode implementation."""

from dataclasses import dataclass
from typing import Optional

from ..models import QSO
from .base import ModeConfig, ModeScore, ModeType, OperatingMode


@dataclass
class ContestConfig(ModeConfig):
    """Configuration for contest mode."""

    # Contest info
    contest_name: str = ""
    contest_id: str = ""  # e.g., "CQ-WW-SSB"

    # Exchange format
    exchange_sent: str = ""  # e.g., "599 05" for CQ zone
    exchange_format: str = "RST+SERIAL"  # RST+SERIAL, RST+ZONE, RST+STATE, etc.

    # Scoring
    points_per_qso: int = 1
    points_same_country: int = 1
    points_diff_country: int = 3
    points_diff_continent: int = 3

    # Dupe rules
    dupe_check_band: bool = True  # Allow same station on different bands
    dupe_check_mode: bool = False  # Allow same station on different modes

    # Station info
    my_callsign: str = ""
    my_exchange: str = ""  # e.g., zone number, state, etc.
    category: str = ""  # e.g., "SINGLE-OP ALL HIGH"
    power: str = "HIGH"  # HIGH, LOW, QRP

    # Serial number
    starting_serial: int = 1


class ContestMode(OperatingMode):
    """General contest mode with configurable exchange formats."""

    mode_type = ModeType.CONTEST

    def __init__(self, config: ContestConfig):
        super().__init__(config)
        self.config: ContestConfig = config
        self._serial_number = config.starting_serial
        self._multipliers: set[str] = set()

    def get_exchange_fields(self) -> list[dict]:
        """Get exchange fields based on contest format."""
        fields = [
            {"id": "rst_received", "label": "RST", "width": 5, "required": True, "default": "599"},
        ]

        fmt = self.config.exchange_format.upper()

        if "SERIAL" in fmt:
            fields.append({"id": "serial_received", "label": "NR", "width": 6, "required": True})
        if "ZONE" in fmt:
            fields.append({"id": "zone", "label": "Zone", "width": 4, "required": True})
        if "STATE" in fmt or "SECTION" in fmt:
            fields.append({"id": "section", "label": "Sect", "width": 6, "required": True})
        if "NAME" in fmt:
            fields.append({"id": "name", "label": "Name", "width": 12, "required": False})
        if "POWER" in fmt:
            fields.append({"id": "power", "label": "Pwr", "width": 5, "required": False})

        return fields

    def validate_exchange(self, exchange: dict) -> tuple[bool, str]:
        """Validate contest exchange."""
        fields = self.get_exchange_fields()

        for f in fields:
            if f.get("required", False):
                value = exchange.get(f["id"], "").strip()
                if not value:
                    return False, f"{f['label']} is required"

        return True, ""

    def calculate_score(self) -> ModeScore:
        """Calculate contest score."""
        score = ModeScore()
        score.qso_count = len(self._qsos)

        for qso in self._qsos:
            # Points per QSO (simplified - real contests have complex rules)
            score.qso_points += self.config.points_per_qso

            # Track multipliers from exchange
            if qso.exchange_received:
                self._multipliers.add(qso.exchange_received.upper())

            # Band breakdown
            band_key = qso.band.value if qso.band else "Unknown"
            score.band_breakdown[band_key] = score.band_breakdown.get(band_key, 0) + 1

            # Mode breakdown
            mode_key = qso.mode.value
            score.mode_breakdown[mode_key] = score.mode_breakdown.get(mode_key, 0) + 1

        score.multipliers = len(self._multipliers)
        score.calculate_total()

        return score

    def check_dupe(self, callsign: str, band: Optional[str] = None, mode: Optional[str] = None) -> bool:
        """Check for duplicate contact."""
        if self.config.dupe_check_band and self.config.dupe_check_mode:
            dupe_key = self._get_dupe_key(callsign, band, mode)
        elif self.config.dupe_check_band:
            dupe_key = self._get_dupe_key(callsign, band, None)
        elif self.config.dupe_check_mode:
            dupe_key = self._get_dupe_key(callsign, None, mode)
        else:
            dupe_key = self._get_dupe_key(callsign, None, None)

        return dupe_key in self._dupes

    def format_exchange_sent(self) -> str:
        """Format the exchange to send."""
        parts = []

        if "RST" in self.config.exchange_format.upper():
            parts.append("599")

        if "SERIAL" in self.config.exchange_format.upper():
            parts.append(f"{self._serial_number:03d}")

        if self.config.my_exchange:
            parts.append(self.config.my_exchange)

        return " ".join(parts)

    def get_next_serial(self) -> int:
        """Get the next serial number."""
        serial = self._serial_number
        self._serial_number += 1
        return serial

    def add_qso(self, qso: QSO) -> None:
        """Add QSO and increment serial."""
        super().add_qso(qso)
        # Serial is incremented when format_exchange_sent is called

    def export_cabrillo(self) -> str:
        """Export log in Cabrillo format."""
        lines = [
            "START-OF-LOG: 3.0",
            f"CONTEST: {self.config.contest_id}",
            f"CALLSIGN: {self.config.my_callsign}",
            "CATEGORY-OPERATOR: SINGLE-OP",
            "CATEGORY-BAND: ALL",
            f"CATEGORY-POWER: {self.config.power}",
            "CATEGORY-MODE: MIXED",
            f"CLAIMED-SCORE: {self.calculate_score().total_score}",
            "CREATED-BY: TermLogger",
            "NAME: ",
            "ADDRESS: ",
            "ADDRESS-CITY: ",
            "ADDRESS-STATE-PROVINCE: ",
            "ADDRESS-POSTALCODE: ",
            "ADDRESS-COUNTRY: ",
            "EMAIL: ",
        ]

        # Add QSO records
        for qso in self._qsos:
            freq = int(qso.frequency * 1000)  # Convert to kHz
            mode = "PH" if qso.mode.value == "SSB" else qso.mode.value
            date = qso.datetime_utc.strftime("%Y-%m-%d")
            time = qso.datetime_utc.strftime("%H%M")

            # QSO: freq mode date time sent_call sent_exch rcvd_call rcvd_exch
            qso_line = (
                f"QSO: {freq:>5} {mode:>2} {date} {time} "
                f"{self.config.my_callsign:<13} {qso.exchange_sent or '':<6} "
                f"{qso.callsign:<13} {qso.exchange_received or ''}"
            )
            lines.append(qso_line)

        lines.append("END-OF-LOG:")
        return "\n".join(lines)

    def get_status_text(self) -> str:
        """Get contest status."""
        score = self.calculate_score()
        return (
            f"{self.config.contest_name} | "
            f"QSOs: {score.qso_count} | "
            f"Mults: {score.multipliers} | "
            f"Score: {score.total_score}"
        )
