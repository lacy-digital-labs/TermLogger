"""Spots table widget for displaying DX cluster and POTA spots."""

import logging
from typing import Optional

from rich.console import RenderableType
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.coordinate import Coordinate
from textual.events import MouseDown
from textual.message import Message
from textual.widget import Widget
from textual.widgets import DataTable, Static

from ..models import Spot, format_frequency

logger = logging.getLogger(__name__)


# Common modes to filter by (in cycle order)
FILTER_MODES = ["All", "CW", "SSB", "FT8", "FT4", "RTTY", "FM", "DIGITAL"]

# Bands to filter by (in cycle order)
FILTER_BANDS = ["All", "160m", "80m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m", "2m"]


class FilterAction(Widget):
    """Clickable filter action widget (similar to FooterKey)."""

    DEFAULT_CSS = """
    FilterAction {
        width: auto;
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }

    FilterAction:hover {
        background: $accent;
        color: $text;
        text-style: bold;
    }
    """

    class Clicked(Message):
        """Message sent when filter action is clicked."""

        def __init__(self, action_id: str) -> None:
            self.action_id = action_id
            super().__init__()

    def __init__(self, label: str, action_id: str, **kwargs) -> None:
        """Initialize filter action.

        Args:
            label: Display label (e.g., "B: Band")
            action_id: Action identifier (e.g., "band", "mode", "clear")
        """
        super().__init__(**kwargs)
        self.label = label
        self.action_id = action_id

    def render(self) -> RenderableType:
        """Render the filter action as clickable text."""
        return Text(self.label, style="")

    def on_mouse_down(self, event: MouseDown) -> None:
        """Handle click by posting message."""
        self.post_message(self.Clicked(self.action_id))
        event.stop()


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
        width: 100%;
        align: left middle;
    }

    SpotsTable .filter-separator {
        width: auto;
        height: 1;
        color: $text-muted;
    }
    """

    class SpotSelected(Message):
        """Message sent when a spot is selected/clicked."""

        def __init__(self, spot: Spot) -> None:
            self.spot = spot
            super().__init__()

    class SpotAgedOut(Message):
        """Message sent when a selected spot ages out and gets pinned."""

        def __init__(self, callsign: str) -> None:
            self.callsign = callsign
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
        self._selected_callsign: Optional[str] = None  # Track selected callsign
        self._pinned_spot: Optional[Spot] = None  # Aged-out spot kept at top
        self._suppressing_selection_event: bool = False  # Suppress DataTable event during restore

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(f"[bold]{self._title}[/bold]", classes="spots-header", id="spots-title")
        with Horizontal(id="filter-status-bar", classes="filter-status"):
            yield FilterAction("B: Band", "band", id="band-action")
            yield Static(" | ", classes="filter-separator")
            yield FilterAction("M: Mode", "mode", id="mode-action")
            yield Static(" | ", classes="filter-separator")
            yield FilterAction("C: Clear", "clear", id="clear-action")
        yield DataTable(id="spots-data-table", cursor_type="row")

    def on_mount(self) -> None:
        """Initialize the table."""
        table = self.query_one(DataTable)

        # Add columns with keys
        for name, width, key in self.COLUMNS:
            table.add_column(name, width=width, key=key)

    def on_filter_action_clicked(self, event: FilterAction.Clicked) -> None:
        """Handle filter action clicks."""
        if event.action_id == "band":
            self._cycle_band_filter()
        elif event.action_id == "mode":
            self._cycle_mode_filter()
        elif event.action_id == "clear":
            self.reset_filters()

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
        """Update the status bar with filter info (no longer needed - info shown in header)."""
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
        """Refresh the table display, preserving selection across refreshes."""
        table = self.query_one(DataTable)

        # Log current selection (use saved callsign, not get_selected_spot which
        # would return wrong spot since _filtered_spots was already updated)
        if self._selected_callsign:
            logger.info(f"[SPOTS] Before refresh: selected spot = {self._selected_callsign}")
        else:
            logger.info("[SPOTS] Before refresh: no spot selected")

        # Save reference to selected spot before clearing table
        # We need the full spot object for pinning if it ages out
        current_spot = None
        if self._selected_callsign:
            # Search for the selected callsign in the OLD filtered list
            # (before we clear the table, the cursor might still point to old data)
            for spot in self._filtered_spots:
                if spot.callsign.upper() == self._selected_callsign.upper():
                    current_spot = spot
                    break

        table.clear()

        # Check if selected callsign is in new filtered list
        new_cursor_row = None
        spot_found_in_list = False
        if self._selected_callsign:
            logger.info(f"[SPOTS] Searching for {self._selected_callsign} in {len(self._filtered_spots)} filtered spots")
            for i, spot in enumerate(self._filtered_spots):
                if spot.callsign.upper() == self._selected_callsign.upper():
                    spot_found_in_list = True
                    new_cursor_row = i
                    logger.info(f"[SPOTS] Found {self._selected_callsign} at index {i}")
                    break

            if not spot_found_in_list:
                logger.info(f"[SPOTS] {self._selected_callsign} NOT found in new list")

        # If selected spot not found and we have a current spot, pin it at top
        if self._selected_callsign and not spot_found_in_list and current_spot:
            # Only emit notification if this is newly pinned (not already pinned)
            is_newly_pinned = (self._pinned_spot is None or
                             self._pinned_spot.callsign != current_spot.callsign)
            self._pinned_spot = current_spot
            new_cursor_row = 0  # Pinned spot will be at row 0
            logger.info(f"[SPOTS] Pinning {current_spot.callsign} at row 0")
            # Emit notification for newly aged out spot
            if is_newly_pinned:
                self.post_message(self.SpotAgedOut(current_spot.callsign))
        elif spot_found_in_list:
            # Spot found in list, clear any old pinned spot
            logger.info("[SPOTS] Spot found in list, clearing pinned spot")
            self._pinned_spot = None

        # Add pinned spot at top if it exists
        if self._pinned_spot:
            freq_str = format_frequency(self._pinned_spot.frequency)
            band_str = self._pinned_spot.band.value if self._pinned_spot.band else "-"
            mode_str = self._pinned_spot.mode or "-"
            info_str = self._pinned_spot.info_str

            table.add_row(
                f"[dim]{self._pinned_spot.time_str}[/dim]",
                f"[yellow][AGED] {self._pinned_spot.callsign[:10]}[/yellow]",
                f"[dim]{freq_str}[/dim]",
                f"[dim]{band_str}[/dim]",
                f"[dim]{mode_str[:5]}[/dim]",
                f"[dim]{info_str}[/dim]",
                f"[dim]{self._pinned_spot.spotter[:8]}[/dim]",
                key="pinned",
            )
            if spot_found_in_list:
                # Adjust cursor position for the offset
                new_cursor_row = new_cursor_row + 1 if new_cursor_row is not None else None

        # Add all filtered spots
        for i, spot in enumerate(self._filtered_spots):
            freq_str = format_frequency(spot.frequency)
            band_str = spot.band.value if spot.band else "-"
            mode_str = spot.mode or "-"
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

        # Restore cursor position
        if new_cursor_row is not None and table.row_count > 0:
            try:
                logger.info(f"[SPOTS] Restoring cursor to row {new_cursor_row} (table has {table.row_count} rows)")

                # Suppress automatic RowSelected event from cursor movement
                self._suppressing_selection_event = True

                # Use cursor_coordinate for absolute positioning
                table.cursor_coordinate = Coordinate(new_cursor_row, 0)
                logger.info(f"[SPOTS] Cursor restored. New cursor_row = {table.cursor_row}")

                # Re-enable events
                self._suppressing_selection_event = False

                # NOTE: We don't post SpotSelected here because that would trigger
                # form update, auto-QSY, and callsign lookup on every refresh.
                # We only restore the visual cursor position - user already selected this spot.
            except Exception as e:
                logger.error(f"[SPOTS] Failed to restore cursor: {e}")
                self._suppressing_selection_event = False  # Make sure we re-enable
        else:
            logger.info(f"[SPOTS] NOT restoring cursor: new_cursor_row={new_cursor_row}, row_count={table.row_count}")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        # Ignore events that occur during cursor restoration
        if self._suppressing_selection_event:
            logger.info("[SPOTS] Row selected event SUPPRESSED (during cursor restore)")
            return

        try:
            row_key = str(event.row_key.value)
            logger.info(f"[SPOTS] Row selected event: row_key={row_key}")

            # Check if pinned spot is selected
            if row_key == "pinned" and self._pinned_spot:
                self._selected_callsign = self._pinned_spot.callsign
                logger.info(f"[SPOTS] Pinned spot selected: {self._selected_callsign}")
                self.post_message(self.SpotSelected(self._pinned_spot))
                return

            # Regular spot selected
            row_index = int(row_key)
            if 0 <= row_index < len(self._filtered_spots):
                spot = self._filtered_spots[row_index]
                self._selected_callsign = spot.callsign
                logger.info(f"[SPOTS] Regular spot selected: {spot.callsign} at index {row_index}")
                # Clear pinned spot when user selects a different spot
                if self._pinned_spot and self._pinned_spot.callsign != spot.callsign:
                    logger.info("[SPOTS] Clearing pinned spot (user selected different spot)")
                    self._pinned_spot = None
                self.post_message(self.SpotSelected(spot))
        except (ValueError, IndexError) as e:
            logger.warning(f"[SPOTS] Row selection failed: {e}")

    def get_selected_spot(self) -> Optional[Spot]:
        """Get the currently selected spot."""
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return None

        # Check if cursor is on pinned spot (row 0 when pinned spot exists)
        if self._pinned_spot and table.cursor_row == 0:
            return self._pinned_spot

        # Calculate offset if pinned spot exists
        offset = 1 if self._pinned_spot else 0
        filtered_index = table.cursor_row - offset

        if 0 <= filtered_index < len(self._filtered_spots):
            return self._filtered_spots[filtered_index]
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
