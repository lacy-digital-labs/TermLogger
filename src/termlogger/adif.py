"""ADIF (Amateur Data Interchange Format) import/export support.

ADIF is the standard format for exchanging amateur radio log data.
Format specification: https://adif.org/
"""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import Mode, QSO


# ADIF field name mappings
ADIF_FIELD_MAP = {
    "CALL": "callsign",
    "FREQ": "frequency",
    "MODE": "mode",
    "RST_SENT": "rst_sent",
    "RST_RCVD": "rst_received",
    "QSO_DATE": "date",
    "TIME_ON": "time",
    "COMMENT": "notes",
    "NOTES": "notes",
    "CONTEST_ID": "contest_id",
    "SRX": "exchange_received",
    "STX": "exchange_sent",
}

# Mode mappings from ADIF to our Mode enum
ADIF_MODE_MAP = {
    "SSB": Mode.SSB,
    "USB": Mode.SSB,
    "LSB": Mode.SSB,
    "CW": Mode.CW,
    "FM": Mode.FM,
    "AM": Mode.AM,
    "RTTY": Mode.RTTY,
    "PSK31": Mode.PSK31,
    "PSK": Mode.PSK31,
    "FT8": Mode.FT8,
    "FT4": Mode.FT4,
    "JS8": Mode.JS8,
    "SSTV": Mode.SSTV,
    "DIGI": Mode.DIGITAL,
    "DATA": Mode.DIGITAL,
    "MFSK": Mode.DIGITAL,
    "JT65": Mode.DIGITAL,
    "JT9": Mode.DIGITAL,
}


class ADIFParseError(Exception):
    """Error parsing ADIF data."""

    pass


def parse_adif_field(data: str, pos: int) -> tuple[Optional[tuple[str, str]], int]:
    """Parse a single ADIF field starting at position pos.

    Returns:
        Tuple of ((field_name, field_value), new_position) or (None, new_position)
    """
    # Skip whitespace
    while pos < len(data) and data[pos] in " \t\n\r":
        pos += 1

    if pos >= len(data):
        return None, pos

    # Look for field start
    if data[pos] != "<":
        # Skip non-field content
        while pos < len(data) and data[pos] != "<":
            pos += 1
        return None, pos

    # Find field end
    end_bracket = data.find(">", pos)
    if end_bracket == -1:
        return None, len(data)

    # Parse field header: <NAME:LENGTH> or <NAME:LENGTH:TYPE>
    field_header = data[pos + 1 : end_bracket]

    # Check for end of header or end of record
    if field_header.upper() in ("EOH", "EOR"):
        return (field_header.upper(), ""), end_bracket + 1

    # Parse field name and length
    parts = field_header.split(":")
    if len(parts) < 2:
        return None, end_bracket + 1

    field_name = parts[0].upper()
    try:
        field_length = int(parts[1])
    except ValueError:
        return None, end_bracket + 1

    # Extract field value
    value_start = end_bracket + 1
    value_end = value_start + field_length
    if value_end > len(data):
        value_end = len(data)

    field_value = data[value_start:value_end]

    return (field_name, field_value), value_end


def parse_adif(data: str) -> list[QSO]:
    """Parse ADIF data and return a list of QSO objects.

    Args:
        data: ADIF formatted string

    Returns:
        List of QSO objects

    Raises:
        ADIFParseError: If the data cannot be parsed
    """
    qsos = []
    pos = 0
    # Start assuming no header - if we see EOH, we know there was a header
    # Header-only fields that indicate we're in a header section
    header_fields = {"ADIF_VER", "PROGRAMID", "PROGRAMVERSION", "CREATED_TIMESTAMP"}
    in_header = False
    current_record: dict[str, str] = {}

    while pos < len(data):
        result, pos = parse_adif_field(data, pos)

        if result is None:
            continue

        field_name, field_value = result

        # Detect if we're in a header by seeing header-specific fields
        if field_name in header_fields:
            in_header = True
            continue

        if field_name == "EOH":
            # End of header - now in data section
            in_header = False
            continue

        if field_name == "EOR":
            # End of record - create QSO
            if current_record:
                try:
                    qso = _record_to_qso(current_record)
                    if qso:
                        qsos.append(qso)
                except Exception:
                    # Skip malformed records
                    pass
            current_record = {}
            continue

        # Only add to record if we're not in header
        if not in_header:
            current_record[field_name] = field_value

    return qsos


