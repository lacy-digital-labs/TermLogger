"""Flex Radio SmartSDR API service for rig control."""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class FlexRadioError(Exception):
    """Error communicating with Flex Radio."""

    pass


class FlexRadioConnectionError(FlexRadioError):
    """Connection to Flex Radio failed or was lost."""

    pass


@dataclass
class SliceState:
    """State of a Flex Radio slice (virtual VFO)."""

    slice_id: int
    frequency: float  # Hz
    mode: str  # USB, LSB, CW, DIGU, DIGL, AM, FM, etc.
    active: bool = False
    tx: bool = False  # Is this the TX slice?

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


@dataclass
class FlexState:
    """Current Flex Radio state."""

    slices: dict[int, SliceState] = field(default_factory=dict)
    active_slice_id: Optional[int] = None

    @property
    def active_slice(self) -> Optional[SliceState]:
        """Get the currently active slice."""
        if self.active_slice_id is not None:
            return self.slices.get(self.active_slice_id)
        # Return first slice if no active slice set
        if self.slices:
            return next(iter(self.slices.values()))
        return None

    @property
    def frequency(self) -> float:
        """Get frequency of active slice in Hz."""
        slice_state = self.active_slice
        return slice_state.frequency if slice_state else 0.0

    @property
    def frequency_mhz(self) -> float:
        """Get frequency of active slice in MHz."""
        return self.frequency / 1_000_000

    @property
    def mode(self) -> str:
        """Get mode of active slice."""
        slice_state = self.active_slice
        return slice_state.mode if slice_state else "USB"

    @property
    def band(self) -> Optional[str]:
        """Get band of active slice."""
        slice_state = self.active_slice
        return slice_state.band if slice_state else None


