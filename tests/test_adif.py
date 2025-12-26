"""Tests for ADIF import/export functionality."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from termlogger.adif import (
    export_adif_file,
    generate_adif,
    parse_adif,
    parse_adif_file,
    qso_to_adif,
)
from termlogger.models import Mode, QSO


class TestADIFParser:
    """Tests for ADIF parsing."""

    def test_parse_simple_record(self):
        """Test parsing a simple ADIF record."""
        adif = """
        <CALL:5>W1ABC <FREQ:6>14.250 <MODE:3>SSB <RST_SENT:2>59 <RST_RCVD:2>59
        <QSO_DATE:8>20251225 <TIME_ON:4>1430 <EOR>
        """
        qsos = parse_adif(adif)
        assert len(qsos) == 1
        assert qsos[0].callsign == "W1ABC"
        assert qsos[0].frequency == 14.250
        assert qsos[0].mode == Mode.SSB
        assert qsos[0].rst_sent == "59"
        assert qsos[0].rst_received == "59"

    def test_parse_multiple_records(self):
        """Test parsing multiple ADIF records."""
        adif = """
        <CALL:5>W1ABC <FREQ:6>14.250 <MODE:3>SSB <EOR>
        <CALL:6>VE3XYZ <FREQ:5>7.150 <MODE:2>CW <EOR>
        <CALL:5>K2DEF <FREQ:6>21.300 <MODE:3>FT8 <EOR>
        """
        qsos = parse_adif(adif)
        assert len(qsos) == 3
        assert qsos[0].callsign == "W1ABC"
        assert qsos[1].callsign == "VE3XYZ"
        assert qsos[2].callsign == "K2DEF"
        assert qsos[2].mode == Mode.FT8

    def test_parse_with_header(self):
        """Test parsing ADIF with header."""
        adif = """
        ADIF Export
        <ADIF_VER:5>3.1.4
        <PROGRAMID:9>TestProg
        <EOH>

        <CALL:5>W1ABC <FREQ:6>14.250 <MODE:3>SSB <EOR>
        """
        qsos = parse_adif(adif)
        assert len(qsos) == 1
        assert qsos[0].callsign == "W1ABC"

    def test_parse_with_comments(self):
        """Test parsing ADIF with comments."""
        adif = """
        <CALL:5>W1ABC <FREQ:6>14.250 <MODE:3>SSB <COMMENT:10>Test notes <EOR>
        """
        qsos = parse_adif(adif)
        assert len(qsos) == 1
        assert qsos[0].notes == "Test notes"

    def test_parse_mode_variants(self):
        """Test parsing various mode representations."""
        test_cases = [
            ("USB", Mode.SSB),
            ("LSB", Mode.SSB),
            ("CW", Mode.CW),
            ("FT8", Mode.FT8),
            ("FT4", Mode.FT4),
            ("RTTY", Mode.RTTY),
        ]
        for adif_mode, expected_mode in test_cases:
            adif = f"<CALL:4>TEST <FREQ:2>14 <MODE:{len(adif_mode)}>{adif_mode} <EOR>"
            qsos = parse_adif(adif)
            assert qsos[0].mode == expected_mode, f"Failed for mode {adif_mode}"

    def test_parse_empty_returns_empty(self):
        """Test parsing empty data."""
        qsos = parse_adif("")
        assert len(qsos) == 0

    def test_parse_no_records_returns_empty(self):
        """Test parsing data with no valid records."""
        adif = "<EOH> No actual records here"
        qsos = parse_adif(adif)
        assert len(qsos) == 0


class TestADIFGenerator:
    """Tests for ADIF generation."""

    def test_generate_single_qso(self):
        """Test generating ADIF for a single QSO."""
        qso = QSO(
            callsign="W1ABC",
            frequency=14.250,
            mode=Mode.SSB,
            rst_sent="59",
            rst_received="59",
            datetime_utc=datetime(2025, 12, 25, 14, 30),
            notes="Test QSO",
        )
        adif = qso_to_adif(qso)
        assert "<CALL:5>W1ABC" in adif
        assert "<MODE:3>SSB" in adif
        assert "<QSO_DATE:8>20251225" in adif
        assert "<TIME_ON:6>143000" in adif
        assert "<COMMENT:8>Test QSO" in adif
        assert "<EOR>" in adif

    def test_generate_multiple_qsos(self):
        """Test generating ADIF for multiple QSOs."""
        qsos = [
            QSO(
                callsign="W1ABC",
                frequency=14.250,
                mode=Mode.SSB,
                datetime_utc=datetime(2025, 12, 25, 14, 30),
            ),
            QSO(
                callsign="K2DEF",
                frequency=7.150,
                mode=Mode.CW,
                datetime_utc=datetime(2025, 12, 25, 15, 00),
            ),
        ]
        adif = generate_adif(qsos)
        assert "<CALL:5>W1ABC" in adif
        assert "<CALL:5>K2DEF" in adif
        assert adif.count("<EOR>") == 2

    def test_generate_includes_header(self):
        """Test that generated ADIF includes header by default."""
        qsos = [
            QSO(
                callsign="W1ABC",
                frequency=14.250,
                mode=Mode.SSB,
                datetime_utc=datetime(2025, 12, 25, 14, 30),
            )
        ]
        adif = generate_adif(qsos, include_header=True)
        assert "<ADIF_VER:" in adif
        assert "<PROGRAMID:" in adif
        assert "<EOH>" in adif

    def test_generate_without_header(self):
        """Test generating ADIF without header."""
        qsos = [
            QSO(
                callsign="W1ABC",
                frequency=14.250,
                mode=Mode.SSB,
                datetime_utc=datetime(2025, 12, 25, 14, 30),
            )
        ]
        adif = generate_adif(qsos, include_header=False)
        assert "<EOH>" not in adif


class TestADIFRoundTrip:
    """Tests for ADIF round-trip (export then import)."""

    def test_roundtrip_preserves_data(self):
        """Test that export then import preserves QSO data."""
        original_qsos = [
            QSO(
                callsign="W1ABC",
                frequency=14.250,
                mode=Mode.SSB,
                rst_sent="59",
                rst_received="57",
                datetime_utc=datetime(2025, 12, 25, 14, 30),
                notes="Round trip test",
            ),
            QSO(
                callsign="VE3XYZ",
                frequency=7.150,
                mode=Mode.CW,
                rst_sent="599",
                rst_received="579",
                datetime_utc=datetime(2025, 12, 25, 15, 0),
            ),
        ]

        # Export to ADIF
        adif = generate_adif(original_qsos)

        # Parse it back
        imported_qsos = parse_adif(adif)

        assert len(imported_qsos) == len(original_qsos)

        for orig, imported in zip(original_qsos, imported_qsos):
            assert imported.callsign == orig.callsign
            assert imported.frequency == orig.frequency
            assert imported.mode == orig.mode
            assert imported.rst_sent == orig.rst_sent
            assert imported.rst_received == orig.rst_received
            assert imported.datetime_utc.date() == orig.datetime_utc.date()
            assert imported.notes == orig.notes


class TestADIFFileOperations:
    """Tests for ADIF file operations."""

    def test_export_and_import_file(self):
        """Test exporting and importing from file."""
        qsos = [
            QSO(
                callsign="W1ABC",
                frequency=14.250,
                mode=Mode.SSB,
                datetime_utc=datetime(2025, 12, 25, 14, 30),
            )
        ]

        with tempfile.NamedTemporaryFile(suffix=".adi", delete=False) as f:
            filepath = Path(f.name)

        try:
            # Export
            count = export_adif_file(qsos, filepath)
            assert count == 1
            assert filepath.exists()

            # Import
            imported = parse_adif_file(filepath)
            assert len(imported) == 1
            assert imported[0].callsign == "W1ABC"
        finally:
            filepath.unlink(missing_ok=True)

    def test_import_nonexistent_file_raises(self):
        """Test that importing non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            parse_adif_file("/nonexistent/file.adi")
