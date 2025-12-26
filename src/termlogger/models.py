"""Data models for TermLogger."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Mode(str, Enum):
    """Amateur radio operating modes."""

    SSB = "SSB"
    CW = "CW"
    FM = "FM"
    AM = "AM"
    RTTY = "RTTY"
    PSK31 = "PSK31"
    FT8 = "FT8"
    FT4 = "FT4"
    JS8 = "JS8"
    SSTV = "SSTV"
    DIGITAL = "DIGITAL"


class Band(str, Enum):
    """Amateur radio bands."""

    BAND_160M = "160m"
    BAND_80M = "80m"
    BAND_60M = "60m"
    BAND_40M = "40m"
    BAND_30M = "30m"
    BAND_20M = "20m"
    BAND_17M = "17m"
    BAND_15M = "15m"
    BAND_12M = "12m"
    BAND_10M = "10m"
    BAND_6M = "6m"
    BAND_2M = "2m"
    BAND_70CM = "70cm"


# Band frequency ranges in MHz
BAND_FREQUENCIES = {
    Band.BAND_160M: (1.8, 2.0),
    Band.BAND_80M: (3.5, 4.0),
    Band.BAND_60M: (5.3, 5.4),
    Band.BAND_40M: (7.0, 7.3),
    Band.BAND_30M: (10.1, 10.15),
    Band.BAND_20M: (14.0, 14.35),
    Band.BAND_17M: (18.068, 18.168),
    Band.BAND_15M: (21.0, 21.45),
    Band.BAND_12M: (24.89, 24.99),
    Band.BAND_10M: (28.0, 29.7),
    Band.BAND_6M: (50.0, 54.0),
    Band.BAND_2M: (144.0, 148.0),
    Band.BAND_70CM: (420.0, 450.0),
}


def frequency_to_band(freq_mhz: float) -> Optional[Band]:
    """Convert a frequency in MHz to its corresponding band."""
    for band, (low, high) in BAND_FREQUENCIES.items():
        if low <= freq_mhz <= high:
            return band
    return None


class QSO(BaseModel):
    """A single QSO (contact) record."""

    # Core fields
    id: Optional[int] = None
    callsign: str = Field(..., min_length=1, max_length=15)
    frequency: float = Field(..., gt=0)
    mode: Mode = Mode.SSB
    rst_sent: str = Field(default="59", max_length=5)
    rst_received: str = Field(default="59", max_length=5)
    datetime_utc: datetime = Field(default_factory=datetime.utcnow)
    notes: str = Field(default="", max_length=500)

    # Contest fields
    contest_id: Optional[int] = None
    exchange_sent: Optional[str] = None
    exchange_received: Optional[str] = None

    # Extended ADIF fields - Contacted station info
    name: Optional[str] = None  # Operator name
    qth: Optional[str] = None  # City/location
    state: Optional[str] = None  # State/province
    country: Optional[str] = None  # Country name
    dxcc: Optional[int] = None  # DXCC entity number
    gridsquare: Optional[str] = None  # Maidenhead grid square
    cq_zone: Optional[int] = None  # CQ zone
    itu_zone: Optional[int] = None  # ITU zone
    continent: Optional[str] = None  # Continent (NA, SA, EU, AF, AS, OC, AN)

    # Power and equipment
    tx_pwr: Optional[float] = None  # Transmit power in watts
    rx_pwr: Optional[float] = None  # Received power (if known)
    ant_az: Optional[float] = None  # Antenna azimuth
    ant_el: Optional[float] = None  # Antenna elevation

    # Special activity references
    sota_ref: Optional[str] = None  # SOTA reference (e.g., W4C/CM-001)
    pota_ref: Optional[str] = None  # POTA reference (e.g., K-1234)
    wwff_ref: Optional[str] = None  # WWFF reference
    iota: Optional[str] = None  # IOTA reference (e.g., NA-001)
    sig: Optional[str] = None  # Special interest activity
    sig_info: Optional[str] = None  # Special interest activity info

    # QSL info
    qsl_sent: Optional[str] = None  # Y, N, R, I, Q
    qsl_sent_date: Optional[datetime] = None
    qsl_rcvd: Optional[str] = None  # Y, N, R, I, Q
    qsl_rcvd_date: Optional[datetime] = None
    qsl_via: Optional[str] = None  # QSL route (direct, bureau, manager call)
    lotw_qsl_sent: Optional[str] = None  # LoTW sent status
    lotw_qsl_rcvd: Optional[str] = None  # LoTW received status
    eqsl_qsl_sent: Optional[str] = None  # eQSL sent status
    eqsl_qsl_rcvd: Optional[str] = None  # eQSL received status

    # Propagation
    prop_mode: Optional[str] = None  # Propagation mode (e.g., SAT, EME, TR)
    sat_name: Optional[str] = None  # Satellite name
    sat_mode: Optional[str] = None  # Satellite mode

    # Metadata
    operator: Optional[str] = None  # Logging operator callsign
    station_callsign: Optional[str] = None  # Station callsign if different
    my_gridsquare: Optional[str] = None  # My grid square
    my_sota_ref: Optional[str] = None  # My SOTA reference
    my_pota_ref: Optional[str] = None  # My POTA reference
    comment: Optional[str] = None  # Extended comment

    created_at: Optional[datetime] = None

    @property
    def band(self) -> Optional[Band]:
        """Get the band for this QSO based on frequency."""
        return frequency_to_band(self.frequency)

    @property
    def time_str(self) -> str:
        """Get formatted time string (HH:MM)."""
        return self.datetime_utc.strftime("%H:%M")

    @property
    def date_str(self) -> str:
        """Get formatted date string (YYYY-MM-DD)."""
        return self.datetime_utc.strftime("%Y-%m-%d")


class Contest(BaseModel):
    """Contest configuration."""

    id: Optional[int] = None
    name: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    exchange_format: str = Field(default="RST+SN")
    active: bool = False


class CallsignLookupResult(BaseModel):
    """Result from a callsign lookup service."""

    callsign: str
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    grid_square: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    qsl_via: Optional[str] = None
    email: Optional[str] = None

    @property
    def location_str(self) -> str:
        """Get a formatted location string."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts) if parts else "Unknown"

    @property
    def display_str(self) -> str:
        """Get a formatted display string for the UI."""
        parts = []
        if self.name:
            parts.append(self.name)
        if self.location_str != "Unknown":
            parts.append(self.location_str)
        if self.grid_square:
            parts.append(f"[{self.grid_square}]")
        return " - ".join(parts) if parts else "No information available"
