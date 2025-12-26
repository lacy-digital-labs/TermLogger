"""ARRL Field Day mode implementation."""

from dataclasses import dataclass, field
from typing import Optional

from .base import ModeConfig, ModeScore, ModeType, OperatingMode


# ARRL/RAC sections
ARRL_SECTIONS = [
    # US Call Areas
    "CT", "EMA", "ME", "NH", "RI", "VT", "WMA",  # 1
    "ENY", "NLI", "NNJ", "NNY", "SNJ", "WNY",  # 2
    "DE", "EPA", "MDC", "WPA",  # 3
    "AL", "GA", "KY", "NC", "NFL", "SC", "SFL", "WCF", "TN", "VA", "PR", "VI",  # 4
    "AR", "LA", "MS", "NM", "NTX", "OK", "STX", "WTX",  # 5
    "EB", "LAX", "ORG", "SB", "SCV", "SDG", "SF", "SJV", "SV", "PAC",  # 6
    "AK", "AZ", "EWA", "ID", "MT", "NV", "OR", "UT", "WWA", "WY",  # 7
    "MI", "OH", "WV",  # 8
    "IL", "IN", "WI",  # 9
    "CO", "IA", "KS", "MN", "MO", "NE", "ND", "SD",  # 0
    # Canada
    "AB", "BC", "GH", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT",
    # DX
    "DX",
]

# Valid Field Day classes
FD_CLASSES = ["1A", "1B", "1C", "1D", "1E", "2A", "2B", "2C", "2D", "2E",
              "3A", "3B", "3C", "3D", "3E", "4A", "4B", "4C", "4D", "4E",
              "5A", "5B", "5C", "5D", "5E", "6A", "6B", "6C", "6D", "6E",
              "7A", "8A", "9A", "10A", "11A", "12A", "13A", "14A", "15A",
              "1AB", "2AB", "3AB", "4AB", "5AB",  # Battery classes
              "1F", "2F", "3F", "4F", "5F"]  # Free VHF


@dataclass
class FieldDayConfig(ModeConfig):
    """Configuration for Field Day mode."""

    # Station info
    my_callsign: str = ""
    my_class: str = ""  # e.g., "3A"
    my_section: str = ""  # e.g., "SNJ"
    my_gota_callsign: str = ""  # Get On The Air station

    # Club info
    club_name: str = ""

    # Power levels
    power_level: str = "HIGH"  # HIGH (>150W), LOW (<=150W), QRP (<=5W)

    # Band/mode restrictions
    bands_used: list[str] = field(default_factory=list)

    # Bonus points tracking
    emergency_power: bool = False  # 100% emergency power
    media_publicity: bool = False
    public_location: bool = False
    public_info_table: bool = False
    message_to_sm: bool = False  # Message to Section Manager
    message_from_sm: bool = False
    w1aw_bulletin: bool = False
    educational_activity: bool = False
    elected_official: bool = False
    agency_representative: bool = False
    gota_bonus: bool = False
    web_submission: bool = False
    youth_participation: bool = False
    social_media: bool = False
    safety_officer: bool = False


