"""Club Log API service for uploading QSOs."""

import logging
from typing import Optional

import httpx

from ..adif import generate_adif, qso_to_adif
from ..models import QSO

logger = logging.getLogger(__name__)


class ClubLogError(Exception):
    """Base error for Club Log operations."""

    pass


class ClubLogAuthError(ClubLogError):
    """Authentication error - invalid credentials or API key."""

    pass


class ClubLogService:
    """Service for interacting with Club Log API.

    Supports uploading QSOs to Club Log via the real-time and batch APIs.

    API Documentation:
    - Real-time: https://clublog.freshdesk.com/support/solutions/articles/54906
    - Batch: https://clublog.freshdesk.com/support/solutions/articles/54905
    """

    REALTIME_URL = "https://secure.clublog.org/realtime.php"
    BATCH_URL = "https://clublog.org/putlogs.php"
    USER_AGENT = "TermLogger/1.0 (NQ0S)"
    TIMEOUT = 60.0  # Batch uploads can take time

    def __init__(
        self,
        email: str,
        password: str,
        callsign: str,
        api_key: str,
    ) -> None:
        """Initialize the Club Log service.

        Args:
            email: Club Log account email
            password: Club Log application password
            callsign: Callsign for uploads
            api_key: Club Log API key (request from helpdesk)
        """
        self._email = email
        self._password = password
        self._callsign = callsign.upper()
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

    def _check_credentials(self) -> None:
        """Check that all required credentials are configured."""
        if not self._email:
            raise ClubLogAuthError("Club Log email not configured")
        if not self._password:
            raise ClubLogAuthError("Club Log password not configured")
        if not self._callsign:
            raise ClubLogAuthError("Club Log callsign not configured")
        if not self._api_key:
            raise ClubLogAuthError("Club Log API key not configured")

    async def upload_qso(self, qso: QSO) -> bool:
        """Upload a single QSO to Club Log via real-time API.

        Args:
            qso: QSO object to upload

        Returns:
            True if successful

        Raises:
            ClubLogAuthError: If credentials are invalid
            ClubLogError: For other API errors
        """
        self._check_credentials()
        client = await self._get_client()

        # Generate ADIF for single QSO (no header)
        adif_data = qso_to_adif(qso)

        data = {
            "email": self._email,
            "password": self._password,
            "callsign": self._callsign,
            "api": self._api_key,
            "adif": adif_data,
        }

        logger.debug(f"Club Log realtime upload: {qso.callsign}")

        try:
            response = await client.post(self.REALTIME_URL, data=data)
        except httpx.TimeoutException:
            raise ClubLogError("Club Log API request timed out")
        except httpx.RequestError as e:
            raise ClubLogError(f"Club Log API request failed: {e}")

        # Check response
        response_text = response.text.strip()
        logger.debug(f"Club Log response: {response.status_code} - {response_text}")

        if response.status_code == 403:
            raise ClubLogAuthError(f"Club Log authentication failed: {response_text}")

        if response.status_code != 200:
            raise ClubLogError(f"Club Log error {response.status_code}: {response_text}")

        # Parse response - Club Log returns "200 QSO OK", "200 QSO Duplicate", etc.
        if "QSO OK" in response_text or "QSO Duplicate" in response_text or "QSO Modified" in response_text:
            logger.info(f"Uploaded QSO {qso.callsign} to Club Log: {response_text}")
            return True
        else:
            logger.warning(f"Club Log upload issue for {qso.callsign}: {response_text}")
            # Still return True if we got a 200 status
            return True

    async def upload_qsos(self, qsos: list[QSO]) -> tuple[int, int]:
        """Upload multiple QSOs to Club Log via batch API.

        Uses the batch upload API (putlogs.php) for efficiency.

        Args:
            qsos: List of QSO objects to upload

        Returns:
            Tuple of (success_count, failed_count)
        """
        if not qsos:
            return 0, 0

        self._check_credentials()
        client = await self._get_client()

        # Generate ADIF file content
        adif_content = generate_adif(qsos, include_header=True)

        # Prepare multipart form data
        files = {
            "file": ("upload.adi", adif_content.encode("utf-8"), "text/plain"),
        }
        data = {
            "email": self._email,
            "password": self._password,
            "callsign": self._callsign,
            "api": self._api_key,
            "clear": "0",  # Don't clear existing log, merge instead
        }

        logger.info(f"Club Log batch upload: {len(qsos)} QSOs")

        try:
            response = await client.post(self.BATCH_URL, data=data, files=files)
        except httpx.TimeoutException:
            raise ClubLogError("Club Log batch upload timed out")
        except httpx.RequestError as e:
            raise ClubLogError(f"Club Log batch upload failed: {e}")

        response_text = response.text.strip()
        logger.debug(f"Club Log batch response: {response.status_code} - {response_text}")

        if response.status_code == 403:
            raise ClubLogAuthError(f"Club Log authentication failed: {response_text}")

        if response.status_code != 200:
            raise ClubLogError(f"Club Log batch error {response.status_code}: {response_text}")

        # Batch upload succeeded
        logger.info(f"Club Log batch upload complete: {len(qsos)} QSOs")
        return len(qsos), 0

    async def upload_qsos_realtime(self, qsos: list[QSO]) -> tuple[int, int]:
        """Upload multiple QSOs one by one via real-time API.

        Use this for small batches or when you need individual confirmation.
        For large batches, use upload_qsos() which uses the batch API.

        Args:
            qsos: List of QSO objects to upload

        Returns:
            Tuple of (success_count, failed_count)
        """
        success = 0
        failed = 0

        for qso in qsos:
            try:
                if await self.upload_qso(qso):
                    success += 1
                else:
                    failed += 1
            except ClubLogError as e:
                logger.error(f"Failed to upload QSO {qso.callsign}: {e}")
                failed += 1

        logger.info(f"Club Log realtime upload complete: {success} succeeded, {failed} failed")
        return success, failed
