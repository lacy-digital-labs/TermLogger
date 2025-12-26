"""Base classes for operating modes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from ..models import QSO


class ModeType(str, Enum):
    """Types of operating modes."""

    GENERAL = "general"
    CONTEST = "contest"
    POTA = "pota"
    FIELDDAY = "fieldday"


@dataclass
class ModeConfig:
    """Base configuration for operating modes."""

    name: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


@dataclass
class ModeScore:
    """Score information for an operating mode."""

    qso_points: int = 0
    multipliers: int = 0
    total_score: int = 0
    qso_count: int = 0
    dupe_count: int = 0

    # Breakdown by band/mode
    band_breakdown: dict[str, int] = field(default_factory=dict)
    mode_breakdown: dict[str, int] = field(default_factory=dict)

    def calculate_total(self) -> int:
        """Calculate total score."""
        self.total_score = self.qso_points * max(1, self.multipliers)
        return self.total_score


class OperatingMode(ABC):
    """Abstract base class for operating modes."""

    mode_type: ModeType = ModeType.GENERAL

    def __init__(self, config: ModeConfig):
        self.config = config
        self._qsos: list[QSO] = []
        self._dupes: set[str] = set()

    @property
    def name(self) -> str:
        """Get the mode name."""
        return self.config.name

    @property
    def is_active(self) -> bool:
        """Check if the mode is currently active (within time window)."""
        if not self.config.start_time:
            return True
        now = datetime.utcnow()
        if self.config.end_time:
            return self.config.start_time <= now <= self.config.end_time
        return now >= self.config.start_time

    @abstractmethod
    def get_exchange_fields(self) -> list[dict]:
        """Get the exchange fields for this mode.

        Returns a list of field definitions:
        [
            {"id": "field_id", "label": "Label", "width": 10, "required": True},
            ...
        ]
        """
        pass

    @abstractmethod
    def validate_exchange(self, exchange: dict) -> tuple[bool, str]:
        """Validate the exchange data.

        Args:
            exchange: Dictionary of exchange field values

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def calculate_score(self) -> ModeScore:
        """Calculate the current score."""
        pass

    @abstractmethod
    def check_dupe(self, callsign: str, band: Optional[str] = None, mode: Optional[str] = None) -> bool:
        """Check if a contact is a duplicate.

        Args:
            callsign: The callsign to check
            band: Optional band for band-specific dupe checking
            mode: Optional mode for mode-specific dupe checking

        Returns:
            True if this is a duplicate contact
        """
        pass

    @abstractmethod
    def format_exchange_sent(self) -> str:
        """Format the exchange to send."""
        pass

    @abstractmethod
    def get_next_serial(self) -> int:
        """Get the next serial number (if applicable)."""
        pass

    def add_qso(self, qso: QSO) -> None:
        """Add a QSO to this mode's log."""
        self._qsos.append(qso)
        # Update dupe tracking
        dupe_key = self._get_dupe_key(qso.callsign, qso.band.value if qso.band else None, qso.mode.value)
        self._dupes.add(dupe_key)

    def _get_dupe_key(self, callsign: str, band: Optional[str], mode: Optional[str]) -> str:
        """Generate a key for dupe checking."""
        return f"{callsign.upper()}_{band or 'ANY'}_{mode or 'ANY'}"

    def get_qsos(self) -> list[QSO]:
        """Get all QSOs for this mode."""
        return self._qsos.copy()

    @abstractmethod
    def export_cabrillo(self) -> str:
        """Export the log in Cabrillo format."""
        pass

    def get_status_text(self) -> str:
        """Get status text to display in the UI."""
        score = self.calculate_score()
        return f"QSOs: {score.qso_count} | Score: {score.total_score}"
