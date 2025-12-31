"""UDP log server for receiving ADIF messages from external programs."""

import asyncio
import logging
import struct
from typing import Callable, Optional

from ..adif import parse_adif
from ..models import QSO

logger = logging.getLogger(__name__)

# WSJT-X protocol constants
WSJTX_MAGIC = 0xADBCCBDA
WSJTX_SCHEMA_VERSION = 2
WSJTX_TYPE_LOGGED_ADIF = 12


class UDPLogServerProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for receiving ADIF log messages."""

    def __init__(self, on_qso_received: Callable[[QSO, str], None]):
        """Initialize protocol handler.

        Args:
            on_qso_received: Callback function(qso, source) called when QSO received
        """
        self.on_qso_received = on_qso_received
        self.transport = None

    def connection_made(self, transport):
        """Called when connection is established."""
        self.transport = transport
        logger.info("UDP log server protocol ready")

    def datagram_received(self, data: bytes, addr):
        """Handle incoming UDP datagram.

        Args:
            data: Raw datagram bytes
            addr: Sender address tuple (host, port)
        """
        try:
            # Try WSJT-X LoggedADIF format first (binary)
            qso, source = self._parse_wsjtx_logged_adif(data)

            if qso is None:
                # Fall back to simple ADIF text format
                qso, source = self._parse_simple_adif(data)

            if qso is not None:
                logger.info(f"Received {source} QSO from {addr}: {qso.callsign}")
                self.on_qso_received(qso, source)
            else:
                logger.warning(f"Could not parse UDP message from {addr}")

        except Exception as e:
            logger.error(f"Error processing UDP message from {addr}: {e}", exc_info=True)

    def _parse_wsjtx_logged_adif(self, data: bytes) -> tuple[Optional[QSO], str]:
        """Parse WSJT-X LoggedADIF binary format.

        Format:
        - Magic number (uint32): 0xADBCCBDA
        - Schema version (uint32): 2
        - Message type (uint32): 12 (LoggedADIF)
        - ID string (length-prefixed UTF-8)
        - ADIF text (length-prefixed UTF-8)

        Args:
            data: Binary message data

        Returns:
            Tuple of (QSO object or None, source string)
        """
        try:
            if len(data) < 12:
                return None, ""

            # Check magic number
            magic = struct.unpack(">I", data[0:4])[0]
            if magic != WSJTX_MAGIC:
                return None, ""

            # Check schema version
            schema = struct.unpack(">I", data[4:8])[0]
            if schema != WSJTX_SCHEMA_VERSION:
                logger.warning(f"WSJT-X schema version {schema} != expected {WSJTX_SCHEMA_VERSION}")
                return None, ""

            # Check message type
            msg_type = struct.unpack(">I", data[8:12])[0]
            if msg_type != WSJTX_TYPE_LOGGED_ADIF:
                return None, ""

            # Parse ID string (length-prefixed UTF-8)
            offset = 12
            id_len = struct.unpack(">I", data[offset : offset + 4])[0]
            offset += 4
            # id_string = data[offset : offset + id_len].decode("utf-8")
            offset += id_len

            # Parse ADIF text (length-prefixed UTF-8)
            adif_len = struct.unpack(">I", data[offset : offset + 4])[0]
            offset += 4
            adif_text = data[offset : offset + adif_len].decode("utf-8")

            # Parse ADIF
            qsos = parse_adif(adif_text)
            if qsos:
                qso = qsos[0]
                qso.source = "udp_wsjtx"
                return qso, "WSJT-X"

            return None, ""

        except Exception as e:
            logger.debug(f"Failed to parse as WSJT-X LoggedADIF: {e}")
            return None, ""

    def _parse_simple_adif(self, data: bytes) -> tuple[Optional[QSO], str]:
        """Parse simple ADIF text format.

        Args:
            data: Text message data (UTF-8 encoded)

        Returns:
            Tuple of (QSO object or None, source string)
        """
        try:
            # Try to decode as UTF-8 text
            adif_text = data.decode("utf-8")

            # Must contain ADIF field markers
            if "<" not in adif_text or ">" not in adif_text:
                return None, ""

            # Parse ADIF
            qsos = parse_adif(adif_text)
            if qsos:
                qso = qsos[0]
                qso.source = "udp_adif"
                return qso, "ADIF"

            return None, ""

        except Exception as e:
            logger.debug(f"Failed to parse as simple ADIF: {e}")
            return None, ""

    def error_received(self, exc):
        """Handle protocol errors."""
        logger.error(f"UDP protocol error: {exc}")

    def connection_lost(self, exc):
        """Handle connection loss."""
        if exc:
            logger.warning(f"UDP connection lost: {exc}")
        else:
            logger.info("UDP log server protocol closed")


class UDPLogServer:
    """UDP server to receive ADIF log messages from external programs.

    Supports:
    - Simple ADIF over UDP (plain text ADIF records)
    - WSJT-X LoggedADIF (binary protocol with magic number 0xADBCCBDA)
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 2237,
        on_qso_received: Optional[Callable[[QSO, str], None]] = None,
    ):
        """Initialize UDP log server.

        Args:
            host: Host to bind to (default: 0.0.0.0 for all interfaces)
            port: Port to listen on (default: 2237, WSJT-X default)
            on_qso_received: Callback function(qso, source) called when QSO received
        """
        self.host = host
        self.port = port
        self.on_qso_received = on_qso_received or self._default_callback
        self.transport = None
        self.protocol = None
        self._running = False

    def _default_callback(self, qso: QSO, source: str) -> None:
        """Default callback that just logs the QSO."""
        logger.info(f"Received {source} QSO: {qso.callsign} on {qso.frequency} MHz")

    async def start(self) -> None:
        """Start the UDP server."""
        if self._running:
            logger.warning("UDP log server already running")
            return

        try:
            loop = asyncio.get_event_loop()

            # Create datagram endpoint
            self.transport, self.protocol = await loop.create_datagram_endpoint(
                lambda: UDPLogServerProtocol(self.on_qso_received),
                local_addr=(self.host, self.port),
            )

            self._running = True
            logger.info(f"UDP log server listening on {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to start UDP log server: {e}")
            raise

    async def stop(self) -> None:
        """Stop the UDP server."""
        if not self._running:
            return

        try:
            if self.transport:
                self.transport.close()
                self.transport = None
                self.protocol = None

            self._running = False
            logger.info("UDP log server stopped")

        except Exception as e:
            logger.error(f"Error stopping UDP log server: {e}")

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running