def _record_to_qso(record: dict[str, str]) -> Optional[QSO]:
    """Convert an ADIF record dictionary to a QSO object."""
    # Callsign is required
    callsign = record.get("CALL", "").strip().upper()
    if not callsign:
        return None

    # Parse frequency
    freq_str = record.get("FREQ", "14.0")
    try:
        frequency = float(freq_str)
    except ValueError:
        frequency = 14.0

    # Parse mode
    mode_str = record.get("MODE", "SSB").upper()
    mode = ADIF_MODE_MAP.get(mode_str, Mode.SSB)

    # Parse RST
    rst_sent = record.get("RST_SENT", "59")
    rst_received = record.get("RST_RCVD", "59")

    # Parse date and time
    date_str = record.get("QSO_DATE", "")
    time_str = record.get("TIME_ON", record.get("TIME_OFF", "0000"))

    # Normalize time string (could be HHMM or HHMMSS)
    time_str = time_str.ljust(6, "0")[:6]

    try:
        if date_str and len(date_str) >= 8:
            datetime_utc = datetime.strptime(
                f"{date_str[:8]}{time_str[:4]}", "%Y%m%d%H%M"
            )
        else:
            datetime_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    except ValueError:
        datetime_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    # Notes/comment
    notes = record.get("COMMENT", record.get("NOTES", ""))

    # Contest exchange
    exchange_sent = record.get("STX", record.get("STX_STRING", ""))
    exchange_received = record.get("SRX", record.get("SRX_STRING", ""))

    # Extended fields
    name = record.get("NAME", "")
    qth = record.get("QTH", "")
    state = record.get("STATE", "")
    country = record.get("COUNTRY", "")
    gridsquare = record.get("GRIDSQUARE", record.get("GRID", ""))

    # Parse numeric fields
    dxcc = None
    if "DXCC" in record:
        try:
            dxcc = int(record["DXCC"])
        except ValueError:
            pass

    cq_zone = None
    if "CQZ" in record:
        try:
            cq_zone = int(record["CQZ"])
        except ValueError:
            pass

    itu_zone = None
    if "ITUZ" in record:
        try:
            itu_zone = int(record["ITUZ"])
        except ValueError:
            pass

    tx_pwr = None
    if "TX_PWR" in record:
        try:
            tx_pwr = float(record["TX_PWR"])
        except ValueError:
            pass

    # Activity references
    pota_ref = record.get("POTA_REF", record.get("SIG_INFO", "") if record.get("SIG", "").upper() == "POTA" else "")
    sota_ref = record.get("SOTA_REF", record.get("SIG_INFO", "") if record.get("SIG", "").upper() == "SOTA" else "")
    iota = record.get("IOTA", "")
    sig = record.get("SIG", "")
    sig_info = record.get("SIG_INFO", "")

    # QSL fields
    qsl_sent = record.get("QSL_SENT", "")
    qsl_rcvd = record.get("QSL_RCVD", "")
    qsl_via = record.get("QSL_VIA", "")
    lotw_qsl_sent = record.get("LOTW_QSL_SENT", "")
    lotw_qsl_rcvd = record.get("LOTW_QSL_RCVD", "")

    # Propagation
    prop_mode = record.get("PROP_MODE", "")
    sat_name = record.get("SAT_NAME", "")

    # My station info
    my_gridsquare = record.get("MY_GRIDSQUARE", "")
    station_callsign = record.get("STATION_CALLSIGN", "")
    operator = record.get("OPERATOR", "")
    comment = record.get("COMMENT", record.get("NOTES", ""))

    return QSO(
        callsign=callsign,
        frequency=frequency,
        mode=mode,
        rst_sent=rst_sent,
        rst_received=rst_received,
        datetime_utc=datetime_utc,
        notes=notes,
        exchange_sent=exchange_sent if exchange_sent else None,
        exchange_received=exchange_received if exchange_received else None,
        # Extended fields
        name=name if name else None,
        qth=qth if qth else None,
        state=state if state else None,
        country=country if country else None,
        gridsquare=gridsquare if gridsquare else None,
        dxcc=dxcc,
        cq_zone=cq_zone,
        itu_zone=itu_zone,
        tx_pwr=tx_pwr,
        pota_ref=pota_ref if pota_ref else None,
        sota_ref=sota_ref if sota_ref else None,
        iota=iota if iota else None,
        sig=sig if sig else None,
        sig_info=sig_info if sig_info else None,
        qsl_sent=qsl_sent if qsl_sent else None,
        qsl_rcvd=qsl_rcvd if qsl_rcvd else None,
        qsl_via=qsl_via if qsl_via else None,
        lotw_qsl_sent=lotw_qsl_sent if lotw_qsl_sent else None,
        lotw_qsl_rcvd=lotw_qsl_rcvd if lotw_qsl_rcvd else None,
        prop_mode=prop_mode if prop_mode else None,
        sat_name=sat_name if sat_name else None,
        my_gridsquare=my_gridsquare if my_gridsquare else None,
        station_callsign=station_callsign if station_callsign else None,
        operator=operator if operator else None,
        comment=comment if comment else None,
    )


