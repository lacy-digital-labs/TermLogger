"""Parks on the Air (POTA) mode implementation."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..models import QSO
from .base import ModeConfig, ModeScore, ModeType, OperatingMode


@dataclass
class POTAConfig(ModeConfig):
    """Configuration for POTA mode."""

    # Activator info
    my_callsign: str = ""
    my_park: str = ""  # e.g., "K-1234" or "VE-1234"
    my_state: str = ""
    my_grid: str = ""

    # Operating mode
    is_activator: bool = True  # True = activator, False = hunter

    # Multi-park activation
    additional_parks: list[str] = field(default_factory=list)  # For 2-fer, 3-fer, etc.

    # Minimum contacts for valid activation
    min_contacts: int = 10


class POTAMode(OperatingMode):
    """Parks on the Air operating mode."""

    mode_type = ModeType.POTA
    PARK_PATTERN = re.compile(r"^[A-Z]{1,2}-\d{4,5}$")

    def __init__(self, config: POTAConfig):
        super().__init__(config)
        self.config: POTAConfig = config
        self._p2p_contacts: list[QSO] = []  # Park-to-park contacts

    def get_exchange_fields(self) -> list[dict]:
        """Get POTA exchange fields."""
        fields = [
            {"id": "rst_received", "label": "RST", "width": 5, "required": True, "default": "59"},
            {"id": "state", "label": "State", "width": 6, "required": False},
            {"id": "name", "label": "Name", "width": 12, "required": False},
        ]

        # Add park reference field for hunters to log activator parks
        # or for activators to log park-to-park contacts
        fields.append({"id": "their_park", "label": "Park", "width": 10, "required": False})

        return fields

    def validate_exchange(self, exchange: dict) -> tuple[bool, str]:
        """Validate POTA exchange."""
        # RST is typically required
        rst = exchange.get("rst_received", "").strip()
        if not rst:
            return False, "RST is required"

        # Validate park reference format if provided
        park = exchange.get("their_park", "").strip().upper()
        if park and not self.PARK_PATTERN.match(park):
            return False, "Invalid park format (use X-NNNN or XX-NNNNN)"

        return True, ""

    def calculate_score(self) -> ModeScore:
        """Calculate POTA statistics."""
        score = ModeScore()
        score.qso_count = len(self._qsos)

        # In POTA, we track unique parks worked and P2P contacts
        parks_worked: set[str] = set()

        for qso in self._qsos:
            score.qso_points += 1

            # Track band breakdown
            band_key = qso.band.value if qso.band else "Unknown"
            score.band_breakdown[band_key] = score.band_breakdown.get(band_key, 0) + 1

            # Track mode breakdown
            mode_key = qso.mode.value
            score.mode_breakdown[mode_key] = score.mode_breakdown.get(mode_key, 0) + 1

            # Check for P2P (park in exchange)
            if qso.exchange_received:
                park_match = self.PARK_PATTERN.search(qso.exchange_received.upper())
                if park_match:
                    parks_worked.add(park_match.group())
                    self._p2p_contacts.append(qso)

        score.multipliers = len(parks_worked)  # Unique parks as "multipliers"
        score.total_score = score.qso_points  # POTA doesn't have traditional scoring

        return score

    def check_dupe(self, callsign: str, band: Optional[str] = None, mode: Optional[str] = None) -> bool:
        """Check for duplicate contact.

        In POTA, you can work the same station on different bands/modes.
        """
        dupe_key = self._get_dupe_key(callsign, band, mode)
        return dupe_key in self._dupes

    def format_exchange_sent(self) -> str:
        """Format the exchange to send."""
        parts = ["59"]  # RST

        if self.config.is_activator and self.config.my_park:
            parts.append(self.config.my_park)

            # Add additional parks for multi-park activations
            for park in self.config.additional_parks:
                parts.append(park)

        if self.config.my_state:
            parts.append(self.config.my_state)

        return " ".join(parts)

    def get_next_serial(self) -> int:
        """POTA doesn't use serial numbers."""
        return 0

    def get_all_parks(self) -> list[str]:
        """Get all parks being activated."""
        parks = []
        if self.config.my_park:
            parks.append(self.config.my_park)
        parks.extend(self.config.additional_parks)
        return parks

    def is_valid_activation(self) -> bool:
        """Check if activation meets minimum contact requirement."""
        return len(self._qsos) >= self.config.min_contacts

    def get_p2p_count(self) -> int:
        """Get number of park-to-park contacts."""
        return len(self._p2p_contacts)

    def export_cabrillo(self) -> str:
        """Export log in Cabrillo-like format for POTA."""
        # POTA uses ADIF, but we'll provide a simple export
        lines = [
            "# POTA Activation Log",
            f"# Callsign: {self.config.my_callsign}",
            f"# Park: {self.config.my_park}",
            f"# Date: {datetime.utcnow().strftime('%Y-%m-%d')}",
            f"# Contacts: {len(self._qsos)}",
            f"# P2P: {self.get_p2p_count()}",
            "#",
            "# Freq, Mode, Date, Time, Callsign, RST Sent, RST Rcvd, Park",
        ]

        for qso in self._qsos:
            park = ""
            if qso.exchange_received:
                match = self.PARK_PATTERN.search(qso.exchange_received.upper())
                if match:
                    park = match.group()

            line = (
                f"{qso.frequency:.3f}, {qso.mode.value}, "
                f"{qso.datetime_utc.strftime('%Y-%m-%d')}, "
                f"{qso.datetime_utc.strftime('%H:%M')}, "
                f"{qso.callsign}, {qso.rst_sent}, {qso.rst_received}, {park}"
            )
            lines.append(line)

        return "\n".join(lines)

    def export_pota_adif(self) -> str:
        """Export ADIF with POTA-specific fields."""
        from ..adif import generate_adif_field, generate_adif_header

        lines = [generate_adif_header()]

        for qso in self._qsos:
            fields = [
                generate_adif_field("CALL", qso.callsign),
                generate_adif_field("FREQ", f"{qso.frequency:.6f}"),
                generate_adif_field("MODE", qso.mode.value),
                generate_adif_field("RST_SENT", qso.rst_sent),
                generate_adif_field("RST_RCVD", qso.rst_received),
                generate_adif_field("QSO_DATE", qso.datetime_utc.strftime("%Y%m%d")),
                generate_adif_field("TIME_ON", qso.datetime_utc.strftime("%H%M%S")),
                generate_adif_field("STATION_CALLSIGN", self.config.my_callsign),
            ]

            # Add my park(s)
            if self.config.my_park:
                fields.append(generate_adif_field("MY_SIG", "POTA"))
                fields.append(generate_adif_field("MY_SIG_INFO", self.config.my_park))

            # Add their park if P2P
            if qso.exchange_received:
                match = self.PARK_PATTERN.search(qso.exchange_received.upper())
                if match:
                    fields.append(generate_adif_field("SIG", "POTA"))
                    fields.append(generate_adif_field("SIG_INFO", match.group()))

            if qso.notes:
                fields.append(generate_adif_field("COMMENT", qso.notes))

            fields.append("<EOR>")
            lines.append(" ".join(fields))
            lines.append("")

        return "\n".join(lines)

    def get_status_text(self) -> str:
        """Get POTA status text."""
        score = self.calculate_score()
        parks = ", ".join(self.get_all_parks()) if self.get_all_parks() else "No park"
        valid = "✓" if self.is_valid_activation() else f"({self.config.min_contacts - score.qso_count} more needed)"

        return (
            f"POTA: {parks} | "
            f"QSOs: {score.qso_count} {valid} | "
            f"P2P: {self.get_p2p_count()}"
        )
