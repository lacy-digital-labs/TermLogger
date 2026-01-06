"""Configuration management for TermLogger."""

import json
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class LookupService(str, Enum):
    """Callsign lookup service providers."""

    NONE = "none"
    QRZ = "qrz"
    QRZ_XML = "qrz_xml"
    HAMQTH = "hamqth"


class DXClusterSource(str, Enum):
    """DX cluster data sources."""

    TELNET = "telnet"
    WEB_API = "webapi"
    BOTH = "both"


class RigControlType(str, Enum):
    """Rig control backend types."""

    NONE = "none"
    RIGCTLD = "rigctld"  # Hamlib rigctld daemon
    FLEXRADIO = "flexradio"  # Flex Radio SmartSDR API


class AppConfig(BaseModel):
    """Application configuration."""

    # Station info
    my_callsign: str = Field(default="")
    my_name: str = Field(default="")
    my_grid: str = Field(default="")
    my_latitude: Optional[float] = Field(default=None)
    my_longitude: Optional[float] = Field(default=None)
    my_qth: str = Field(default="")  # City/Location
    my_state: str = Field(default="")
    my_country: str = Field(default="")
    my_cq_zone: str = Field(default="")
    my_itu_zone: str = Field(default="")

    # Callsign lookup
    lookup_service: LookupService = LookupService.NONE
    qrz_username: str = Field(default="")
    qrz_password: str = Field(default="")
    qrz_api_key: str = Field(default="")  # QRZ Logbook API key
    hamqth_username: str = Field(default="")
    hamqth_password: str = Field(default="")
    auto_lookup: bool = Field(default=True)

    # Club Log
    clublog_email: str = Field(default="")  # Club Log account email
    clublog_password: str = Field(default="")  # Club Log application password
    clublog_callsign: str = Field(default="")  # Callsign for Club Log uploads
    clublog_api_key: str = Field(default="")  # Club Log API key (request from helpdesk)

    # UI preferences
    default_mode: str = Field(default="SSB")
    default_rst: str = Field(default="59")
    default_frequency: float = Field(default=14.250)

    # Database
    db_path: str = Field(default="")

    # POTA Spots
    pota_spots_enabled: bool = Field(default=True)
    pota_spots_refresh_seconds: int = Field(default=60, ge=10, le=300)

    # DX Cluster
    dx_cluster_enabled: bool = Field(default=True)
    dx_cluster_source: DXClusterSource = DXClusterSource.WEB_API
    dx_cluster_host: str = Field(default="dxc.nc7j.com")
    dx_cluster_port: int = Field(default=7373, ge=1, le=65535)
    dx_cluster_callsign: str = Field(default="")  # Uses my_callsign if empty
    dx_cluster_refresh_seconds: int = Field(default=30, ge=10, le=300)

    # Rig Control
    rig_control_type: RigControlType = RigControlType.NONE
    rig_auto_qsy: bool = Field(default=True)  # QSY radio on spot click
    rig_poll_interval: float = Field(default=0.5, ge=0.1, le=5.0)

    # Rig Control - rigctld settings
    rigctld_host: str = Field(default="localhost")
    rigctld_port: int = Field(default=4532, ge=1, le=65535)

    # Rig Control - Flex Radio settings
    flexradio_host: str = Field(default="localhost")
    flexradio_port: int = Field(default=4992, ge=1, le=65535)

    # UDP Log Server
    udp_log_server_enabled: bool = Field(default=False)
    udp_log_server_port: int = Field(default=2237, ge=1024, le=65535)  # WSJT-X default
    udp_log_server_host: str = Field(default="0.0.0.0")  # Listen on all interfaces
    udp_log_server_notify: bool = Field(default=True)  # Show notification on receive

    # Debug Logging
    debug_logging_enabled: bool = Field(default=False)
    debug_log_level: str = Field(default="INFO")  # DEBUG, INFO, WARNING, ERROR
    debug_log_file: str = Field(default="termlogger.log")

    # Legacy compatibility (maps to rig_control_type)
    @property
    def rigctld_enabled(self) -> bool:
        """Legacy property for rigctld_enabled."""
        return self.rig_control_type == RigControlType.RIGCTLD

    @property
    def rigctld_auto_qsy(self) -> bool:
        """Legacy property for rigctld_auto_qsy."""
        return self.rig_auto_qsy

    @property
    def rigctld_poll_interval(self) -> float:
        """Legacy property for rigctld_poll_interval."""
        return self.rig_poll_interval


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_dir = Path.home() / ".config" / "termlogger"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def get_default_db_path() -> Path:
    """Get the default database path."""
    data_dir = Path.home() / ".local" / "share" / "termlogger"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "termlogger.db"


def load_config() -> AppConfig:
    """Load configuration from file or create default."""
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            config = AppConfig(**data)
        except (json.JSONDecodeError, ValueError):
            config = AppConfig()
    else:
        config = AppConfig()

    # Set default db path if not configured
    if not config.db_path:
        config.db_path = str(get_default_db_path())

    return config


def save_config(config: AppConfig) -> None:
    """Save configuration to file."""
    config_path = get_config_path()

    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