def parse_adif_file(filepath: str | Path) -> list[QSO]:
    """Parse an ADIF file and return a list of QSO objects.

    Args:
        filepath: Path to the ADIF file

    Returns:
        List of QSO objects

    Raises:
        FileNotFoundError: If the file doesn't exist
        ADIFParseError: If the file cannot be parsed
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"ADIF file not found: {filepath}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        data = f.read()

    return parse_adif(data)


def generate_adif_field(name: str, value: str) -> str:
    """Generate a single ADIF field.

    Args:
        name: Field name
        value: Field value

    Returns:
        Formatted ADIF field string
    """
    return f"<{name}:{len(value)}>{value}"


def generate_adif_header(
    program_name: str = "TermLogger",
    program_version: str = "0.1.0",
) -> str:
    """Generate an ADIF header.

    Args:
        program_name: Name of the program
        program_version: Version of the program

    Returns:
        ADIF header string
    """
    now = datetime.now(timezone.utc)
    lines = [
        "ADIF Export from TermLogger",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        generate_adif_field("ADIF_VER", "3.1.4"),
        generate_adif_field("PROGRAMID", program_name),
        generate_adif_field("PROGRAMVERSION", program_version),
        generate_adif_field("CREATED_TIMESTAMP", now.strftime("%Y%m%d %H%M%S")),
        "<EOH>",
        "",
    ]
    return "\n".join(lines)


def qso_to_adif(qso: QSO) -> str:
    """Convert a QSO to an ADIF record.

    Args:
        qso: QSO object to convert

    Returns:
        ADIF record string
    """
    fields = []

    # Required fields
    fields.append(generate_adif_field("CALL", qso.callsign.upper()))
    fields.append(generate_adif_field("FREQ", f"{qso.frequency:.6f}"))
    fields.append(generate_adif_field("MODE", qso.mode.value))

    # Band (derived from frequency)
    if qso.band:
        fields.append(generate_adif_field("BAND", qso.band.value))

    # RST
    fields.append(generate_adif_field("RST_SENT", qso.rst_sent))
    fields.append(generate_adif_field("RST_RCVD", qso.rst_received))

    # Date and time
    fields.append(generate_adif_field("QSO_DATE", qso.datetime_utc.strftime("%Y%m%d")))
    fields.append(generate_adif_field("TIME_ON", qso.datetime_utc.strftime("%H%M%S")))

    # Optional fields
    if qso.notes:
        fields.append(generate_adif_field("COMMENT", qso.notes))

    if qso.exchange_sent:
        fields.append(generate_adif_field("STX_STRING", qso.exchange_sent))

    if qso.exchange_received:
        fields.append(generate_adif_field("SRX_STRING", qso.exchange_received))

    # Extended fields - Station info
    if qso.name:
        fields.append(generate_adif_field("NAME", qso.name))
    if qso.qth:
        fields.append(generate_adif_field("QTH", qso.qth))
    if qso.state:
        fields.append(generate_adif_field("STATE", qso.state))
    if qso.country:
        fields.append(generate_adif_field("COUNTRY", qso.country))
    if qso.gridsquare:
        fields.append(generate_adif_field("GRIDSQUARE", qso.gridsquare))
    if qso.dxcc:
        fields.append(generate_adif_field("DXCC", str(qso.dxcc)))
    if qso.cq_zone:
        fields.append(generate_adif_field("CQZ", str(qso.cq_zone)))
    if qso.itu_zone:
        fields.append(generate_adif_field("ITUZ", str(qso.itu_zone)))
    if qso.continent:
        fields.append(generate_adif_field("CONT", qso.continent))

    # Power
    if qso.tx_pwr:
        fields.append(generate_adif_field("TX_PWR", str(qso.tx_pwr)))

    # Activity references
    if qso.pota_ref:
        fields.append(generate_adif_field("POTA_REF", qso.pota_ref))
    if qso.sota_ref:
        fields.append(generate_adif_field("SOTA_REF", qso.sota_ref))
    if qso.wwff_ref:
        fields.append(generate_adif_field("WWFF_REF", qso.wwff_ref))
    if qso.iota:
        fields.append(generate_adif_field("IOTA", qso.iota))
    if qso.sig:
        fields.append(generate_adif_field("SIG", qso.sig))
    if qso.sig_info:
        fields.append(generate_adif_field("SIG_INFO", qso.sig_info))

    # QSL fields
    if qso.qsl_sent:
        fields.append(generate_adif_field("QSL_SENT", qso.qsl_sent))
    if qso.qsl_rcvd:
        fields.append(generate_adif_field("QSL_RCVD", qso.qsl_rcvd))
    if qso.qsl_via:
        fields.append(generate_adif_field("QSL_VIA", qso.qsl_via))
    if qso.lotw_qsl_sent:
        fields.append(generate_adif_field("LOTW_QSL_SENT", qso.lotw_qsl_sent))
    if qso.lotw_qsl_rcvd:
        fields.append(generate_adif_field("LOTW_QSL_RCVD", qso.lotw_qsl_rcvd))
    if qso.eqsl_qsl_sent:
        fields.append(generate_adif_field("EQSL_QSL_SENT", qso.eqsl_qsl_sent))
    if qso.eqsl_qsl_rcvd:
        fields.append(generate_adif_field("EQSL_QSL_RCVD", qso.eqsl_qsl_rcvd))

    # Propagation
    if qso.prop_mode:
        fields.append(generate_adif_field("PROP_MODE", qso.prop_mode))
    if qso.sat_name:
        fields.append(generate_adif_field("SAT_NAME", qso.sat_name))
    if qso.sat_mode:
        fields.append(generate_adif_field("SAT_MODE", qso.sat_mode))

    # My station info
    if qso.station_callsign:
        fields.append(generate_adif_field("STATION_CALLSIGN", qso.station_callsign))
    if qso.operator:
        fields.append(generate_adif_field("OPERATOR", qso.operator))
    if qso.my_gridsquare:
        fields.append(generate_adif_field("MY_GRIDSQUARE", qso.my_gridsquare))
    if qso.my_pota_ref:
        fields.append(generate_adif_field("MY_POTA_REF", qso.my_pota_ref))
    if qso.my_sota_ref:
        fields.append(generate_adif_field("MY_SOTA_REF", qso.my_sota_ref))

    # End of record
    fields.append("<EOR>")

    return " ".join(fields)


def generate_adif(qsos: list[QSO], include_header: bool = True) -> str:
    """Generate ADIF data from a list of QSOs.

    Args:
        qsos: List of QSO objects
        include_header: Whether to include the ADIF header

    Returns:
        ADIF formatted string
    """
    lines = []

    if include_header:
        lines.append(generate_adif_header())

    for qso in qsos:
        lines.append(qso_to_adif(qso))
        lines.append("")  # Empty line between records for readability

    return "\n".join(lines)


def export_adif_file(
    qsos: list[QSO],
    filepath: str | Path,
    include_header: bool = True,
) -> int:
    """Export QSOs to an ADIF file.

    Args:
        qsos: List of QSO objects to export
        filepath: Path to the output file
        include_header: Whether to include the ADIF header

    Returns:
        Number of QSOs exported

    Raises:
        IOError: If the file cannot be written
    """
    path = Path(filepath)

    # Ensure .adi extension
    if path.suffix.lower() not in (".adi", ".adif"):
        path = path.with_suffix(".adi")

    adif_data = generate_adif(qsos, include_header)

    with open(path, "w", encoding="utf-8") as f:
        f.write(adif_data)

    return len(qsos)
