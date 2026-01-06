# TermLogger

A terminal-based amateur radio logging application built with Python and Textual.

## Features

- **Fast keyboard-driven QSO logging** - Optimized for rapid contest and everyday logging
- **Real-time dupe checking** - Instant duplicate contact detection
- **ADIF import/export** - Full ADIF 3.1 support for log interchange
- **ADIF log receive server** - Receive logs on UDP ADIF and WSJTX format
- **Callsign lookup** - QRZ.com and HamQTH integration
- **QRZ Logbook sync** - Upload and download QSOs to/from QRZ.com Logbook
- **Club Log upload** - Upload QSOs to Club Log
- **Real-time DX spots** - DX cluster spots via HamQTH web API
- **POTA spots** - Parks on the Air spot integration from pota.app
- **POTA park database** - Automatic park info lookup with name, location, and grid square
- **Rig control** - Hamlib (rigctld) and Flex Radio SmartSDR integration with auto-QSY

### Operating Modes

- **General Logging** - Standard everyday QSO logging
- **POTA Activation** - Parks on the Air activation mode with progress tracking
- **POTA Hunter** - Hunt park activators and track unique parks worked
- **Contest Mode** - Contest logging with serial numbers and scoring
- **ARRL Field Day** - Field Day with class/section exchange and bonus tracking

## Installation

### Recommended: pipx (isolated environment)

```bash
# Install pipx if you don't have it
pip install --user pipx
pipx ensurepath

# Install TermLogger
pipx install termlogger
```

### Alternative: pip

```bash
pip install termlogger
```

### From Source (for development)

```bash
git clone https://github.com/lacy-digital-labs/TermLogger.git
cd TermLogger
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Requirements

- Python 3.11 or later
- A terminal with Unicode support

## Usage

```bash
termlogger
```

## Key Bindings

| Key | Action |
|-----|--------|
| Tab / Shift-Tab | Navigate fields |
| Enter | Log QSO |
| F1 | Help |
| F2 | New mode / End mode (toggle) |
| F3 | Clear form |
| F5 | Lookup callsign |
| F6 | Log manager (export/import/archive) |
| F7 | Browse log |
| F9 | Settings |
| F10 | Exit |
| Ctrl+F | Manual tune (frequency/mode) |

### Spots Table

- Click on **Band** column header to cycle through band filters
- Click on **Mode** column header to cycle through mode filters
- Click on any spot row to auto-fill the QSO entry form
- POTA spots display park info (name, location, grid) when selected

## Configuration

Configuration is stored in `~/.config/termlogger/config.json`.

### Callsign Lookup

To enable callsign lookup, configure your credentials in Settings (F9):

- **QRZ.com** - Requires XML subscription
- **HamQTH** - Free registration at hamqth.com

### QRZ Logbook Sync

Sync your QSOs with QRZ.com Logbook:

1. Get your Logbook API key from qrz.com (requires subscription)
2. Enter API key in Settings (F9) → Lookup tab
3. Use Log Manager (F6) → QRZ Upload/Download buttons

Features:
- Upload only sends QSOs not previously uploaded
- Download skips duplicate QSOs automatically

### Club Log Upload

Upload your QSOs to Club Log:

1. Request an API key from Club Log helpdesk
2. Enter credentials in Settings (F9) → Lookup tab:
   - Email: Your Club Log account email
   - App Password: Application password (not your login password)
   - Callsign: Callsign for uploads
   - API Key: Your Club Log API key
3. Use Log Manager (F6) → Club Log button

### Spot Settings

- **POTA Spots** - Enabled by default, refreshes every 60 seconds
- **DX Cluster** - Enabled by default, uses HamQTH web API

### Rig Control

TermLogger supports automatic radio control through two backends:

**Hamlib (rigctld)**
```bash
# Start rigctld before running TermLogger
rigctld -m <model_number> -r <serial_port>

# Example for Icom IC-7300:
rigctld -m 3073 -r /dev/ttyUSB0

# Find your radio's model number:
rigctl -l | grep <radio_name>
```

**Flex Radio SmartSDR**
- Enter the Flex Radio's IP address in Settings
- Default port: 4992 (SmartSDR API)

Features:
- Band indicator shows current frequency/band from radio
- Frequency field updates from rig when focused
- Auto-QSY: clicking a spot changes the radio frequency

## Documentation

See the [User Guide](docs/USER_GUIDE.md) for detailed documentation.

## Version Numbering

TermLogger uses calendar-based versioning: `YY.MM.nn`

- `YY` - Two-digit year
- `MM` - Two-digit month
- `nn` - Release number within the month (01, 02, etc.)

Example: `25.12.01` is the first release in December 2025.

## License

MIT License - See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting pull requests.

All contributors must agree to the Developer Certificate of Origin (DCO) by signing off on their commits. See the contributing guide for details.
