# TermLogger

A terminal-based amateur radio logging application built with Python and Textual.

## Features

- **Fast keyboard-driven QSO logging** - Optimized for rapid contest and everyday logging
- **Real-time dupe checking** - Instant duplicate contact detection
- **ADIF import/export** - Full ADIF 3.1 support for log interchange
- **Callsign lookup** - QRZ.com and HamQTH integration
- **Real-time DX spots** - DX cluster spots via HamQTH web API
- **POTA spots** - Parks on the Air spot integration from pota.app

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
| F2 | Import ADIF |
| F3 | Export ADIF |
| F5 | Lookup callsign |
| F10 | Exit |
| Ctrl+N | Start new operating mode |
| Ctrl+E | End current mode |
| Ctrl+S | Settings |
| Ctrl+L | Log browser |
| Ctrl+Q | Quit |

### Spots Table

- Click on **Band** column header to cycle through band filters
- Click on **Mode** column header to cycle through mode filters
- Click on any spot row to auto-fill the QSO entry form

## Configuration

Configuration is stored in `~/.config/termlogger/config.json`.

### Callsign Lookup

To enable callsign lookup, configure your credentials in Settings (Ctrl+S):

- **QRZ.com** - Requires XML subscription
- **HamQTH** - Free registration at hamqth.com

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

MIT

## Contributing

Contributions are welcome! Please see [RELEASING.md](docs/RELEASING.md) for release procedures.
