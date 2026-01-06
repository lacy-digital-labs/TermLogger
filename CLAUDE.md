# TermLogger Development Notes

This file contains development context and roadmap for Claude Code sessions.

## Project Overview

TermLogger is a terminal-based amateur radio logging application built with Python and Textual TUI framework.

## Version Numbering

Calendar versioning: `YY.MM.nn` (e.g., 25.12.01 = first release December 2025)

## Current Version

26.01.02

## Feature Roadmap

### Log Upload Services
- [x] QRZ logbook upload and download
- [ ] LOTW (Logbook of The World) upload (stretch goal)

### Completed Features

#### POTA Enhancements
- [x] Download and cache parks database from pota.app API
- [x] Display park info when selecting POTA spots (name, type, location, grid)
- [x] POTA-formatted ADIF export with proper fields (Ctrl+P)
- [x] POTA filename convention (callsign@park-YYYYMMDD.adi)

#### Rig Control
- [x] rigctld integration (supports 200+ radios via Hamlib)
- [x] Flex Radio SmartSDR API integration
- [x] Read current frequency from radio → populate QSO form
- [x] Frequency updates on focus to frequency field
- [x] Click spot → change radio frequency (QSY)

## Recently Completed

### v25.12.01
- [x] Virtual logs for separate activations/events (F6 to manage)
- [x] Real-time DX spots from HamQTH web API
- [x] Real-time POTA spots from pota.app API
- [x] Band/mode filtering on spots table
- [x] POTA Hunter mode
- [x] Help screen (F1) and splash screen
- [x] Callsign lookup on field blur
- [x] Rig control via rigctld (200+ radio support)
- [x] Auto-QSY on spot click (configurable)

## Key Files

| File | Purpose |
|------|---------|
| `src/termlogger/app.py` | Main application entry point |
| `src/termlogger/database.py` | SQLite database operations |
| `src/termlogger/models.py` | Data models (QSO, Log, Spot, etc.) |
| `src/termlogger/screens/main.py` | Main logging screen |
| `src/termlogger/screens/log_manager.py` | Virtual log management |
| `src/termlogger/widgets/qso_entry.py` | QSO entry form |
| `src/termlogger/widgets/qso_table.py` | QSO display table |
| `src/termlogger/widgets/spots_table.py` | DX/POTA spots table |
| `src/termlogger/services/` | External API services |
| `src/termlogger/services/rigctld.py` | Rig control via rigctld |
| `src/termlogger/services/flexradio.py` | Rig control via Flex SmartSDR |
| `src/termlogger/services/pota_parks.py` | POTA parks lookup and caching |
| `src/termlogger/services/qrz_logbook.py` | QRZ Logbook API for upload/download |
| `src/termlogger/services/clublog.py` | Club Log API for upload |

## Key Bindings

| Key | Action |
|-----|--------|
| F1 | Help |
| F2 | New mode / End mode (toggle) |
| F3 | Clear form |
| F5 | Callsign lookup |
| F6 | Log manager (export/import/archive) |
| F7 | Browse log |
| F9 | Settings |
| F10 | Exit |
| Ctrl+E | Export ADIF (current mode) |
| Ctrl+I | Import ADIF |
| Ctrl+P | Export POTA log (current mode) |
| Ctrl+F | Manual tune (frequency/mode) |

## Database Schema

### Tables
- `qsos` - QSO records with `log_id` foreign key
- `logs` - Virtual logs for activations/events
- `contests` - Contest configurations
- `config` - Key-value configuration storage

## Implementation Notes

### Virtual Logs
- Each QSO can belong to a log (or none for general logging)
- Active log filters the QSO table display
- Logs can be archived (soft delete)
- Log types: general, pota_activation, pota_hunter, sota, contest, field_day, dx_expedition, special_event

### Spots
- DX spots from HamQTH web API (not telnet)
- POTA spots from pota.app API
- Spots refresh on configurable interval
- Click spot to auto-fill QSO form

### Rig Control
- Two backends: rigctld (Hamlib) and Flex Radio (SmartSDR)
- rigctld: localhost:4532, Flex: radio IP:4992
- Polls frequency/mode at configurable interval (0.1-5.0 seconds, default 0.5s)
- Auto-QSY on spot click (toggleable in settings)
- Frequency field updates from rig when focused
- Start rigctld: `rigctld -m <model> -r <device>`
- Find model: `rigctl -l | grep <radio_name>`
- Mode mapping: USB/LSB → SSB, CW/CWR → CW, PKTUSB/DIGU → FT8

### POTA Parks
- Parks cached in ~/.config/termlogger/pota_parks_cache.json
- API: https://api.pota.app/park/{reference}
- Cache expires after 7 days
- Displays park name, type, location, grid when spot selected

### QRZ Logbook
- API endpoint: https://logbook.qrz.com/api
- Requires QRZ Logbook API key (subscription required)
- API key configured in Settings → Lookup tab
- Upload: Sends QSOs via INSERT action, tracks qrz_logid for sync
- Download: Fetches all QSOs via FETCH action with automatic paging
- Duplicate detection on download by callsign + datetime + frequency
- Access via Log Manager (F6) → QRZ Upload/Download buttons

### Club Log
- API endpoints: realtime.php (single QSO), putlogs.php (batch)
- Requires: email, application password, callsign, API key
- API key must be requested from Club Log helpdesk
- Credentials configured in Settings → Lookup tab
- Upload only (no download API available)
- Uses batch upload for efficiency
- Access via Log Manager (F6) → Club Log button
