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
    hamqth_username: str = Field(default="")
    hamqth_password: str = Field(default="")
    auto_lookup: bool = Field(default=True)

    # UI preferences
    default_mode: str = Field(default="SSB")
    default_rst: str = Field(default="59")
    default_frequency: float = Field(default=14.250)

    # Database
    db_path: str = Field(default="")


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
