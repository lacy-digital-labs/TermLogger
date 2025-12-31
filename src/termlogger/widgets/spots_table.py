"""Spots table widget for displaying DX cluster and POTA spots."""

from typing import Optional

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import DataTable, Static

from ..models import Spot, format_frequency


# Common modes to filter by (in cycle order)
FILTER_MODES = ["All", "CW", "SSB", "FT8", "FT4", "RTTY", "FM", "DIGITAL"]

# Bands to filter by (in cycle order)
FILTER_BANDS = ["All", "160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m", "2m"]


class SpotsTable(Static):
    """Widget for displaying spots in a table."""

    DEFAULT_CSS = """
    SpotsTable {
        height: 100%;
        width: 100%;
        border: solid $accent;
    }

    SpotsTable DataTable {
        height: 1fr;
        width: 100%;
    }

    SpotsTable .spots-header {
        height: 1;
        background: $accent;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    SpotsTable .filter-status {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
        text-align: center;
    }
    """

    class SpotSelected(Message):
        """Message sent when a spot is selected/clicked."""

        def __init__(self, spot: Spot) -> None:
            self.spot = spot
            super().__init__()

    # Column definitions: (name, width, column_key)
    # Band and Mode columns are clickable for filtering
    COLUMNS = [
        ("Time", 5, "time"),
        ("Call", 10, "call"),
        ("Freq", 8, "freq"),
        ("Band", 5, "band"),
        ("Mode", 5, "mode"),
        ("Info", None, "info"),  # None = auto-expand to fill remaining space
        ("By", 8, "by"),
    ]

    def __init__(
        self,
        id: Optional[str] = None,
        title: str = "Spots",
    ) -> None:
        super().__init__(id=id)
        self._spots: list[Spot] = []
        self._filtered_spots: list[Spot] = []
        self._title = title
        self._band_filter: str = "All"
        self._mode_filter: str = "All"

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(f"[bold]{self._title}[/bold]", classes="spots-header", id="spots-title")
        yield DataTable(id="spots-data-table", cursor_type="row")
        yield Static("", id="filter-status", classes="filter-status")

    def on_mount(self) -> None:
        """Initialize the table."""
        table = self.query_one(DataTable)

        # Add columns with keys
        for name, width, key in self.COLUMNS:
            table.add_column(name, width=width, key=key)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle header click - cycle through filter options."""
        column_key = str(event.column_key)

        if column_key == "band":
            self._cycle_band_filter()
        elif column_key == "mode":
            self._cycle_mode_filter()

    def _cycle_band_filter(self) -> None:
        """Cycle to next band filter."""
        current_idx = FILTER_BANDS.index(self._band_filter) if self._band_filter in FILTER_BANDS else 0
        next_idx = (current_idx + 1) % len(FILTER_BANDS)
        self._band_filter = FILTER_BANDS[next_idx]
        self._apply_filters()

    def _cycle_mode_filter(self) -> None:
        """Cycle to next mode filter."""
        current_idx = FILTER_MODES.index(self._mode_filter) if self._mode_filter in FILTER_MODES else 0
        next_idx = (current_idx + 1) % len(FILTER_MODES)
        self._mode_filter = FILTER_MODES[next_idx]
        self._apply_filters()

    def _update_status_bar(self) -> None:
        """Update the status bar with filter info and keyboard hints."""
        try:
            status = self.query_one("#filter-status", Static)

            if self._band_filter == "All" and self._mode_filter == "All":
                status.update("[dim]B: Band | M: Mode | C: Clear filters[/dim]")
            else:
                filters = []
                if self._band_filter != "All":
                    filters.append(f"Band={self._band_filter}")
                if self._mode_filter != "All":
                    filters.append(f"Mode={self._mode_filter}")
                filter_str = " ".join(filters)
                status.update(f"[yellow]{filter_str}[/yellow] [dim]| B: Next Band | M: Next Mode | C: Clear[/dim]")
        except Exception:
            pass

    def _update_header(self) -> None:
        """Update the header with title and filter info."""
        try:
            header = self.query_one(".spots-header", Static)
            total = len(self._spots)
            filtered = len(self._filtered_spots)

            if self._band_filter == "All" and self._mode_filter == "All":
                header.update(f"[bold]{self._title}[/bold] [dim]({total})[/dim]")
            else:
                filters = []
                if self._band_filter != "All":
                    filters.append(self._band_filter)
                if self._mode_filter != "All":
                    filters.append(self._mode_filter)
                filter_str = "+".join(filters)
                header.update(f"[bold]{self._title}[/bold] [dim]({filtered}/{total} {filter_str})[/dim]")
        except Exception:
            pass

    def _apply_filters(self) -> None:
        """Apply current filters and refresh the table."""
        self._filtered_spots = []

        for spot in self._spots:
            # Apply band filter
            if self._band_filter != "All":
                if spot.band is None or spot.band.value != self._band_filter:
                    continue

            # Apply mode filter
            if self._mode_filter != "All":
                if spot.mode is None or spot.mode.upper() != self._mode_filter.upper():
                    continue

            self._filtered_spots.append(spot)

        # Sort by frequency (ascending)
        self._filtered_spots.sort(key=lambda s: s.frequency)

        self._refresh_table()
        self._update_header()
        self._update_status_bar()

    def load_spots(self, spots: list[Spot]) -> None:
        """Load spots into the table."""
        self._spots = spots
        self._apply_filters()

    def add_spot(self, spot: Spot) -> None:
        """Add a new spot to the top of the table."""
        self._spots.insert(0, spot)
        # Keep table size reasonable
        if len(self._spots) > 100:
            self._spots = self._spots[:100]
        self._apply_filters()

    def clear_spots(self) -> None:
        """Clear all spots from the table."""
        self._spots = []
        self._filtered_spots = []
        self._refresh_table()
        self._update_header()
        self._update_status_bar()

    def _refresh_table(self) -> None:
        """Refresh the table display."""
        table = self.query_one(DataTable)
        table.clear()

        for i, spot in enumerate(self._filtered_spots):
            # Format frequency
            freq_str = format_frequency(spot.frequency)

            # Get band
            band_str = spot.band.value if spot.band else "-"

            # Get mode or dash
            mode_str = spot.mode or "-"

            # Get info string (park ref for POTA, comment for DX)
            info_str = spot.info_str

            table.add_row(
                spot.time_str,
                spot.callsign[:10],
                freq_str,
                band_str,
                mode_str[:5],
                info_str,
                spot.spotter[:8],
                key=str(i),
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        try:
            row_index = int(str(event.row_key.value))
            if 0 <= row_index < len(self._filtered_spots):
                spot = self._filtered_spots[row_index]
                self.post_message(self.SpotSelected(spot))
        except (ValueError, IndexError):
            pass

    def get_selected_spot(self) -> Optional[Spot]:
        """Get the currently selected spot."""
        table = self.query_one(DataTable)
        if table.cursor_row is not None and table.cursor_row < len(self._filtered_spots):
            return self._filtered_spots[table.cursor_row]
        return None

    @property
    def spot_count(self) -> int:
        """Get the number of filtered spots in the table."""
        return len(self._filtered_spots)

    @property
    def total_spot_count(self) -> int:
        """Get the total number of spots (unfiltered)."""
        return len(self._spots)

    def set_title(self, title: str) -> None:
        """Update the table title."""
        self._title = title
        self._update_header()

    def reset_filters(self) -> None:
        """Reset all filters to show all spots."""
        self._band_filter = "All"
        self._mode_filter = "All"
        self._apply_filters()