class FlexRadioService:
    """Service for controlling Flex Radio via SmartSDR API.

    The SmartSDR API is a TCP-based protocol for controlling Flex Radio
    transceivers (Flex-6000 series and later).

    Usage:
        The radio must be running and accessible on the network.
        Default port is 4992.

    Protocol:
        Commands: "C<seq>|<command>\\n"
        Responses: "R<seq>|<status>|<data>\\n"
        Status updates: "S<handle>|<status_type> <data>\\n"
    """

    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 4992
    TIMEOUT = 5.0
    CONNECT_TIMEOUT = 10.0

    # SmartSDR mode names
    MODES = ["USB", "LSB", "CW", "DIGU", "DIGL", "AM", "SAM", "FM", "NFM", "DFM", "RTTY"]

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        on_state_change: Optional[Callable[[FlexState], None]] = None,
    ) -> None:
        """Initialize the Flex Radio service.

        Args:
            host: Radio hostname or IP address
            port: SmartSDR API port (default: 4992)
            on_state_change: Callback invoked when radio state changes
        """
        self.host = host
        self.port = port
        self.on_state_change = on_state_change

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._state = FlexState()
        self._last_state: Optional[FlexState] = None
        self._seq = 1
        self._lock = asyncio.Lock()
        self._receive_task: Optional[asyncio.Task] = None
        self._client_handle: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to radio."""
        return self._connected and self._writer is not None

    @property
    def last_state(self) -> Optional[FlexState]:
        """Get the last known radio state."""
        return self._last_state

    async def connect(self) -> bool:
        """Connect to Flex Radio.

        Returns:
            True if connected successfully

        Raises:
            FlexRadioConnectionError: If connection fails
        """
        if self._connected:
            return True

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.CONNECT_TIMEOUT,
            )
            self._connected = True
            logger.info(f"Connected to Flex Radio at {self.host}:{self.port}")

            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Subscribe to slice updates
            await self._subscribe()

            return True

        except asyncio.TimeoutError:
            raise FlexRadioConnectionError(
                f"Timeout connecting to Flex Radio at {self.host}:{self.port}"
            )
        except OSError as e:
            raise FlexRadioConnectionError(
                f"Failed to connect to Flex Radio at {self.host}:{self.port}: {e}"
            )

    async def disconnect(self) -> None:
        """Disconnect from radio."""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        logger.info("Disconnected from Flex Radio")

    async def close(self) -> None:
        """Close the service (alias for disconnect)."""
        await self.disconnect()

    async def _send_command(self, command: str) -> tuple[int, str]:
        """Send a command and return sequence number.

        Args:
            command: The SmartSDR command to send

        Returns:
            Tuple of (sequence_number, command_sent)

        Raises:
            FlexRadioError: If command fails
        """
        if not self._connected or not self._writer:
            raise FlexRadioConnectionError("Not connected to Flex Radio")

        async with self._lock:
            seq = self._seq
            self._seq += 1

            try:
                # Format: C<seq>|<command>\n
                cmd = f"C{seq}|{command}\n"
                self._writer.write(cmd.encode())
                await self._writer.drain()
                logger.debug(f"Sent: {cmd.strip()}")
                return seq, command

            except Exception as e:
                self._connected = False
                raise FlexRadioConnectionError(f"Failed to send command: {e}")

    async def _subscribe(self) -> None:
        """Subscribe to status updates."""
        try:
            # Subscribe to slice updates
            await self._send_command("sub slice all")
            # Subscribe to client updates (to get our handle)
            await self._send_command("sub client all")
            # Request current slice list to get initial state
            await self._send_command("slice list")
            logger.info("Subscribed to Flex Radio status updates")
        except FlexRadioError as e:
            logger.warning(f"Failed to subscribe: {e}")

    async def _receive_loop(self) -> None:
        """Background task to receive and process status updates."""
        while self._connected and self._reader:
            try:
                line = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=60.0,
                )
                if not line:
                    break

                message = line.decode().strip()
                if message:
                    self._process_message(message)

            except asyncio.TimeoutError:
                # Send keepalive
                if self._connected:
                    try:
                        await self._send_command("keepalive")
                    except FlexRadioError:
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break

        self._connected = False

    def _process_message(self, message: str) -> None:
        """Process a received message."""
        logger.debug(f"Flex RX: {message[:100]}")
        if message.startswith("S"):
            # Status update: S<handle>|<type> <data>
            self._process_status(message)
        elif message.startswith("R"):
            # Response: R<seq>|<status>|<data>
            self._process_response(message)
        elif message.startswith("V"):
            # Version info
            logger.info(f"Flex Radio version: {message}")
        elif message.startswith("H"):
            # Handle assignment: H<handle>
            match = re.match(r"H([0-9A-Fa-f]+)", message)
            if match:
                self._client_handle = match.group(1)
                logger.info(f"Assigned client handle: {self._client_handle}")

    def _process_response(self, message: str) -> None:
        """Process a command response."""
        # R<seq>|<status>|<data>
        parts = message[1:].split("|", 2)
        if len(parts) >= 2:
            seq = parts[0]
            status = parts[1]
            data = parts[2] if len(parts) > 2 else ""
            logger.debug(f"Response seq={seq} status={status} data={data[:100]}")

            # Parse slice list response - contains slice data
            if "slice" in data.lower():
                # Try to extract slice info from response
                self._process_slice_status(data)

    def _process_status(self, message: str) -> None:
        """Process a status update."""
        # S<handle>|<type> <data>
        parts = message[1:].split("|", 1)
        if len(parts) < 2:
            return

        _handle = parts[0]  # noqa: F841 - handle preserved for future use
        status_data = parts[1]

        # Parse status type and data
        space_idx = status_data.find(" ")
        if space_idx > 0:
            status_type = status_data[:space_idx]
            data = status_data[space_idx + 1 :]
        else:
            status_type = status_data
            data = ""

        if status_type == "slice":
            self._process_slice_status(data)

    def _process_slice_status(self, data: str) -> None:
        """Process slice status update."""
        # Parse key=value pairs
        props = {}
        for match in re.finditer(r'(\w+)=("[^"]*"|\S+)', data):
            key = match.group(1)
            value = match.group(2).strip('"')
            props[key] = value

        # Try multiple possible slice ID field names
        slice_id_str = props.get("index") or props.get("slice") or props.get("slice_id")
        if not slice_id_str:
            # Try to find a bare number at the start (e.g., "0 RF_frequency=14.250")
            match = re.match(r"^(\d+)\s", data)
            if match:
                slice_id_str = match.group(1)
            else:
                return

        try:
            slice_id = int(slice_id_str)
        except ValueError:
            return

        # Get or create slice state
        if slice_id not in self._state.slices:
            self._state.slices[slice_id] = SliceState(
                slice_id=slice_id,
                frequency=0.0,
                mode="USB",
            )
            logger.info(f"Created slice {slice_id}")

        slice_state = self._state.slices[slice_id]
        updated = False

        # Update properties - check multiple possible field names
        freq_str = props.get("RF_frequency") or props.get("freq") or props.get("frequency")
        if freq_str:
            try:
                # Frequency is in MHz in the API
                new_freq = float(freq_str) * 1_000_000
                if slice_state.frequency != new_freq:
                    slice_state.frequency = new_freq
                    updated = True
                    logger.info(f"Slice {slice_id} freq: {freq_str} MHz")
            except ValueError:
                pass

        if "mode" in props:
            new_mode = props["mode"].upper()
            if slice_state.mode != new_mode:
                slice_state.mode = new_mode
                updated = True
                logger.info(f"Slice {slice_id} mode: {new_mode}")

        if "active" in props:
            is_active = props["active"] == "1"
            slice_state.active = is_active
            if is_active:
                if self._state.active_slice_id != slice_id:
                    self._state.active_slice_id = slice_id
                    updated = True
                    logger.info(f"Slice {slice_id} is now active")

        if "tx" in props:
            slice_state.tx = props["tx"] == "1"

        # If this is the first slice and no active slice set, make it active
        if self._state.active_slice_id is None and self._state.slices:
            self._state.active_slice_id = slice_id
            updated = True
            logger.info(f"Set default active slice to {slice_id}")

        # Notify state change
        if updated:
            self._check_state_change()

    def _check_state_change(self) -> None:
        """Check if state changed and notify callback."""
        if self._last_state is None or (
            self._state.frequency != self._last_state.frequency
            or self._state.mode != self._last_state.mode
        ):
            # Create a copy of current state
            self._last_state = FlexState(
                slices={k: SliceState(**v.__dict__) for k, v in self._state.slices.items()},
                active_slice_id=self._state.active_slice_id,
            )
            if self.on_state_change:
                self.on_state_change(self._last_state)

    async def get_frequency(self) -> float:
        """Get current frequency of active slice.

        Returns:
            Frequency in Hz
        """
        if self._state.active_slice:
            return self._state.active_slice.frequency
        return 0.0

    async def set_frequency(self, freq_hz: float) -> None:
        """Set frequency of active slice.

        Args:
            freq_hz: Frequency in Hz
        """
        if not self._connected:
            try:
                await self.connect()
            except FlexRadioConnectionError as e:
                logger.error(f"Cannot set frequency - not connected: {e}")
                raise FlexRadioError(f"Not connected: {e}")

        slice_state = self._state.active_slice
        if slice_state is None:
            logger.error("No active slice to set frequency on")
            raise FlexRadioError("No active slice")

        # Frequency is in MHz in the API
        freq_mhz = freq_hz / 1_000_000
        logger.info(f"Setting slice {slice_state.slice_id} to {freq_mhz:.6f} MHz")
        await self._send_command(f"slice tune {slice_state.slice_id} {freq_mhz:.6f}")

    async def set_frequency_mhz(self, freq_mhz: float) -> None:
        """Set frequency of active slice in MHz.

        Args:
            freq_mhz: Frequency in MHz
        """
        await self.set_frequency(freq_mhz * 1_000_000)

    async def get_mode(self) -> tuple[str, int]:
        """Get current mode of active slice.

        Returns:
            Tuple of (mode_name, passband_hz)
        """
        slice_state = self._state.active_slice
        if slice_state:
            return slice_state.mode, 0
        return "USB", 0

    async def set_mode(self, mode: str, passband: int = 0) -> None:
        """Set mode of active slice.

        Args:
            mode: Mode name (USB, LSB, CW, DIGU, DIGL, AM, FM, etc.)
            passband: Passband width (ignored for Flex)
        """
        if not self._connected:
            try:
                await self.connect()
            except FlexRadioConnectionError as e:
                logger.error(f"Cannot set mode - not connected: {e}")
                raise FlexRadioError(f"Not connected: {e}")

        slice_state = self._state.active_slice
        if slice_state is None:
            logger.error("No active slice to set mode on")
            raise FlexRadioError("No active slice")

        logger.info(f"Setting slice {slice_state.slice_id} mode to {mode}")
        await self._send_command(f"slice set {slice_state.slice_id} mode={mode}")

    async def get_state(self) -> FlexState:
        """Get complete radio state.

        Returns:
            FlexState with current frequency and mode
        """
        return self._state

    async def poll(self) -> Optional[FlexState]:
        """Poll the radio state (for compatibility with rigctld interface).

        For Flex Radio, state updates are pushed automatically via the
        status subscription, so this just returns the current state.

        Returns:
            Current FlexState, or None if not connected
        """
        if not self._connected:
            try:
                await self.connect()
            except FlexRadioConnectionError as e:
                logger.warning(f"Flex Radio connection failed: {e}")
                return None

        # If we have valid state data, trigger callback
        if self._state.active_slice and self._state.frequency > 0:
            if self.on_state_change:
                self.on_state_change(self._state)

        return self._state

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
    def map_mode_to_flex(mode: str, freq_mhz: float = 14.0) -> str:
        """Map TermLogger mode to Flex Radio mode name.

        Args:
            mode: TermLogger mode (SSB, CW, FT8, etc.)
            freq_mhz: Frequency in MHz (for USB/LSB determination)

        Returns:
            Flex Radio mode name
        """
        mode_upper = mode.upper()
        mapping = {
            "SSB": FlexRadioService.get_ssb_mode(freq_mhz),
            "CW": "CW",
            "FM": "FM",
            "AM": "AM",
            "RTTY": "RTTY",
            "FT8": "DIGU",
            "FT4": "DIGU",
            "JS8": "DIGU",
            "PSK31": "DIGU",
            "DIGITAL": "DIGU",
            "SSTV": "USB",
        }
        return mapping.get(mode_upper, mode_upper)

    @staticmethod
    def map_mode_from_flex(mode: str) -> str:
        """Map Flex Radio mode name to TermLogger mode.

        Args:
            mode: Flex Radio mode name (USB, LSB, CW, DIGU, etc.)

        Returns:
            TermLogger mode name
        """
        mode_upper = mode.upper()
        mapping = {
            "USB": "SSB",
            "LSB": "SSB",
            "CW": "CW",
            "CWL": "CW",
            "CWU": "CW",
            "FM": "FM",
            "NFM": "FM",
            "DFM": "FM",
            "AM": "AM",
            "SAM": "AM",
            "RTTY": "RTTY",
            "DIGU": "FT8",  # Digital upper
            "DIGL": "FT8",  # Digital lower
        }
        return mapping.get(mode_upper, mode_upper)
