"""QRZ Logbook API service for uploading and downloading QSOs."""

import logging
from typing import Optional
from urllib.parse import parse_qs

import httpx

from ..adif import parse_adif, qso_to_adif
from ..models import QSO

logger = logging.getLogger(__name__)


class QRZLogbookError(Exception):
    """Base error for QRZ Logbook operations."""

    pass


class QRZLogbookAuthError(QRZLogbookError):
    """Authentication error - invalid or missing API key."""

    pass


class QRZLogbookService:
    """Service for interacting with QRZ Logbook API.

    Supports uploading and downloading QSOs via the QRZ Logbook API.
    Requires a valid QRZ Logbook API key (subscription required).

    API Documentation: https://www.qrz.com/docs/logbook/QRZLogbookAPI.html
    """

    API_URL = "https://logbook.qrz.com/api"
    USER_AGENT = "TermLogger/1.0 (NQ0S)"
    TIMEOUT = 30.0
    MAX_FETCH_PER_REQUEST = 250

    def __init__(self, api_key: str) -> None:
        """Initialize the QRZ Logbook service.

        Args:
            api_key: QRZ Logbook API key
        """
        self._api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                headers={"User-Agent": self.USER_AGENT},
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _parse_response(self, response_text: str) -> dict[str, str]:
        """Parse QRZ API response.

        QRZ returns URL-encoded name=value pairs separated by &.

        Args:
            response_text: Raw response text from API

        Returns:
            Dictionary of response fields
        """
        result = {}
        # Parse URL-encoded format
        parsed = parse_qs(response_text, keep_blank_values=True)
        for key, values in parsed.items():
            # parse_qs returns lists, take first value
            result[key] = values[0] if values else ""
        return result

    async def _request(
        self, action: str, params: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Make a request to the QRZ Logbook API.

        Args:
            action: API action (INSERT, DELETE, STATUS, FETCH)
            params: Additional parameters

        Returns:
            Parsed response dictionary

        Raises:
            QRZLogbookAuthError: If API key is invalid or missing
            QRZLogbookError: For other API errors
        """
        if not self._api_key:
            raise QRZLogbookAuthError("QRZ Logbook API key not configured")

        client = await self._get_client()

        # Build request data
        data = {"KEY": self._api_key, "ACTION": action}
        if params:
            data.update(params)

        logger.debug(f"QRZ Logbook API request: action={action}")

        try:
            response = await client.post(self.API_URL, data=data)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise QRZLogbookError("QRZ Logbook API request timed out")
        except httpx.HTTPStatusError as e:
            raise QRZLogbookError(f"QRZ Logbook API HTTP error: {e}")
        except httpx.RequestError as e:
            raise QRZLogbookError(f"QRZ Logbook API request failed: {e}")

        result = self._parse_response(response.text)
        logger.debug(f"QRZ Logbook API response: {result.get('RESULT', 'unknown')}")

        # Check for errors
        if result.get("RESULT") == "FAIL":
            reason = result.get("REASON", "Unknown error")
            if "auth" in reason.lower() or "key" in reason.lower():
                raise QRZLogbookAuthError(f"QRZ Logbook authentication failed: {reason}")
            raise QRZLogbookError(f"QRZ Logbook API error: {reason}")

        if result.get("RESULT") == "AUTH":
            raise QRZLogbookAuthError("QRZ Logbook API key is invalid or lacks permissions")

        return result

    async def get_status(self) -> dict[str, str]:
        """Get logbook status and statistics.

        Returns:
            Dictionary with logbook statistics (count, confirmed, DXCC, etc.)
        """
        result = await self._request("STATUS")
        # Parse the DATA field if present
        data = result.get("DATA", "")
        status = {}
        if data:
            # DATA contains name:value pairs
            for pair in data.split("&"):
                if ":" in pair:
                    key, value = pair.split(":", 1)
                    status[key.strip()] = value.strip()
        return status

    async def upload_qso(self, qso: QSO, replace: bool = True) -> Optional[str]:
        """Upload a single QSO to QRZ Logbook.

        Args:
            qso: QSO object to upload
            replace: If True, replace existing duplicate QSOs

        Returns:
            QRZ logid if successful, None if failed

        Raises:
            QRZLogbookAuthError: If API key is invalid
            QRZLogbookError: For other API errors
        """
        adif_data = qso_to_adif(qso)

        params = {"ADIF": adif_data}
        if replace:
            params["OPTION"] = "REPLACE"

        result = await self._request("INSERT", params)

        if result.get("RESULT") in ("OK", "REPLACE"):
            logid = result.get("LOGID")
            logger.info(f"Uploaded QSO {qso.callsign} to QRZ, logid={logid}")
            return logid
        else:
            logger.warning(f"Failed to upload QSO {qso.callsign}: {result}")
            return None

    async def upload_qsos(
        self, qsos: list[QSO], replace: bool = True
    ) -> tuple[int, int, list[tuple[QSO, Optional[str]]]]:
        """Upload multiple QSOs to QRZ Logbook.

        QRZ API only supports one QSO per request, so this iterates through
        all QSOs and uploads them individually.

        Args:
            qsos: List of QSO objects to upload
            replace: If True, replace existing duplicate QSOs

        Returns:
            Tuple of (success_count, failed_count, results_list)
            results_list contains tuples of (qso, logid or None)
        """
        success = 0
        failed = 0
        results: list[tuple[QSO, Optional[str]]] = []

        for qso in qsos:
            try:
                logid = await self.upload_qso(qso, replace=replace)
                if logid:
                    success += 1
                    results.append((qso, logid))
                else:
                    failed += 1
                    results.append((qso, None))
            except QRZLogbookError as e:
                logger.error(f"Failed to upload QSO {qso.callsign}: {e}")
                failed += 1
                results.append((qso, None))

        logger.info(f"QRZ upload complete: {success} succeeded, {failed} failed")
        return success, failed, results

    async def fetch_qsos(
        self,
        after_logid: str = "0",
        max_records: int = 250,
        call: Optional[str] = None,
        band: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> tuple[list[QSO], Optional[str]]:
        """Fetch QSOs from QRZ Logbook.

        Args:
            after_logid: Fetch records after this logid (for paging)
            max_records: Maximum records to fetch (max 250)
            call: Filter by callsign
            band: Filter by band
            mode: Filter by mode

        Returns:
            Tuple of (list of QSOs, last_logid for paging)
        """
        max_records = min(max_records, self.MAX_FETCH_PER_REQUEST)

        # Build OPTION parameter
        options = [f"MAX:{max_records}", f"AFTERLOGID:{after_logid}"]
        if call:
            options.append(f"CALL:{call}")
        if band:
            options.append(f"BAND:{band}")
        if mode:
            options.append(f"MODE:{mode}")

        params = {"OPTION": ",".join(options)}

        result = await self._request("FETCH", params)

        if result.get("RESULT") != "OK":
            logger.warning(f"QRZ fetch failed: {result}")
            return [], None

        count = int(result.get("COUNT", "0"))
        if count == 0:
            return [], None

        # Parse ADIF data
        adif_data = result.get("ADIF", "")
        if not adif_data:
            return [], None

        qsos = parse_adif(adif_data)

        # Get last logid for paging (from LOGIDS field or last QSO)
        logids = result.get("LOGIDS", "")
        last_logid = None
        if logids:
            logid_list = logids.split(",")
            if logid_list:
                last_logid = logid_list[-1].strip()

        logger.info(f"Fetched {len(qsos)} QSOs from QRZ")
        return qsos, last_logid

    async def fetch_all_qsos(
        self,
        call: Optional[str] = None,
        band: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> list[QSO]:
        """Fetch all QSOs from QRZ Logbook with automatic paging.

        Args:
            call: Filter by callsign
            band: Filter by band
            mode: Filter by mode

        Returns:
            List of all QSOs from the logbook
        """
        all_qsos: list[QSO] = []
        after_logid = "0"

        while True:
            qsos, last_logid = await self.fetch_qsos(
                after_logid=after_logid,
                max_records=self.MAX_FETCH_PER_REQUEST,
                call=call,
                band=band,
                mode=mode,
            )

            if not qsos:
                break

            all_qsos.extend(qsos)

            if not last_logid or len(qsos) < self.MAX_FETCH_PER_REQUEST:
                # No more records
                break

            after_logid = last_logid

        logger.info(f"Fetched total of {len(all_qsos)} QSOs from QRZ")
        return all_qsos

    async def delete_qso(self, logid: str) -> bool:
        """Delete a QSO from QRZ Logbook.

        Args:
            logid: QRZ logid of the QSO to delete

        Returns:
            True if deleted successfully
        """
        params = {"LOGIDS": logid}
        result = await self._request("DELETE", params)

        if result.get("RESULT") == "OK":
            count = int(result.get("COUNT", "0"))
            logger.info(f"Deleted {count} QSO(s) from QRZ, logid={logid}")
            return count > 0
        else:
            logger.warning(f"Failed to delete QSO logid={logid}: {result}")
            return False
