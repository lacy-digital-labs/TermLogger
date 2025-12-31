"""Callsign lookup services for TermLogger.

Supports:
- QRZ.com XML API (requires subscription)
- HamQTH (free)
"""

import logging
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from .config import AppConfig, LookupService
from .models import CallsignLookupResult

logger = logging.getLogger(__name__)


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
    NS = {"qrz": "http://xmldata.qrz.com"}

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._session_key: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=10.0)

    def _find(self, root: ET.Element, path: str) -> Optional[ET.Element]:
        """Find element with QRZ namespace."""
        # Try with namespace using {uri}tag format
        ns_uri = "http://xmldata.qrz.com"

        # Handle paths like ".//Session" or "Key"
        if path.startswith(".//"):
            tag = path[3:]
            ns_path = f".//{{{ns_uri}}}{tag}"
        elif path.startswith("./"):
            tag = path[2:]
            ns_path = f"./{{{ns_uri}}}{tag}"
        else:
            ns_path = f"{{{ns_uri}}}{path}"

        elem = root.find(ns_path)
        if elem is None:
            # Fallback to without namespace
            elem = root.find(path)
        return elem

    async def authenticate(self) -> bool:
        """Authenticate and get session key."""
        logger.info(f"QRZ: Authenticating as {self.username}")
        try:
            params = {
                "username": self.username,
                "password": self.password,
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()
            logger.debug(f"QRZ: Auth response status={response.status_code}")
            logger.debug(f"QRZ: Auth response XML: {response.text[:500]}")  # First 500 chars

            # Parse XML response
            root = ET.fromstring(response.text)
            session = self._find(root, ".//Session")

            if session is not None:
                key_elem = self._find(session, "Key")
                if key_elem is not None and key_elem.text:
                    self._session_key = key_elem.text
                    logger.info("QRZ: Authentication successful")
                    return True

                # Check for error
                error_elem = self._find(session, "Error")
                if error_elem is not None:
                    logger.error(f"QRZ: Auth error: {error_elem.text}")
                    raise LookupError(f"QRZ auth error: {error_elem.text}")

            logger.warning("QRZ: No session found in auth response")
            return False

        except httpx.HTTPError as e:
            logger.error(f"QRZ: Connection error during auth: {e}")
            raise LookupError(f"QRZ connection error: {e}")
        except ET.ParseError as e:
            logger.error(f"QRZ: XML parse error during auth: {e}")
            raise LookupError(f"QRZ XML parse error: {e}")

    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign using QRZ XML API."""
        logger.info(f"QRZ: Looking up {callsign}")
        if not self._session_key:
            logger.debug("QRZ: No session key, authenticating first")
            if not await self.authenticate():
                logger.warning("QRZ: Authentication failed, cannot lookup")
                return None

        try:
            params = {
                "s": self._session_key,
                "callsign": callsign.upper(),
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()
            logger.debug(f"QRZ: Lookup response status={response.status_code}")
            logger.debug(f"QRZ: Lookup response XML: {response.text[:500]}")  # First 500 chars

            root = ET.fromstring(response.text)

            # Check for session error (expired key)
            session = self._find(root, ".//Session")
            if session is not None:
                error_elem = self._find(session, "Error")
                if error_elem is not None:
                    error_text = error_elem.text or ""
                    if "Session Timeout" in error_text or "Invalid session" in error_text:
                        logger.warning("QRZ: Session expired, re-authenticating")
                        # Re-authenticate and retry
                        self._session_key = None
                        if await self.authenticate():
                            return await self.lookup(callsign)
                    elif "Not found" in error_text:
                        logger.info(f"QRZ: Callsign {callsign} not found")
                        return None
                    else:
                        logger.error(f"QRZ: Lookup error: {error_text}")
                        raise LookupError(f"QRZ error: {error_text}")

            # Parse callsign data
            callsign_elem = self._find(root, ".//Callsign")
            if callsign_elem is None:
                logger.warning(f"QRZ: No callsign data found for {callsign}")
                return None

            result = CallsignLookupResult(
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
            logger.info(f"QRZ: Lookup successful for {callsign} - {result.name or 'No name'}, {result.city or ''} {result.state or ''} {result.country or ''}")
            logger.debug(f"QRZ: Grid={result.grid_square}, Lat/Lon={result.latitude}/{result.longitude}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"QRZ: Connection error during lookup: {e}")
            raise LookupError(f"QRZ connection error: {e}")
        except ET.ParseError as e:
            logger.error(f"QRZ: XML parse error during lookup: {e}")
            raise LookupError(f"QRZ XML parse error: {e}")

    def _get_text(
        self, parent: ET.Element, tag: str, default: str = ""
    ) -> Optional[str]:
        """Get text content of a child element."""
        elem = self._find(parent, tag)
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
    NS = {"h": "https://www.hamqth.com"}  # XML namespace

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self._session_id: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=10.0)

    def _find(self, parent: ET.Element, path: str) -> Optional[ET.Element]:
        """Find element handling HamQTH namespace."""
        # Convert path like ".//session" to use namespace: ".//h:session"
        # Split by / and add namespace prefix to each tag
        parts = path.split('/')
        ns_parts = []
        for part in parts:
            if part and part not in ['.', '..']:
                ns_parts.append(f'h:{part}')
            else:
                ns_parts.append(part)
        ns_path = '/'.join(ns_parts)

        logger.debug(f"HamQTH _find: original='{path}', namespaced='{ns_path}'")
        elem = parent.find(ns_path, self.NS)
        if elem is None:
            logger.debug("HamQTH _find: namespace search failed, trying without namespace")
            # Fallback to without namespace
            elem = parent.find(path)
        else:
            logger.debug("HamQTH _find: found element with namespace")
        return elem

    def _findtext(self, parent: ET.Element, path: str, default: str = "") -> Optional[str]:
        """Get text content of element handling HamQTH namespace."""
        elem = self._find(parent, path)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default if default else None

    async def authenticate(self) -> bool:
        """Authenticate and get session ID."""
        logger.info(f"HamQTH: Authenticating as {self.username}")
        try:
            params = {
                "u": self.username,
                "p": self.password,
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()
            logger.debug(f"HamQTH: Auth response status={response.status_code}")
            logger.debug(f"HamQTH: Auth response XML: {response.text[:500]}")  # First 500 chars

            root = ET.fromstring(response.text)

            # Check for session ID
            session = self._find(root, ".//session")
            if session is not None:
                session_id_text = self._findtext(session, "session_id")
                if session_id_text:
                    self._session_id = session_id_text
                    logger.info("HamQTH: Authentication successful")
                    return True

                # Check for error
                error_text = self._findtext(session, "error")
                if error_text:
                    logger.error(f"HamQTH: Auth error: {error_text}")
                    raise LookupError(f"HamQTH auth error: {error_text}")

            logger.warning("HamQTH: No session found in auth response")
            return False

        except httpx.HTTPError as e:
            logger.error(f"HamQTH: Connection error during auth: {e}")
            raise LookupError(f"HamQTH connection error: {e}")
        except ET.ParseError as e:
            logger.error(f"HamQTH: XML parse error during auth: {e}")
            raise LookupError(f"HamQTH XML parse error: {e}")

    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign using HamQTH API."""
        logger.info(f"HamQTH: Looking up {callsign}")
        if not self._session_id:
            logger.debug("HamQTH: No session ID, authenticating first")
            if not await self.authenticate():
                logger.warning("HamQTH: Authentication failed, cannot lookup")
                return None

        try:
            params = {
                "id": self._session_id,
                "callsign": callsign.upper(),
                "prg": "TermLogger",
            }
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()
            logger.debug(f"HamQTH: Lookup response status={response.status_code}")
            logger.debug(f"HamQTH: Lookup response XML: {response.text[:500]}")  # First 500 chars

            root = ET.fromstring(response.text)

            # Check for session error
            session = self._find(root, ".//session")
            if session is not None:
                error_text = self._findtext(session, "error")
                if error_text:
                    if "Session does not exist" in error_text:
                        logger.warning("HamQTH: Session expired, re-authenticating")
                        self._session_id = None
                        if await self.authenticate():
                            return await self.lookup(callsign)
                    elif "Callsign not found" in error_text:
                        logger.info(f"HamQTH: Callsign {callsign} not found")
                        return None
                    else:
                        logger.error(f"HamQTH: Lookup error: {error_text}")
                        raise LookupError(f"HamQTH error: {error_text}")

            # Parse search result
            search = self._find(root, ".//search")
            if search is None:
                logger.warning(f"HamQTH: No search data found for {callsign}")
                return None

            # Build full name
            nick = self._findtext(search, "nick")
            adr_name = self._findtext(search, "adr_name")
            name = nick or adr_name

            result = CallsignLookupResult(
                callsign=self._findtext(search, "callsign", callsign.upper()),
                name=name,
                address=self._findtext(search, "adr_street1"),
                city=self._findtext(search, "adr_city"),
                state=self._findtext(search, "us_state"),
                country=self._findtext(search, "country"),
                grid_square=self._findtext(search, "grid"),
                latitude=self._get_float(search, "latitude"),
                longitude=self._get_float(search, "longitude"),
                qsl_via=self._findtext(search, "qsl_via"),
                email=self._findtext(search, "email"),
            )
            logger.info(f"HamQTH: Lookup successful for {callsign} - {result.name or 'No name'}, {result.city or ''} {result.state or ''} {result.country or ''}")
            logger.debug(f"HamQTH: Grid={result.grid_square}, Lat/Lon={result.latitude}/{result.longitude}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"HamQTH: Connection error during lookup: {e}")
            raise LookupError(f"HamQTH connection error: {e}")
        except ET.ParseError as e:
            logger.error(f"HamQTH: XML parse error during lookup: {e}")
            raise LookupError(f"HamQTH XML parse error: {e}")

    def _get_float(self, parent: ET.Element, tag: str) -> Optional[float]:
        """Get float value from a child element."""
        text = self._findtext(parent, tag)
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
            logger.debug("Lookup service disabled in config")
            return None

        # Create provider if needed
        if self._provider is None:
            if self.config.lookup_service in (LookupService.QRZ, LookupService.QRZ_XML):
                # Both QRZ options use the XML API (requires subscription)
                if self.config.qrz_username and self.config.qrz_password:
                    logger.info(f"Creating QRZ XML lookup provider for user {self.config.qrz_username}")
                    self._provider = QRZXMLLookup(
                        self.config.qrz_username,
                        self.config.qrz_password,
                    )
                else:
                    logger.warning("QRZ configured but username/password missing")
            elif self.config.lookup_service == LookupService.HAMQTH:
                if self.config.hamqth_username and self.config.hamqth_password:
                    logger.info(f"Creating HamQTH lookup provider for user {self.config.hamqth_username}")
                    self._provider = HamQTHLookup(
                        self.config.hamqth_username,
                        self.config.hamqth_password,
                    )
                else:
                    logger.warning("HamQTH configured but username/password missing")

        return self._provider

    async def lookup(self, callsign: str) -> Optional[CallsignLookupResult]:
        """Look up a callsign.

        Results are cached to avoid repeated API calls.
        """
        callsign = callsign.upper().strip()

        if not callsign:
            logger.debug("Lookup called with empty callsign")
            return None

        # Check cache first
        if callsign in self._cache:
            logger.debug(f"Cache HIT for {callsign}")
            return self._cache[callsign]

        logger.debug(f"Cache MISS for {callsign}, performing lookup")
        provider = self._get_provider()
        if provider is None:
            logger.debug("No lookup provider available")
            return None

        try:
            result = await provider.lookup(callsign)
            if result:
                logger.info(f"Caching lookup result for {callsign}")
                self._cache[callsign] = result
            else:
                logger.debug(f"No result returned for {callsign}")
            return result
        except LookupError as e:
            logger.error(f"Lookup error for {callsign}: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the lookup cache."""
        logger.info(f"Clearing lookup cache ({len(self._cache)} entries)")
        self._cache.clear()

    def update_config(self, config: AppConfig) -> None:
        """Update configuration (clears provider and cache)."""
        logger.info("Updating lookup service configuration")
        self.config = config
        self._provider = None
        self._cache.clear()

    async def close(self) -> None:
        """Close the service and release resources."""
        if self._provider:
            logger.info("Closing lookup service provider")
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