class FieldDayMode(OperatingMode):
    """ARRL Field Day operating mode."""

    mode_type = ModeType.FIELDDAY

    # Point values
    CW_DIGITAL_POINTS = 2
    PHONE_POINTS = 1

    def __init__(self, config: FieldDayConfig):
        super().__init__(config)
        self.config: FieldDayConfig = config
        self._sections_worked: dict[str, set[str]] = {}  # band -> sections

    def get_exchange_fields(self) -> list[dict]:
        """Get Field Day exchange fields."""
        return [
            {"id": "class", "label": "Class", "width": 5, "required": True, "hint": "e.g., 3A"},
            {"id": "section", "label": "Section", "width": 6, "required": True, "hint": "e.g., SNJ"},
        ]

    def validate_exchange(self, exchange: dict) -> tuple[bool, str]:
        """Validate Field Day exchange."""
        fd_class = exchange.get("class", "").strip().upper()
        section = exchange.get("section", "").strip().upper()

        if not fd_class:
            return False, "Class is required"

        if not section:
            return False, "Section is required"

        # Validate class format (number + letter(s))
        if not any(fd_class.startswith(str(i)) for i in range(1, 30)):
            return False, "Invalid class format (e.g., 3A, 1E)"

        # Validate section
        if section not in ARRL_SECTIONS:
            return False, f"Unknown section: {section}"

        return True, ""

    def calculate_score(self) -> ModeScore:
        """Calculate Field Day score."""
        score = ModeScore()
        score.qso_count = len(self._qsos)

        cw_digital_modes = {"CW", "RTTY", "PSK31", "FT8", "FT4", "JS8", "DIGITAL"}

        for qso in self._qsos:
            # Point calculation
            if qso.mode.value.upper() in cw_digital_modes:
                score.qso_points += self.CW_DIGITAL_POINTS
            else:
                score.qso_points += self.PHONE_POINTS

            # Track sections per band
            band_key = qso.band.value if qso.band else "Unknown"
            if band_key not in self._sections_worked:
                self._sections_worked[band_key] = set()

            if qso.exchange_received:
                # Extract section from exchange (e.g., "3A SNJ" -> "SNJ")
                parts = qso.exchange_received.upper().split()
                if len(parts) >= 2:
                    section = parts[-1]
                    if section in ARRL_SECTIONS:
                        self._sections_worked[band_key].add(section)

            # Band breakdown
            score.band_breakdown[band_key] = score.band_breakdown.get(band_key, 0) + 1

            # Mode breakdown
            mode_key = qso.mode.value
            score.mode_breakdown[mode_key] = score.mode_breakdown.get(mode_key, 0) + 1

        # Count unique sections across all bands
        all_sections = set()
        for sections in self._sections_worked.values():
            all_sections.update(sections)
        score.multipliers = len(all_sections)

        # Base score
        base_score = score.qso_points

        # Power multiplier
        power_mult = self._get_power_multiplier()
        base_score = int(base_score * power_mult)

        # Add bonus points
        bonus = self._calculate_bonus_points()

        score.total_score = base_score + bonus

        return score

    def _get_power_multiplier(self) -> float:
        """Get power multiplier based on class and power level."""
        # Class A, B, F use transmitter count, E is emergency power
        # D is home station
        fd_class = self.config.my_class.upper()

        if "E" in fd_class:
            return 2.0  # Emergency power
        elif "B" in fd_class:
            return 2.0  # Battery
        elif self.config.power_level == "QRP":
            return 5.0  # QRP bonus
        elif self.config.power_level == "LOW":
            return 2.0  # Low power
        else:
            return 1.0  # High power

    def _calculate_bonus_points(self) -> int:
        """Calculate bonus points."""
        bonus = 0

        if self.config.emergency_power:
            bonus += 100  # 100% emergency power

        if self.config.media_publicity:
            bonus += 100

        if self.config.public_location:
            bonus += 100

        if self.config.public_info_table:
            bonus += 100

        if self.config.message_to_sm:
            bonus += 100

        if self.config.w1aw_bulletin:
            bonus += 100

        if self.config.educational_activity:
            bonus += 100

        if self.config.elected_official:
            bonus += 100

        if self.config.agency_representative:
            bonus += 100

        if self.config.gota_bonus:
            bonus += 100  # Up to 500 for GOTA

        if self.config.web_submission:
            bonus += 50

        if self.config.youth_participation:
            bonus += 100

        if self.config.social_media:
            bonus += 100

        if self.config.safety_officer:
            bonus += 100

        return bonus

    def check_dupe(self, callsign: str, band: Optional[str] = None, mode: Optional[str] = None) -> bool:
        """Check for duplicate contact.

        In Field Day, you can work the same station once per band per mode category.
        Mode categories: CW, Digital, Phone
        """
        # Normalize mode to category
        mode_category = self._get_mode_category(mode)
        dupe_key = f"{callsign.upper()}_{band}_{mode_category}"
        return dupe_key in self._dupes

    def _get_mode_category(self, mode: Optional[str]) -> str:
        """Get Field Day mode category."""
        if not mode:
            return "PHONE"

        mode_upper = mode.upper()
        if mode_upper == "CW":
            return "CW"
        elif mode_upper in {"RTTY", "PSK31", "FT8", "FT4", "JS8", "DIGITAL"}:
            return "DIGITAL"
        else:
            return "PHONE"

    def format_exchange_sent(self) -> str:
        """Format the exchange to send."""
        return f"{self.config.my_class} {self.config.my_section}"

    def get_next_serial(self) -> int:
        """Field Day doesn't use serial numbers."""
        return 0

    def export_cabrillo(self) -> str:
        """Export log in Cabrillo format."""
        score = self.calculate_score()

        lines = [
            "START-OF-LOG: 3.0",
            "CONTEST: ARRL-FIELD-DAY",
            f"CALLSIGN: {self.config.my_callsign}",
            f"LOCATION: {self.config.my_section}",
            f"ARRL-SECTION: {self.config.my_section}",
            f"CATEGORY: {self.config.my_class}",
            f"CATEGORY-POWER: {self.config.power_level}",
            f"CLUB: {self.config.club_name}",
            f"CLAIMED-SCORE: {score.total_score}",
            "CREATED-BY: TermLogger",
            f"SOAPBOX: QSO Points: {score.qso_points}",
            f"SOAPBOX: Sections: {score.multipliers}",
            f"SOAPBOX: Bonus: {self._calculate_bonus_points()}",
        ]

        # Add QSO records
        for qso in self._qsos:
            freq = int(qso.frequency * 1000)  # Convert to kHz
            mode = self._get_cabrillo_mode(qso.mode.value)
            date = qso.datetime_utc.strftime("%Y-%m-%d")
            time = qso.datetime_utc.strftime("%H%M")

            # Parse their exchange
            their_class = ""
            their_section = ""
            if qso.exchange_received:
                parts = qso.exchange_received.upper().split()
                if len(parts) >= 2:
                    their_class = parts[0]
                    their_section = parts[1]

            qso_line = (
                f"QSO: {freq:>5} {mode:>2} {date} {time} "
                f"{self.config.my_callsign:<13} {self.config.my_class:<4} {self.config.my_section:<4} "
                f"{qso.callsign:<13} {their_class:<4} {their_section:<4}"
            )
            lines.append(qso_line)

        lines.append("END-OF-LOG:")
        return "\n".join(lines)

    def _get_cabrillo_mode(self, mode: str) -> str:
        """Convert mode to Cabrillo format."""
        mode_upper = mode.upper()
        if mode_upper == "SSB":
            return "PH"
        elif mode_upper == "CW":
            return "CW"
        elif mode_upper in {"RTTY", "PSK31"}:
            return "RY"
        elif mode_upper in {"FT8", "FT4", "JS8", "DIGITAL"}:
            return "DG"
        else:
            return "PH"

    def get_status_text(self) -> str:
        """Get Field Day status text."""
        score = self.calculate_score()
        exchange = self.format_exchange_sent()

        return (
            f"Field Day {self.config.my_callsign} {exchange} | "
            f"QSOs: {score.qso_count} | "
            f"Pts: {score.qso_points} | "
            f"Sects: {score.multipliers} | "
            f"Score: {score.total_score}"
        )
