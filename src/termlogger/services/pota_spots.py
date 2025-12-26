"""POTA (Parks on the Air) spots service."""

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models import Spot, SpotSource

logger = logging.getLogger(__name__)


class POTASpotError(Exception):
    """Error fetching POTA spots."""

    pass


class POTASpotService:
    """Service for fetching POTA activator spots from pota.app API."""

    BASE_URL = "https://api.pota.app/spot/activator"
    TIMEOUT = 10.0

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                headers={"User-Agent": "TermLogger/0.1.0"},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_spots(self, limit: int = 50) -> list[Spot]:
        """
        Fetch recent POTA activator spots.

        Args:
            limit: Maximum number of spots to return

        Returns:
            List of Spot objects
        """
        try:
            client = await self._get_client()
            response = await client.get(self.BASE_URL)
            response.raise_for_status()

            data = response.json()
            spots = []

            for item in data[:limit]:
                spot = self._parse_spot(item)
                if spot:
                    spots.append(spot)

            return spots

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching POTA spots: {e}")
            raise POTASpotError(f"Failed to fetch POTA spots: {e}") from e
        except Exception as e:
            logger.error(f"Error fetching POTA spots: {e}")
            raise POTASpotError(f"Failed to fetch POTA spots: {e}") from e

    def _parse_spot(self, data: dict) -> Optional[Spot]:
        """Parse a spot from the POTA API response."""
        try:
            # Parse frequency - POTA returns it as a string like "14.250"
            freq_str = data.get("frequency", "0")
            try:
                frequency = float(freq_str)
            except (ValueError, TypeError):
                frequency = 0.0

            if frequency <= 0:
                return None

            # Parse spot time
            spot_time_str = data.get("spotTime", "")
            try:
                # POTA returns ISO format like "2024-01-15T14:30:00Z"
                spot_time = datetime.fromisoformat(
                    spot_time_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                spot_time = datetime.now(timezone.utc)

            return Spot(
                callsign=data.get("activator", "").upper(),
                frequency=frequency,
                mode=data.get("mode", "").upper() or None,
                spotter=data.get("spotter", "").upper(),
                comment=data.get("comments", ""),
                time=spot_time,
                source=SpotSource.POTA,
                park_reference=data.get("reference", ""),
                park_name=data.get("parkName", ""),
                grid_square=data.get("grid", None),
                state=None,  # Not always provided
                country=None,  # Could extract from reference prefix
            )

        except Exception as e:
            logger.warning(f"Failed to parse POTA spot: {e}")
            return None

    async def get_spots_by_reference(self, park_reference: str) -> list[Spot]:
        """
        Fetch spots for a specific park reference.

        Args:
            park_reference: Park reference (e.g., "K-1234")

        Returns:
            List of Spot objects for that park
        """
        spots = await self.get_spots(limit=100)
        return [s for s in spots if s.park_reference == park_reference.upper()]

    async def get_spots_by_band(self, band: str) -> list[Spot]:
        """
        Fetch spots filtered by band.

        Args:
            band: Band name (e.g., "20m")

        Returns:
            List of Spot objects on that band
        """
        spots = await self.get_spots(limit=100)
        return [s for s in spots if s.band and s.band.value == band]
