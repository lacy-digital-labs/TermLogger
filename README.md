# TermLogger

A terminal-based amateur radio logging application built with Python and Textual.

## Features

- Keyboard-driven QSO logging
- Real-time dupe checking
- ADIF import/export (coming soon)
- Callsign lookup via QRZ.com and HamQTH (coming soon)
- Contest mode with scoring (coming soon)

## Installation

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install TermLogger
pip install -e .
```

## Usage

```bash
termlogger
```

## Key Bindings

| Key | Action |
|-----|--------|
| Tab/Shift-Tab | Navigate fields |
| Enter | Log QSO |
| F1 | Help |
| F2 | Export ADIF |
| F3 | Clear form |
| F5 | Lookup callsign |
| F10 | Exit |
| Ctrl+Q | Quit |

## Configuration

Configuration is stored in `~/.config/termlogger/config.json`.

## License

MIT
