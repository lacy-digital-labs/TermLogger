"""DX Cluster spots service with telnet and web API support."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from ..models import Spot, SpotSource

logger = logging.getLogger(__name__)


class DXClusterError(Exception):
    """Error with DX cluster connection or fetching."""

    pass


class DXClusterService:
    """Service for fetching DX cluster spots via telnet or web API."""

    # Default telnet cluster nodes
    DEFAULT_HOST = "dxc.nc7j.com"
    DEFAULT_PORT = 7373

    # Web API endpoint (HamQTH DX Cluster)
    WEB_API_URL = "https://www.hamqth.com/dxc_csv.php"

    # Regex to parse DX spot lines
    # Format: DX de W1ABC:     14250.0  K2XYZ        CQ CQ CQ              1845Z
    SPOT_PATTERN = re.compile(
        r"DX de\s+(\S+):\s*(\d+\.?\d*)\s+(\S+)\s*(.*?)\s+(\d{4})Z",
        re.IGNORECASE,
    )

    TIMEOUT = 10.0
    TELNET_TIMEOUT = 30.0

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        callsign: str = "",
    ) -> None:
        self.host = host
        self.port = port
        self.callsign = callsign
        self._http_client: Optional[httpx.AsyncClient] = None
        self._telnet_reader: Optional[asyncio.StreamReader] = None
        self._telnet_writer: Optional[asyncio.StreamWriter] = None
        self._spots_buffer: list[Spot] = []
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                headers={"User-Agent": "TermLogger/0.1.0"},
            )
        return self._http_client

    async def close(self) -> None:
        """Close all connections."""
        await self.disconnect_telnet()
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    # -------------------------------------------------------------------------
    # Telnet Methods
    # -------------------------------------------------------------------------

    async def connect_telnet(self) -> bool:
        """
        Connect to the DX cluster via telnet.

        Returns:
            True if connected successfully
        """
        if not self.callsign:
            raise DXClusterError("Callsign required for telnet connection")

        try:
            self._telnet_reader, self._telnet_writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.TELNET_TIMEOUT,
            )

            # Read initial prompt and send callsign
            await asyncio.sleep(0.5)
            initial = await self._read_until_prompt()
            logger.debug(f"Telnet initial: {initial}")

            # Send callsign to login
            self._telnet_writer.write(f"{self.callsign}\n".encode())
            await self._telnet_writer.drain()

            # Read login response
            await asyncio.sleep(0.5)
            response = await self._read_until_prompt()
            logger.debug(f"Telnet login response: {response}")

            self._connected = True

            # Start background task to receive spots
            self._receive_task = asyncio.create_task(self._receive_spots_loop())

            logger.info(f"Connected to DX cluster {self.host}:{self.port}")
            return True

        except asyncio.TimeoutError:
            raise DXClusterError(f"Timeout connecting to {self.host}:{self.port}")
        except Exception as e:
            raise DXClusterError(f"Failed to connect to DX cluster: {e}") from e

    async def disconnect_telnet(self) -> None:
        """Disconnect from the telnet cluster."""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._telnet_writer:
            try:
                self._telnet_writer.write(b"bye\n")
                await self._telnet_writer.drain()
                self._telnet_writer.close()
                await self._telnet_writer.wait_closed()
            except Exception:
                pass
            self._telnet_writer = None
            self._telnet_reader = None

        logger.info("Disconnected from DX cluster")

    async def _read_until_prompt(self) -> str:
        """Read from telnet until a prompt or timeout."""
        if not self._telnet_reader:
            return ""

        try:
            data = await asyncio.wait_for(
                self._telnet_reader.read(4096),
                timeout=5.0,
            )
            return data.decode("utf-8", errors="ignore")
        except asyncio.TimeoutError:
            return ""

    async def _receive_spots_loop(self) -> None:
        """Background loop to receive and parse spots."""
        while self._connected and self._telnet_reader:
            try:
                data = await asyncio.wait_for(
                    self._telnet_reader.readline(),
                    timeout=60.0,
                )
                line = data.decode("utf-8", errors="ignore").strip()

                if line:
                    spot = self._parse_spot_line(line)
                    if spot:
                        self._spots_buffer.append(spot)
                        # Keep buffer size reasonable
                        if len(self._spots_buffer) > 100:
                            self._spots_buffer = self._spots_buffer[-100:]

            except asyncio.TimeoutError:
                # Send a keepalive
                if self._telnet_writer:
                    try:
                        self._telnet_writer.write(b"\n")
                        await self._telnet_writer.drain()
                    except Exception:
                        break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error receiving spots: {e}")
                break

        self._connected = False

    def _parse_spot_line(self, line: str) -> Optional[Spot]:
        """Parse a DX spot line from telnet."""
        match = self.SPOT_PATTERN.search(line)
        if not match:
            return None

        try:
            spotter = match.group(1).upper().rstrip(":")
            freq_str = match.group(2)
            callsign = match.group(3).upper()
            comment = match.group(4).strip()
            time_str = match.group(5)

            # Parse frequency (could be in kHz or MHz)
            frequency = float(freq_str)
            if frequency > 1000:
                # Assume kHz, convert to MHz
                frequency = frequency / 1000

            # Parse time (HHMM format)
            now = datetime.now(timezone.utc)
            try:
                hour = int(time_str[:2])
                minute = int(time_str[2:])
                spot_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except (ValueError, IndexError):
                spot_time = now

            # Try to extract mode from comment
            mode = self._extract_mode(comment)

            return Spot(
                callsign=callsign,
                frequency=frequency,
                mode=mode,
                spotter=spotter,
                comment=comment,
                time=spot_time,
                source=SpotSource.DX_CLUSTER,
            )

        except Exception as e:
            logger.debug(f"Failed to parse spot line '{line}': {e}")
            return None

    def _extract_mode(self, comment: str) -> Optional[str]:
        """Try to extract operating mode from spot comment."""
        comment_upper = comment.upper()
        modes = ["FT8", "FT4", "CW", "SSB", "RTTY", "PSK", "JS8", "FM", "AM"]
        for mode in modes:
            if mode in comment_upper:
                return mode
        return None

    def get_telnet_spots(self, limit: int = 50) -> list[Spot]:
        """
        Get spots from the telnet buffer.

        Args:
            limit: Maximum number of spots to return

        Returns:
            List of recent spots (newest first)
        """
        # Return most recent spots first
        return list(reversed(self._spots_buffer[-limit:]))

    @property
    def is_connected(self) -> bool:
        """Check if telnet connection is active."""
        return self._connected

    # -------------------------------------------------------------------------
    # Web API Methods
    # -------------------------------------------------------------------------

    async def fetch_web_spots(
        self,
        limit: int = 50,
        band: Optional[str] = None,
    ) -> list[Spot]:
        """
        Fetch spots from HamQTH DX Cluster web API.

        Args:
            limit: Maximum number of spots to return
            band: Optional band filter (e.g., "20m")

        Returns:
            List of Spot objects
        """
        try:
            client = await self._get_http_client()

            params = {
                "limit": str(limit),
            }

            if band:
                # HamQTH uses band parameter directly
                params["band"] = band.lower().rstrip("m")  # e.g., "20" for 20m

            response = await client.get(self.WEB_API_URL, params=params)
            response.raise_for_status()

            # Parse the response
            spots = self._parse_web_response(response.text)
            return spots[:limit]

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching DX spots: {e}")
            raise DXClusterError(f"Failed to fetch DX spots: {e}") from e
        except Exception as e:
            logger.error(f"Error fetching DX spots: {e}")
            raise DXClusterError(f"Failed to fetch DX spots: {e}") from e

    def _parse_web_response(self, text: str) -> list[Spot]:
        """Parse the HamQTH DX Cluster CSV response."""
        spots = []

        # HamQTH returns caret-separated data
        # Format: spotter^frequency^callsign^comment^time^^^continent^band^country^?
        # Example: HB9DDS^7170.0^9K2KO^Nice Signal^2036 2025-12-26^^^AS^40M^Kuwait^348
        for line in text.strip().split("\n"):
            if not line:
                continue

            parts = line.split("^")
            if len(parts) < 5:
                continue

            try:
                spotter = parts[0].upper()
                freq_str = parts[1]
                callsign = parts[2].upper()
                comment = parts[3] if len(parts) > 3 else ""
                time_str = parts[4] if len(parts) > 4 else ""

                # Parse frequency (in kHz, convert to MHz)
                try:
                    frequency = float(freq_str) / 1000
                except ValueError:
                    continue

                # Parse time (format: "HHMM YYYY-MM-DD")
                try:
                    if " " in time_str:
                        time_part, date_part = time_str.split(" ", 1)
                        hour = int(time_part[:2])
                        minute = int(time_part[2:4]) if len(time_part) >= 4 else 0
                        year, month, day = map(int, date_part.split("-"))
                        spot_time = datetime(
                            year, month, day, hour, minute, tzinfo=timezone.utc
                        )
                    else:
                        spot_time = datetime.now(timezone.utc)
                except (ValueError, IndexError):
                    spot_time = datetime.now(timezone.utc)

                spots.append(
                    Spot(
                        callsign=callsign,
                        frequency=frequency,
                        mode=self._extract_mode(comment),
                        spotter=spotter,
                        comment=comment,
                        time=spot_time,
                        source=SpotSource.WEB_API,
                    )
                )

            except Exception as e:
                logger.debug(f"Failed to parse web spot: {e}")
                continue

        return spots

    # -------------------------------------------------------------------------
    # Combined Methods
    # -------------------------------------------------------------------------

    async def get_spots(
        self,
        limit: int = 50,
        use_telnet: bool = True,
        use_web: bool = True,
    ) -> list[Spot]:
        """
        Get spots from available sources.

        Args:
            limit: Maximum number of spots to return
            use_telnet: Include telnet spots if connected
            use_web: Fetch from web API if needed

        Returns:
            List of Spot objects (newest first)
        """
        spots = []

        # Get telnet spots if connected
        if use_telnet and self._connected:
            spots.extend(self.get_telnet_spots(limit))

        # Fetch from web API if enabled and we don't have enough spots
        if use_web and len(spots) < limit:
            try:
                web_spots = await self.fetch_web_spots(limit - len(spots))
                spots.extend(web_spots)
            except DXClusterError:
                pass  # Web API is optional fallback

        # Sort by time (newest first) and dedupe by callsign+frequency
        seen = set()
        unique_spots = []
        for spot in sorted(spots, key=lambda s: s.time, reverse=True):
            key = (spot.callsign, round(spot.frequency, 1))
            if key not in seen:
                seen.add(key)
                unique_spots.append(spot)

        return unique_spots[:limit]
