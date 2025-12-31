"""Rigctld rig control service for Hamlib integration."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class RigctldError(Exception):
    """Error communicating with rigctld."""

    pass


class RigctldConnectionError(RigctldError):
    """Connection to rigctld failed or was lost."""

    pass


@dataclass
class RigState:
    """Current rig state."""

    frequency: float  # Hz
    mode: str  # USB, LSB, CW, etc.
    passband: int  # Passband width in Hz

    @property
    def frequency_mhz(self) -> float:
        """Get frequency in MHz."""
        return self.frequency / 1_000_000

    @property
    def band(self) -> Optional[str]:
        """Get band name from frequency."""
        from ..models import frequency_to_band

        band = frequency_to_band(self.frequency_mhz)
        return band.value if band else None


class RigctldService:
    """Service for controlling radio via rigctld.

    rigctld is Hamlib's rig control daemon that provides a simple TCP interface
    for controlling amateur radio transceivers. It supports 200+ radio models.

    Usage:
        Start rigctld before running TermLogger:
            rigctld -m <model_number> -r <serial_port>

        Example for Icom IC-7300:
            rigctld -m 3073 -r /dev/ttyUSB0

        Find your radio's model number with:
            rigctl -l | grep <radio_name>
    """

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 4532
    TIMEOUT = 2.0  # Command timeout in seconds
    CONNECT_TIMEOUT = 5.0

    # rigctld protocol commands
    CMD_GET_FREQ = "f"
    CMD_SET_FREQ = "F"
    CMD_GET_MODE = "m"
    CMD_SET_MODE = "M"

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        on_state_change: Optional[Callable[[RigState], None]] = None,
    ) -> None:
        """Initialize the rigctld service.

        Args:
            host: rigctld hostname (default: localhost)
            port: rigctld port (default: 4532)
            on_state_change: Callback invoked when frequency or mode changes
        """
        self.host = host
        self.port = port
        self.on_state_change = on_state_change

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._last_state: Optional[RigState] = None
        self._lock = asyncio.Lock()  # Serialize commands

    @property
    def is_connected(self) -> bool:
        """Check if connected to rigctld."""
        return self._connected and self._writer is not None

    @property
    def last_state(self) -> Optional[RigState]:
        """Get the last known rig state."""
        return self._last_state

    async def connect(self) -> bool:
        """Connect to rigctld.

        Returns:
            True if connected successfully

        Raises:
            RigctldConnectionError: If connection fails
        """
        if self._connected:
            return True

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.CONNECT_TIMEOUT,
            )
            self._connected = True
            logger.info(f"Connected to rigctld at {self.host}:{self.port}")
            return True

        except asyncio.TimeoutError:
            raise RigctldConnectionError(
                f"Timeout connecting to rigctld at {self.host}:{self.port}"
            )
        except OSError as e:
            raise RigctldConnectionError(
                f"Failed to connect to rigctld at {self.host}:{self.port}: {e}"
            )

    async def disconnect(self) -> None:
        """Disconnect from rigctld."""
        self._connected = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        logger.info("Disconnected from rigctld")

    async def close(self) -> None:
        """Close the service (alias for disconnect)."""
        await self.disconnect()

    async def _send_command(self, command: str) -> str:
        """Send a command and read response.

        Args:
            command: The rigctld command to send

        Returns:
            Response string from rigctld

        Raises:
            RigctldError: If command fails
        """
        if not self._connected or not self._writer or not self._reader:
            raise RigctldConnectionError("Not connected to rigctld")

        async with self._lock:
            try:
                # Send command with newline
                self._writer.write(f"{command}\n".encode())
                await self._writer.drain()

                # Read response
                response = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=self.TIMEOUT,
                )
                return response.decode().strip()

            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to '{command}'")
                raise RigctldError(f"Timeout waiting for response to '{command}'")
            except Exception as e:
                self._connected = False
                logger.error(f"Connection lost while executing '{command}': {e}")
                raise RigctldConnectionError(f"Connection lost: {e}")

    async def get_frequency(self) -> float:
        """Get current VFO frequency.

        Returns:
            Frequency in Hz
        """
        response = await self._send_command(self.CMD_GET_FREQ)
        try:
            # Check for stream desync - if we got a command response instead of frequency
            if response.startswith("RPRT"):
                logger.error(f"Stream desync detected in get_frequency: got '{response}' instead of frequency")
                self._connected = False
                raise RigctldConnectionError("Stream desynchronized - connection reset required")
            return float(response)
        except ValueError:
            # Non-numeric response suggests stream desync
            logger.error(f"Invalid frequency response: {response} - possible stream desync")
            self._connected = False
            raise RigctldError(f"Invalid frequency response: {response}")

    async def set_frequency(self, freq_hz: float) -> None:
        """Set VFO frequency.

        Args:
            freq_hz: Frequency in Hz
        """
        freq_int = int(freq_hz)
        response = await self._send_command(f"{self.CMD_SET_FREQ} {freq_int}")

        # Validate response - rigctld should return "RPRT N" where N is error code
        if not response:
            logger.error("Empty response from rigctld when setting frequency")
            raise RigctldError("Empty response from rigctld when setting frequency")

        if not response.startswith("RPRT"):
            logger.error(f"Unexpected response format from rigctld: {response}")
            raise RigctldError(f"Unexpected response format: {response}")

        # Parse error code
        try:
            code = int(response.split()[1])
        except (IndexError, ValueError):
            logger.error(f"Failed to parse RPRT code from response: {response}")
            raise RigctldError(f"Failed to parse response: {response}")

        if code != 0:
            logger.error(f"Rigctld returned error code {code} when setting frequency")
            raise RigctldError(f"Failed to set frequency: error {code}")

    async def set_frequency_mhz(self, freq_mhz: float) -> None:
        """Set VFO frequency in MHz.

        Args:
            freq_mhz: Frequency in MHz
        """
        await self.set_frequency(freq_mhz * 1_000_000)

    async def get_mode(self) -> tuple[str, int]:
        """Get current mode and passband.

        Returns:
            Tuple of (mode_name, passband_hz)
        """
        if not self._connected or not self._writer or not self._reader:
            raise RigctldConnectionError("Not connected to rigctld")

        # IMPORTANT: Must read both lines under the same lock to prevent interleaving
        async with self._lock:
            try:
                # Send command
                self._writer.write(f"{self.CMD_GET_MODE}\n".encode())
                await self._writer.drain()

                # Read first line (mode)
                mode_line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=self.TIMEOUT,
                )
                mode_str = mode_line.decode().strip()

                # Read second line (passband) - rigctld sends this on a separate line
                # CRITICAL: Must read this line with full timeout to prevent buffer desync
                # If we timeout here, the connection is broken and should be reset
                passband_line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=self.TIMEOUT,
                )
                passband_str = passband_line.decode().strip()

                # Parse passband value
                try:
                    passband = int(passband_str)
                except ValueError:
                    # Check if this looks like a mode string (stream desync)
                    # Valid passband is numeric, if we got letters it's likely a mode
                    if passband_str.isalpha() and len(passband_str) >= 2:
                        logger.error(f"Stream desync detected in get_mode: got '{passband_str}' instead of passband")
                        self._connected = False
                        raise RigctldConnectionError("Stream desynchronized - connection reset required")
                    # Otherwise just warn and use 0
                    logger.warning(f"Invalid passband value '{passband_str}', using 0")
                    passband = 0

                return mode_str, passband

            except asyncio.TimeoutError:
                logger.error(f"Timeout waiting for response to '{self.CMD_GET_MODE}'")
                raise RigctldError(f"Timeout waiting for response to '{self.CMD_GET_MODE}'")
            except Exception as e:
                self._connected = False
                logger.error(f"Connection lost while executing '{self.CMD_GET_MODE}': {e}")
                raise RigctldConnectionError(f"Connection lost: {e}")

    async def set_mode(self, mode: str, passband: int = -1) -> None:
        """Set operating mode.

        Args:
            mode: Mode name (USB, LSB, CW, AM, FM, etc.)
            passband: Passband width in Hz (-1 for no change, 0 for default)
        """
        response = await self._send_command(f"{self.CMD_SET_MODE} {mode} {passband}")

        # Validate response - rigctld should return "RPRT N" where N is error code
        if not response:
            logger.error("Empty response from rigctld when setting mode")
            raise RigctldError("Empty response from rigctld when setting mode")

        if not response.startswith("RPRT"):
            logger.error(f"Unexpected response format from rigctld: {response}")
            raise RigctldError(f"Unexpected response format: {response}")

        # Parse error code
        try:
            code = int(response.split()[1])
        except (IndexError, ValueError):
            logger.error(f"Failed to parse RPRT code from response: {response}")
            raise RigctldError(f"Failed to parse response: {response}")

        if code != 0:
            logger.error(f"Rigctld returned error code {code} when setting mode")
            raise RigctldError(f"Failed to set mode: error {code}")

    async def get_state(self) -> RigState:
        """Get complete rig state (frequency and mode).

        Returns:
            RigState with current frequency and mode
        """
        freq = await self.get_frequency()
        mode, passband = await self.get_mode()
        return RigState(frequency=freq, mode=mode, passband=passband)

    async def poll(self) -> Optional[RigState]:
        """Poll the rig state and emit change callback if changed.

        This method handles connection failures gracefully and will
        attempt to reconnect on the next poll if the connection is lost.

        Returns:
            Current RigState, or None if not connected
        """
        if not self._connected:
            try:
                await self.connect()
            except RigctldConnectionError:
                return None

        try:
            state = await self.get_state()

            # Check if state changed
            if self._last_state is None or (
                state.frequency != self._last_state.frequency
                or state.mode != self._last_state.mode
            ):
                self._last_state = state
                if self.on_state_change:
                    self.on_state_change(state)

            return state

        except RigctldError as e:
            logger.warning(f"Rigctld poll error: {e}")
            return None

    @staticmethod
    def get_ssb_mode(freq_mhz: float) -> str:
        """Determine USB or LSB based on frequency convention.

        Args:
            freq_mhz: Frequency in MHz

        Returns:
            'LSB' for frequencies below 10 MHz, 'USB' otherwise
        """
        return "LSB" if freq_mhz < 10.0 else "USB"

    @staticmethod
    def map_mode_to_rigctld(mode: str, freq_mhz: float = 14.0) -> str:
        """Map TermLogger mode to rigctld mode name.

        Args:
            mode: TermLogger mode (SSB, CW, FT8, etc.)
            freq_mhz: Frequency in MHz (for USB/LSB determination)

        Returns:
            rigctld mode name
        """
        mode_upper = mode.upper()
        mapping = {
            "SSB": RigctldService.get_ssb_mode(freq_mhz),
            "CW": "CW",
            "FM": "FM",
            "AM": "AM",
            "RTTY": "RTTY",
            "FT8": "PKTUSB",
            "FT4": "PKTUSB",
            "JS8": "PKTUSB",
            "PSK31": "PKTUSB",
            "DIGITAL": "PKTUSB",
            "SSTV": "USB",
        }
        return mapping.get(mode_upper, mode_upper)

    @staticmethod
    def map_mode_from_rigctld(mode: str) -> str:
        """Map rigctld mode name to TermLogger mode.

        Args:
            mode: rigctld mode name (USB, LSB, CW, etc.)

        Returns:
            TermLogger mode name
        """
        mode_upper = mode.upper()
        mapping = {
            "USB": "SSB",
            "LSB": "SSB",
            "CW": "CW",
            "CWR": "CW",
            "FM": "FM",
            "WFM": "FM",
            "AM": "AM",
            "RTTY": "RTTY",
            "RTTYR": "RTTY",
            "PKTUSB": "FT8",
            "PKTLSB": "FT8",
            "PKT": "DIGITAL",
        }
        return mapping.get(mode_upper, mode_upper)
