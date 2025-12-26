"""Callsign lookup services for TermLogger.

Supports:
- QRZ.com XML API (requires subscription)
- HamQTH (free)
"""

import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from .config import AppConfig, LookupService
from .models import CallsignLookupResult


class LookupError(Exception):
    """Error during callsign lookup."""

    pass


class CallsignLookupProvider(ABC):
    """Abstract base class for callsign lookup providers."""

    @abstractmethod
    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign and return the result."""
        pass

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate with the service. Returns True if successful."""
        pass


class QRZXMLLookup(CallsignLookupProvider):
    """QRZ.com XML API lookup provider.

    Requires a QRZ.com XML subscription.
    API docs: https://www.qrz.com/XML/current_spec.html
    """

    API_URL = "https://xmldata.qrz.com/xml/current/"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._session_key: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def authenticate(self) -> bool:
        """Authenticate and get session key."""
        try:
            params = {
                "username": self.username,
                "password": self.password,
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()

            # Parse XML response
            root = ET.fromstring(response.text)
            session = root.find(".//Session")

            if session is not None:
                key_elem = session.find("Key")
                if key_elem is not None and key_elem.text:
                    self._session_key = key_elem.text
                    return True

                # Check for error
                error_elem = session.find("Error")
                if error_elem is not None:
                    raise LookupError(f"QRZ auth error: {error_elem.text}")

            return False

        except httpx.HTTPError as e:
            raise LookupError(f"QRZ connection error: {e}")
        except ET.ParseError as e:
            raise LookupError(f"QRZ XML parse error: {e}")

    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign using QRZ XML API."""
        if not self._session_key:
            if not await self.authenticate():
                return None

        try:
            params = {
                "s": self._session_key,
                "callsign": callsign.upper(),
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)

            # Check for session error (expired key)
            session = root.find(".//Session")
            if session is not None:
                error_elem = session.find("Error")
                if error_elem is not None:
                    error_text = error_elem.text or ""
                    if "Session Timeout" in error_text or "Invalid session" in error_text:
                        # Re-authenticate and retry
                        self._session_key = None
                        if await self.authenticate():
                            return await self.lookup(callsign)
                    elif "Not found" in error_text:
                        return None
                    else:
                        raise LookupError(f"QRZ error: {error_text}")

            # Parse callsign data
            callsign_elem = root.find(".//Callsign")
            if callsign_elem is None:
                return None

            return CallsignLookupResult(
                callsign=self._get_text(callsign_elem, "call", callsign.upper()),
                name=self._get_full_name(callsign_elem),
                address=self._get_text(callsign_elem, "addr1"),
                city=self._get_text(callsign_elem, "addr2"),
                state=self._get_text(callsign_elem, "state"),
                country=self._get_text(callsign_elem, "country"),
                grid_square=self._get_text(callsign_elem, "grid"),
                latitude=self._get_float(callsign_elem, "lat"),
                longitude=self._get_float(callsign_elem, "lon"),
                qsl_via=self._get_text(callsign_elem, "qslmgr"),
                email=self._get_text(callsign_elem, "email"),
            )

        except httpx.HTTPError as e:
            raise LookupError(f"QRZ connection error: {e}")
        except ET.ParseError as e:
            raise LookupError(f"QRZ XML parse error: {e}")

    def _get_text(
        self, parent: ET.Element, tag: str, default: str = ""
    ) -> Optional[str]:
        """Get text content of a child element."""
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default if default else None

    def _get_float(self, parent: ET.Element, tag: str) -> Optional[float]:
        """Get float value from a child element."""
        text = self._get_text(parent, tag)
        if text:
            try:
                return float(text)
            except ValueError:
                pass
        return None

    def _get_full_name(self, callsign_elem: ET.Element) -> Optional[str]:
        """Construct full name from first/last name elements."""
        fname = self._get_text(callsign_elem, "fname", "")
        name = self._get_text(callsign_elem, "name", "")

        if fname and name:
            return f"{fname} {name}"
        elif name:
            return name
        elif fname:
            return fname
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class HamQTHLookup(CallsignLookupProvider):
    """HamQTH.com lookup provider.

    Free callsign lookup service.
    API docs: https://www.hamqth.com/developers.php
    """

    API_URL = "https://www.hamqth.com/xml.php"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._session_id: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=10.0)

    async def authenticate(self) -> bool:
        """Authenticate and get session ID."""
        try:
            params = {
                "u": self.username,
                "p": self.password,
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)

            # Check for session ID
            session = root.find(".//session")
            if session is not None:
                session_id = session.find("session_id")
                if session_id is not None and session_id.text:
                    self._session_id = session_id.text
                    return True

                # Check for error
                error = session.find("error")
                if error is not None:
                    raise LookupError(f"HamQTH auth error: {error.text}")

            return False

        except httpx.HTTPError as e:
            raise LookupError(f"HamQTH connection error: {e}")
        except ET.ParseError as e:
            raise LookupError(f"HamQTH XML parse error: {e}")

    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign using HamQTH API."""
        if not self._session_id:
            if not await self.authenticate():
                return None

        try:
            params = {
                "id": self._session_id,
                "callsign": callsign.upper(),
                "prg": "TermLogger",
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()

            root = ET.fromstring(response.text)

            # Check for session error
            session = root.find(".//session")
            if session is not None:
                error = session.find("error")
                if error is not None:
                    error_text = error.text or ""
                    if "Session does not exist" in error_text:
                        self._session_id = None
                        if await self.authenticate():
                            return await self.lookup(callsign)
                    elif "Callsign not found" in error_text:
                        return None
                    else:
                        raise LookupError(f"HamQTH error: {error_text}")

            # Parse search result
            search = root.find(".//search")
            if search is None:
                return None

            # Build full name
            nick = self._get_text(search, "nick")
            adr_name = self._get_text(search, "adr_name")
            name = nick or adr_name

            return CallsignLookupResult(
                callsign=self._get_text(search, "callsign", callsign.upper()),
                name=name,
                address=self._get_text(search, "adr_street1"),
                city=self._get_text(search, "adr_city"),
                state=self._get_text(search, "us_state"),
                country=self._get_text(search, "country"),
                grid_square=self._get_text(search, "grid"),
                latitude=self._get_float(search, "latitude"),
                longitude=self._get_float(search, "longitude"),
                qsl_via=self._get_text(search, "qsl_via"),
                email=self._get_text(search, "email"),
            )

        except httpx.HTTPError as e:
            raise LookupError(f"HamQTH connection error: {e}")
        except ET.ParseError as e:
            raise LookupError(f"HamQTH XML parse error: {e}")

    def _get_text(
        self, parent: ET.Element, tag: str, default: str = ""
    ) -> Optional[str]:
        """Get text content of a child element."""
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default if default else None

    def _get_float(self, parent: ET.Element, tag: str) -> Optional[float]:
        """Get float value from a child element."""
        text = self._get_text(parent, tag)
        if text:
            try:
                return float(text)
            except ValueError:
                pass
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()


class CallsignLookupService:
    """Main callsign lookup service that manages providers."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._provider: Optional[CallsignLookupProvider] = None
        self._cache: dict[str, CallsignLookupResult] = {}

    def _get_provider(self) -> Optional[CallsignLookupProvider]:
        """Get or create the lookup provider based on config."""
        if self.config.lookup_service == LookupService.NONE:
            return None

        # Create provider if needed
        if self._provider is None:
            if self.config.lookup_service == LookupService.QRZ_XML:
                if self.config.qrz_username and self.config.qrz_password:
                    self._provider = QRZXMLLookup(
                        self.config.qrz_username,
                        self.config.qrz_password,
                    )
            elif self.config.lookup_service == LookupService.HAMQTH:
                if self.config.hamqth_username and self.config.hamqth_password:
                    self._provider = HamQTHLookup(
                        self.config.hamqth_username,
                        self.config.hamqth_password,
                    )

        return self._provider

    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign.

        Results are cached to avoid repeated API calls.
        """
        callsign = callsign.upper().strip()

        if not callsign:
            return None

        # Check cache first
        if callsign in self._cache:
            return self._cache[callsign]

        provider = self._get_provider()
        if provider is None:
            return None

        try:
            result = await provider.lookup(callsign)
            if result:
                self._cache[callsign] = result
            return result
        except LookupError:
            return None

    def clear_cache(self) -> None:
        """Clear the lookup cache."""
        self._cache.clear()

    def update_config(self, config: AppConfig) -> None:
        """Update configuration (clears provider and cache)."""
        self.config = config
        self._provider = None
        self._cache.clear()

    async def close(self) -> None:
        """Close the service and release resources."""
        if self._provider:
            await self._provider.close()
            self._provider = None


# Convenience function for one-off lookups
async def lookup_callsign(
    callsign: str, config: AppConfig
) -> Optional[CallsignLookupResult]:
    """Perform a single callsign lookup."""
    service = CallsignLookupService(config)
    try:
        return await service.lookup(callsign)
    finally:
        await service.close()
