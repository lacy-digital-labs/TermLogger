"""POTA (Parks on the Air) parks database service."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class POTAParksError(Exception):
    """Error fetching POTA parks data."""

    pass


@dataclass
class Park:
    """POTA park information."""

    reference: str  # e.g., "US-0001", "K-1234"
    name: str  # e.g., "Acadia"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    grid4: Optional[str] = None
    grid6: Optional[str] = None
    parktype: Optional[str] = None  # e.g., "National Park"
    location_desc: Optional[str] = None  # e.g., "US-ME"
    location_name: Optional[str] = None  # e.g., "Maine"
    entity_name: Optional[str] = None  # e.g., "United States of America"
    website: Optional[str] = None
    first_activator: Optional[str] = None
    first_activation_date: Optional[str] = None
    activations: int = 0
    qsos: int = 0

    @property
    def display_name(self) -> str:
        """Get display name with reference."""
        return f"{self.reference}: {self.name}"

    @property
    def location_str(self) -> str:
        """Get location string."""
        parts = []
        if self.location_name:
            parts.append(self.location_name)
        if self.entity_name and self.entity_name != "United States of America":
            parts.append(self.entity_name)
        return ", ".join(parts) if parts else self.location_desc or ""


class POTAParksService:
    """Service for fetching and caching POTA park information.

    The service maintains a local cache of park data to minimize API calls.
    Parks are looked up by reference (e.g., "K-1234" or "US-0001").
    """

    BASE_URL = "https://api.pota.app"
    TIMEOUT = 10.0
    CACHE_FILENAME = "pota_parks_cache.json"
    CACHE_MAX_AGE_DAYS = 7  # Re-fetch park data after this many days

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """Initialize the parks service.

        Args:
            cache_dir: Directory for cache file. Defaults to ~/.config/termlogger
        """
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: dict[str, dict] = {}  # reference -> park data
        self._cache_timestamps: dict[str, str] = {}  # reference -> ISO timestamp

        if cache_dir is None:
            cache_dir = Path.home() / ".config" / "termlogger"
        self._cache_dir = cache_dir
        self._cache_file = cache_dir / self.CACHE_FILENAME

        self._load_cache()

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    data = json.load(f)
                self._cache = data.get("parks", {})
                self._cache_timestamps = data.get("timestamps", {})
                logger.info(f"Loaded {len(self._cache)} parks from cache")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load parks cache: {e}")
                self._cache = {}
                self._cache_timestamps = {}

    def _save_cache(self) -> None:
        """Save cache to disk."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            with open(self._cache_file, "w") as f:
                json.dump(
                    {"parks": self._cache, "timestamps": self._cache_timestamps},
                    f,
                    indent=2,
                )
        except OSError as e:
            logger.warning(f"Failed to save parks cache: {e}")

    def _is_cache_stale(self, reference: str) -> bool:
        """Check if cached park data is stale."""
        if reference not in self._cache_timestamps:
            return True

        try:
            cached_time = datetime.fromisoformat(self._cache_timestamps[reference])
            age = datetime.now(timezone.utc) - cached_time
            return age.days >= self.CACHE_MAX_AGE_DAYS
        except (ValueError, TypeError):
            return True

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

    def get_cached_park(self, reference: str) -> Optional[Park]:
        """Get a park from cache without fetching.

        Args:
            reference: Park reference (e.g., "K-1234")

        Returns:
            Park if cached, None otherwise
        """
        reference = reference.upper()
        if reference in self._cache:
            return self._parse_park(self._cache[reference])
        return None

    async def get_park(self, reference: str, force_refresh: bool = False) -> Optional[Park]:
        """Get park information by reference.

        Args:
            reference: Park reference (e.g., "K-1234" or "US-0001")
            force_refresh: Force refresh from API even if cached

        Returns:
            Park information or None if not found
        """
        reference = reference.upper()

        # Check cache first
        if not force_refresh and reference in self._cache and not self._is_cache_stale(reference):
            return self._parse_park(self._cache[reference])

        # Fetch from API
        try:
            client = await self._get_client()
            response = await client.get(f"{self.BASE_URL}/park/{reference}")

            if response.status_code == 404:
                return None
            response.raise_for_status()

            data = response.json()
            if data is None:
                return None

            # Cache the result
            self._cache[reference] = data
            self._cache_timestamps[reference] = datetime.now(timezone.utc).isoformat()
            self._save_cache()

            return self._parse_park(data)

        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch park {reference}: {e}")
            # Return cached version if available
            if reference in self._cache:
                return self._parse_park(self._cache[reference])
            return None
        except Exception as e:
            logger.error(f"Error fetching park {reference}: {e}")
            return None

    def _parse_park(self, data: dict) -> Park:
        """Parse park data from API response."""
        return Park(
            reference=data.get("reference", ""),
            name=data.get("name", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            grid4=data.get("grid4"),
            grid6=data.get("grid6"),
            parktype=data.get("parktypeDesc"),
            location_desc=data.get("locationDesc"),
            location_name=data.get("locationName"),
            entity_name=data.get("entityName"),
            website=data.get("website"),
            first_activator=data.get("firstActivator"),
            first_activation_date=data.get("firstActivationDate"),
            activations=data.get("activations", 0),
            qsos=data.get("qsos", 0),
        )

    async def get_parks_for_location(self, location_code: str) -> list[Park]:
        """Get all parks for a location.

        Args:
            location_code: Location code (e.g., "US-CA" for California)

        Returns:
            List of parks in that location
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.BASE_URL}/location/parks/{location_code}")
            response.raise_for_status()

            data = response.json()
            parks = []

            for item in data:
                # The location endpoint returns less data, so we create a partial Park
                park = Park(
                    reference=item.get("reference", ""),
                    name=item.get("name", ""),
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                    grid4=item.get("grid"),
                    location_desc=item.get("locationDesc"),
                    activations=item.get("activations", 0),
                    qsos=item.get("qsos", 0),
                )
                parks.append(park)

                # Cache basic info
                self._cache[park.reference] = item
                self._cache_timestamps[park.reference] = datetime.now(timezone.utc).isoformat()

            self._save_cache()
            logger.info(f"Loaded {len(parks)} parks for {location_code}")
            return parks

        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch parks for {location_code}: {e}")
            raise POTAParksError(f"Failed to fetch parks: {e}") from e

    async def prefetch_parks(self, references: list[str]) -> dict[str, Park]:
        """Prefetch multiple parks in parallel.

        Args:
            references: List of park references to fetch

        Returns:
            Dict mapping references to Park objects
        """
        results: dict[str, Park] = {}

        for ref in references:
            ref = ref.upper()
            # Check cache first
            if ref in self._cache and not self._is_cache_stale(ref):
                park = self._parse_park(self._cache[ref])
                results[ref] = park
            else:
                # Fetch from API
                park = await self.get_park(ref)
                if park:
                    results[ref] = park

        return results

    @property
    def cache_size(self) -> int:
        """Get number of cached parks."""
        return len(self._cache)

    def clear_cache(self) -> None:
        """Clear the park cache."""
        self._cache = {}
        self._cache_timestamps = {}
        if self._cache_file.exists():
            try:
                self._cache_file.unlink()
            except OSError:
                pass
        logger.info("Cleared parks cache")
