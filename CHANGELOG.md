# Changelog

All notable changes to TermLogger will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Calendar Versioning](https://calver.org/) with the format `YY.MM.nn`.

## [25.12.01] - 2025-12-26

### Added

- **Core Logging Features**
  - Keyboard-driven QSO entry form with auto-uppercase callsign
  - Real-time duplicate contact checking
  - UTC clock display
  - Band and frequency tracking

- **Operating Modes**
  - General Logging mode for everyday use
  - POTA Activation mode with 10-contact progress tracking
  - POTA Hunter mode for hunting park activators
  - Contest mode with serial numbers and scoring
  - ARRL Field Day mode with class/section exchange

- **Callsign Lookup**
  - QRZ.com XML API integration (requires subscription)
  - HamQTH lookup integration (free)
  - Automatic lookup on field blur
  - Manual lookup with F5

- **DX Spots**
  - Real-time POTA spots from pota.app API
  - DX cluster spots from HamQTH web API
  - Band and mode filtering via column header clicks
  - Click-to-fill frequency from spots

- **ADIF Support**
  - ADIF 3.1 import
  - ADIF 3.1 export
  - Extended fields support (name, QTH, grid, etc.)
  - POTA-specific fields (MY_SIG, SIG_INFO)

- **User Interface**
  - Split-pane layout with QSO log and spots tables
  - Settings screen with multiple tabs
  - Mode status display in footer
  - Log browser for reviewing past contacts

- **Documentation**
  - Comprehensive user guide
  - Release process documentation
  - Updated README with feature list

### Technical

- Built with Python 3.11+ and Textual TUI framework
- SQLite database for QSO storage
- Async HTTP clients for API calls
- Modular architecture with separate services for spots, lookup, etc.

---

## Version History

| Version | Date | Summary |
|---------|------|---------|
| 25.12.01 | 2025-12-26 | Initial release |
