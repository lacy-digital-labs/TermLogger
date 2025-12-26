"""Tests for spot services."""

from datetime import datetime, timezone

import pytest

from termlogger.models import Spot, SpotSource


class TestSpotModel:
    """Tests for the Spot model."""

    def test_create_spot(self):
        """Test creating a basic spot."""
        spot = Spot(
            callsign="W1ABC",
            frequency=14.250,
            mode="SSB",
            spotter="K2XYZ",
            comment="CQ CQ CQ",
            source=SpotSource.DX_CLUSTER,
        )
        assert spot.callsign == "W1ABC"
        assert spot.frequency == 14.250
        assert spot.mode == "SSB"
        assert spot.spotter == "K2XYZ"
        assert spot.source == SpotSource.DX_CLUSTER

    def test_create_pota_spot(self):
        """Test creating a POTA spot."""
        spot = Spot(
            callsign="N3ABC",
            frequency=7.250,
            mode="SSB",
            spotter="POTA",
            comment="",
            source=SpotSource.POTA,
            park_reference="K-1234",
            park_name="Acadia National Park",
        )
        assert spot.source == SpotSource.POTA
        assert spot.park_reference == "K-1234"
        assert spot.park_name == "Acadia National Park"

    def test_spot_band_property(self):
        """Test the band property derivation from frequency."""
        spot_20m = Spot(callsign="W1ABC", frequency=14.250, source=SpotSource.DX_CLUSTER)
        assert spot_20m.band is not None
        assert spot_20m.band.value == "20m"

        spot_40m = Spot(callsign="W1ABC", frequency=7.150, source=SpotSource.DX_CLUSTER)
        assert spot_40m.band is not None
        assert spot_40m.band.value == "40m"

    def test_spot_time_str(self):
        """Test the time_str property."""
        spot = Spot(
            callsign="W1ABC",
            frequency=14.250,
            time=datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
            source=SpotSource.DX_CLUSTER,
        )
        assert spot.time_str == "14:30"

    def test_spot_info_str_pota(self):
        """Test info_str for POTA spots."""
        spot = Spot(
            callsign="W1ABC",
            frequency=14.250,
            source=SpotSource.POTA,
            park_reference="K-1234",
            park_name="Test Park",
        )
        assert "K-1234" in spot.info_str
        assert "Test Park" in spot.info_str

    def test_spot_info_str_dx(self):
        """Test info_str for DX cluster spots."""
        spot = Spot(
            callsign="W1ABC",
            frequency=14.250,
            source=SpotSource.DX_CLUSTER,
            comment="CQ Contest",
        )
        assert spot.info_str == "CQ Contest"


class TestPOTASpotService:
    """Tests for POTA spot service parsing."""

    def test_parse_pota_spot_data(self):
        """Test parsing POTA API response data."""
        from termlogger.services.pota_spots import POTASpotService

        service = POTASpotService()

        # Simulate API response data
        spot_data = {
            "activator": "W1ABC",
            "frequency": "14.250",
            "mode": "SSB",
            "reference": "K-1234",
            "parkName": "Test National Park",
            "spotTime": "2024-01-15T14:30:00Z",
            "spotter": "K2XYZ",
            "comments": "Great signals",
        }

        spot = service._parse_spot(spot_data)

        assert spot is not None
        assert spot.callsign == "W1ABC"
        assert spot.frequency == 14.250
        assert spot.mode == "SSB"
        assert spot.park_reference == "K-1234"
        assert spot.park_name == "Test National Park"
        assert spot.spotter == "K2XYZ"
        assert spot.source == SpotSource.POTA

    def test_parse_spot_invalid_frequency(self):
        """Test parsing spot with invalid frequency."""
        from termlogger.services.pota_spots import POTASpotService

        service = POTASpotService()

        spot_data = {
            "activator": "W1ABC",
            "frequency": "invalid",
            "mode": "SSB",
            "reference": "K-1234",
        }

        spot = service._parse_spot(spot_data)
        assert spot is None

    def test_parse_spot_zero_frequency(self):
        """Test parsing spot with zero frequency."""
        from termlogger.services.pota_spots import POTASpotService

        service = POTASpotService()

        spot_data = {
            "activator": "W1ABC",
            "frequency": "0",
            "mode": "SSB",
        }

        spot = service._parse_spot(spot_data)
        assert spot is None


class TestDXClusterService:
    """Tests for DX cluster service parsing."""

    def test_parse_dx_spot_line(self):
        """Test parsing a standard DX cluster spot line."""
        from termlogger.services.dx_cluster import DXClusterService

        service = DXClusterService()

        line = "DX de W1ABC:     14250.0  K2XYZ        CQ CQ CQ              1845Z"
        spot = service._parse_spot_line(line)

        assert spot is not None
        assert spot.spotter == "W1ABC"
        assert spot.callsign == "K2XYZ"
        assert abs(spot.frequency - 14.250) < 0.001  # kHz to MHz
        assert "CQ" in spot.comment
        assert spot.source == SpotSource.DX_CLUSTER

    def test_parse_dx_spot_with_mode(self):
        """Test parsing spot with mode in comment."""
        from termlogger.services.dx_cluster import DXClusterService

        service = DXClusterService()

        line = "DX de N3ABC:     7074.0  W5XYZ        FT8 -12dB             2030Z"
        spot = service._parse_spot_line(line)

        assert spot is not None
        assert spot.mode == "FT8"

    def test_parse_invalid_line(self):
        """Test parsing an invalid line returns None."""
        from termlogger.services.dx_cluster import DXClusterService

        service = DXClusterService()

        line = "This is not a spot line"
        spot = service._parse_spot_line(line)
        assert spot is None

    def test_extract_mode_from_comment(self):
        """Test mode extraction from various comments."""
        from termlogger.services.dx_cluster import DXClusterService

        service = DXClusterService()

        assert service._extract_mode("FT8 -12dB") == "FT8"
        assert service._extract_mode("CW up 2") == "CW"
        assert service._extract_mode("SSB contest") == "SSB"
        assert service._extract_mode("Working simplex") is None

    def test_parse_hamqth_web_response(self):
        """Test parsing HamQTH DX cluster web API response."""
        from termlogger.services.dx_cluster import DXClusterService

        service = DXClusterService()

        # Simulate HamQTH API response (caret-separated)
        response_text = """HB9DDS^7170.0^9K2KO^Nice Signal Mussalam.^2036 2025-12-26^^^AS^40M^Kuwait^348
ES2IPA^5357.0^SM2LKW^FT8^2035 2025-12-26^^^EU^60M^Sweden^284
AC3RA^7035.8^VE3RIA^^2035 2025-12-26^^^NA^40M^Canada^1"""

        spots = service._parse_web_response(response_text)

        assert len(spots) == 3

        # Check first spot
        assert spots[0].spotter == "HB9DDS"
        assert spots[0].callsign == "9K2KO"
        assert abs(spots[0].frequency - 7.170) < 0.001
        assert spots[0].comment == "Nice Signal Mussalam."

        # Check second spot with FT8 mode
        assert spots[1].callsign == "SM2LKW"
        assert spots[1].mode == "FT8"

        # Check third spot
        assert spots[2].callsign == "VE3RIA"
        assert spots[2].spotter == "AC3RA"
