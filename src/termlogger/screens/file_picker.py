"""File picker screen for ADIF import/export."""

from pathlib import Path
from typing import Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Static


class FilePickerScreen(ModalScreen[Optional[Path]]):
    """A modal file picker screen."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    CSS = """
    FilePickerScreen {
        align: center middle;
    }

    FilePickerScreen > Vertical {
        width: 80;
        height: 30;
        border: thick $primary;
        background: $surface;
        padding: 1;
    }

    FilePickerScreen .title {
        text-align: center;
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }

    FilePickerScreen .path-input {
        height: 3;
        margin-bottom: 1;
    }

    FilePickerScreen DirectoryTree {
        height: 1fr;
        border: solid $primary;
        margin-bottom: 1;
    }

    FilePickerScreen .button-row {
        height: 3;
        align: center middle;
    }

    FilePickerScreen Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        title: str = "Select File",
        start_path: Optional[Path] = None,
        extensions: Optional[list[str]] = None,
        save_mode: bool = False,
        default_filename: str = "",
    ) -> None:
        """Initialize the file picker.

        Args:
            title: Title to display
            start_path: Starting directory path
            extensions: List of file extensions to filter (e.g., [".adi", ".adif"])
            save_mode: If True, allow entering a new filename
            default_filename: Default filename for save mode
        """
        super().__init__()
        self.title_text = title
        self.start_path = start_path or Path.home()
        self.extensions = extensions or []
        self.save_mode = save_mode
        self.default_filename = default_filename
        self._selected_path: Optional[Path] = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        with Vertical():
            yield Label(self.title_text, classes="title")

            yield Input(
                value=str(self.start_path / self.default_filename)
                if self.default_filename
                else str(self.start_path),
                placeholder="Enter file path...",
                id="path-input",
                classes="path-input",
            )

            yield DirectoryTree(str(self.start_path), id="file-tree")

            with Horizontal(classes="button-row"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button(
                    "Save" if self.save_mode else "Open",
                    variant="primary",
                    id="select",
                )

    def on_mount(self) -> None:
        """Focus the path input on mount."""
        self.query_one("#path-input", Input).focus()

    @on(DirectoryTree.FileSelected)
    def _on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Handle file selection in the tree."""
        path = Path(event.path)

        # Filter by extension if specified
        if self.extensions:
            if path.suffix.lower() not in [ext.lower() for ext in self.extensions]:
                return

        self._selected_path = path
        self.query_one("#path-input", Input).value = str(path)

    @on(DirectoryTree.DirectorySelected)
    def _on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Handle directory selection in the tree."""
        self.query_one("#path-input", Input).value = str(event.path)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        """Handle cancel button."""
        self.dismiss(None)

    @on(Button.Pressed, "#select")
    def _on_select(self) -> None:
        """Handle select button."""
        self._do_select()

    @on(Input.Submitted, "#path-input")
    def _on_path_submitted(self, event: Input.Submitted) -> None:
        """Handle enter in path input."""
        self._do_select()

    def _do_select(self) -> None:
        """Perform the selection."""
        path_str = self.query_one("#path-input", Input).value.strip()
        if path_str:
            path = Path(path_str)

            # For save mode, allow non-existent files
            if self.save_mode:
                # Add default extension if missing
                if self.extensions and path.suffix.lower() not in [
                    ext.lower() for ext in self.extensions
                ]:
                    path = path.with_suffix(self.extensions[0])
                self.dismiss(path)
            else:
                # For open mode, file must exist
                if path.exists() and path.is_file():
                    self.dismiss(path)
                else:
                    self.notify("File not found", severity="error")
        else:
            self.notify("Please enter a file path", severity="warning")

    def action_cancel(self) -> None:
        """Cancel action."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Select action."""
        self._do_select()


class ExportCompleteScreen(ModalScreen[None]):
    """Modal screen showing export completion."""

    CSS = """
    ExportCompleteScreen {
        align: center middle;
    }

    ExportCompleteScreen > Vertical {
        width: 50;
        height: 10;
        border: thick $success;
        background: $surface;
        padding: 1;
    }

    ExportCompleteScreen .message {
        text-align: center;
        height: 1fr;
        content-align: center middle;
    }

    ExportCompleteScreen Button {
        width: 100%;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(self.message, classes="message")
            yield Button("OK", variant="primary", id="ok")

    @on(Button.Pressed, "#ok")
    def _on_ok(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key in ("enter", "escape"):
            self.dismiss(None)
