# TermLogger User Guide

TermLogger is a terminal-based amateur radio logging application designed for fast, keyboard-driven operation. This guide covers all features and operating modes.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Main Screen Layout](#main-screen-layout)
3. [Logging QSOs](#logging-qsos)
4. [Operating Modes](#operating-modes)
5. [Callsign Lookup](#callsign-lookup)
6. [DX Spots](#dx-spots)
7. [ADIF Import/Export](#adif-importexport)
8. [Settings](#settings)
9. [Keyboard Reference](#keyboard-reference)

---

## Getting Started

### First Launch

When you first run TermLogger, you'll see the main logging screen with:
- QSO entry form at the top
- Callsign information display
- QSO log table on the left
- DX/POTA spots table on the right
- Status bar at the bottom

### Initial Configuration

Press **Ctrl+S** to open Settings and configure:

1. **Station Information**
   - Your callsign
   - Grid square
   - CQ/ITU zones
   - State/Province

2. **Callsign Lookup** (optional)
   - QRZ.com credentials (requires XML subscription)
   - HamQTH credentials (free)

3. **Spots Configuration**
   - POTA spots refresh interval
   - DX cluster settings

---

## Main Screen Layout

```
+------------------------------------------------------------------+
| TermLogger                                           UTC: 14:35  |
+------------------------------------------------------------------+
| Callsign: [W1ABC    ] Freq: [14.250    ] Mode: [SSB       ]      |
| Sent: [59    ] Rcvd: [59    ] UTC: [14:35 ] Date: [2025-12-26]   |
| Notes: [                                            ] [More...]  |
|                                           [Log QSO]              |
+------------------------------------------------------------------+
| Callsign Info: John Smith, Boston, MA                            |
+------------------------------------------------------------------+
| QSO Log (15)                    | DX Spots (50)                  |
| Time  Call    Freq   Mode RST   | Time  Call   Freq  Band Mode   |
| 14:32 K1ABC   14.250 SSB  59    | 14:30 DL1ABC 14.2  20m  SSB    |
| 14:28 W2XYZ   14.255 SSB  59    | 14:29 JA1XYZ 21.3  15m  CW     |
| ...                             | ...                             |
+------------------------------------------------------------------+
| Mode: General Logging | Ctrl+N for new mode                      |
+------------------------------------------------------------------+
```

---

## Logging QSOs

### Basic QSO Entry

1. Enter the **callsign** - automatically converts to uppercase
2. Enter the **frequency** in MHz (e.g., 14.250)
3. Select the **mode** from the dropdown
4. Adjust **RST sent/received** if needed (defaults to 59)
5. **Time and date** auto-fill with current UTC
6. Add optional **notes**
7. Press **Enter** or click **Log QSO**

### Extended Fields

Click **More...** to access additional ADIF fields:
- Name, QTH, State, Country
- Grid square
- Contest exchange
- POTA/SOTA references
- Power, Propagation mode
- Comments

### Dupe Checking

TermLogger automatically checks for duplicate contacts:
- **DUPE!** appears in red when a duplicate is detected
- Dupe checking considers band and mode

---

## Operating Modes

Press **Ctrl+N** to select an operating mode.

### General Logging

Standard everyday QSO logging with no special requirements.

### POTA Activation

For Parks on the Air activators:

1. Enter your **callsign**
2. Enter your **park reference** (e.g., K-1234)
3. Optionally add **additional parks** for 2-fer, 3-fer activations
4. Enter your **state** and **grid square**

**Status Display:**
```
POTA: K-1234 | QSOs: 8 (2 more needed) | P2P: 1
```

- Shows progress toward 10-contact activation requirement
- Tracks park-to-park (P2P) contacts
- Checkmark appears when activation is valid

### POTA Hunter

For hunting park activators from home:

1. Enter your **callsign**
2. Enter your **state** and **grid square**

**Status Display:**
```
POTA Hunter | QSOs: 12 | Parks: 5
```

- Tracks total QSOs and unique parks worked
- No activation requirement tracking
- Enter the activator's park reference in the exchange field

### Contest Mode

For contest operation:

1. Enter **contest name** and **ID**
2. Select **exchange format** (RST+Serial, RST+Zone, etc.)
3. Configure your **callsign** and **exchange**
4. Set **starting serial number**
5. Select **power level**

Features:
- Automatic serial number incrementing
- Score calculation
- Band/mode breakdown
- Cabrillo export

### ARRL Field Day

For Field Day operation:

1. Enter your **callsign** and **club name**
2. Select your **class** (1A, 2A, etc.)
3. Select your **ARRL section**
4. Configure **bonus points** checkboxes

Features:
- Automatic exchange formatting (class + section)
- Score calculation with bonuses
- Section multiplier tracking

---

## Callsign Lookup

### Automatic Lookup

When you tab out of the callsign field, TermLogger automatically looks up the callsign and displays:
- Name
- Location (city, state, country)
- Grid square
- License class

### Manual Lookup

Press **F5** to manually trigger a lookup for the current callsign.

### Configuring Lookup Services

In Settings (**Ctrl+S**), choose from:

| Service | Requirements |
|---------|--------------|
| QRZ.com | XML subscription required |
| HamQTH | Free account at hamqth.com |
| None | Disable lookup |

---

## DX Spots

The spots table shows real-time DX activity.

### Spot Sources

- **POTA Mode**: Shows POTA activator spots from pota.app
- **General Mode**: Shows DX cluster spots from HamQTH

### Filtering Spots

Click column headers to filter:

- **Band column**: Cycles through 160m, 80m, 40m, 30m, 20m, 17m, 15m, 12m, 10m, 6m, 2m, All
- **Mode column**: Cycles through CW, SSB, FT8, FT4, RTTY, FM, DIGITAL, All

Active filters are shown in bold in the column header.

### Selecting a Spot

Click on any spot row to:
- Auto-fill the frequency in the QSO entry form
- Auto-fill the mode if detected
- The callsign is NOT auto-filled (to prevent accidental overwrites)

### Refresh Rate

- POTA spots: Every 60 seconds (configurable)
- DX cluster: Every 30 seconds (configurable)

---

## ADIF Import/Export

### Importing ADIF

Press **F2** to import:

1. Select the ADIF file to import
2. QSOs are added to your log
3. Duplicates are skipped

### Exporting ADIF

Press **F3** to export:

1. Choose the save location
2. All QSOs are exported in ADIF 3.1 format

### POTA ADIF Export

In POTA mode, exports include:
- `MY_SIG=POTA`
- `MY_SIG_INFO=K-1234` (your park)
- `SIG=POTA` and `SIG_INFO` for P2P contacts

---

## Settings

Press **Ctrl+S** to open the Settings screen.

### Station Tab

- My Callsign
- Grid Square
- CQ Zone
- ITU Zone
- State/Province

### Lookup Tab

- Lookup Service (QRZ, HamQTH, None)
- Auto-lookup toggle
- QRZ username/password
- HamQTH username/password

### Spots Tab

- POTA spots enabled/disabled
- POTA refresh interval
- DX cluster enabled/disabled
- DX cluster refresh interval

---

## Keyboard Reference

### Global Keys

| Key | Action |
|-----|--------|
| Ctrl+Q | Quit application |
| Ctrl+S | Open settings |
| Ctrl+N | Start new operating mode |
| Ctrl+E | End current operating mode |
| Ctrl+L | Open log browser |
| F1 | Help |
| F2 | Import ADIF |
| F3 | Export ADIF |
| F5 | Lookup callsign |
| F10 | Exit |

### QSO Entry

| Key | Action |
|-----|--------|
| Tab | Next field |
| Shift+Tab | Previous field |
| Enter | Log QSO |
| Escape | Clear form |

### Tables

| Key | Action |
|-----|--------|
| Up/Down | Navigate rows |
| Enter | Select row |
| Click header | Cycle filter (spots table) |

---

## Tips and Tricks

### Fast Logging

1. Keep your hands on the keyboard
2. Use Tab to move between fields
3. Press Enter to log - the form clears and focus returns to callsign
4. RST defaults to 59 - only change when needed

### POTA Tips

- Click spots to quickly fill in frequency
- Watch the P2P count for bonus points
- Use the More... button to log their park reference

### Contest Tips

- Serial numbers auto-increment
- Score updates after each QSO
- Use the band/mode breakdown to track your coverage

---

## Troubleshooting

### Callsign Lookup Not Working

1. Check your credentials in Settings
2. Verify your subscription status (QRZ requires XML subscription)
3. Check your internet connection

### Spots Not Loading

1. Verify spots are enabled in Settings
2. Check your internet connection
3. Wait for the next refresh cycle

### QSOs Not Saving

1. Check disk space
2. Verify the database path in config
3. Check file permissions on `~/.config/termlogger/`

---

## Getting Help

- Press **F1** for quick help
- Report issues at: https://github.com/yourusername/TermLogger/issues
- Join the discussion on the project's GitHub page
