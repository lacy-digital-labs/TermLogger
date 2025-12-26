"""TermLogger - Terminal Amateur Radio Logging Application."""

from pathlib import Path

from textual.app import App

from .callsign import CallsignLookupService
from .config import load_config
from .database import Database
from .screens.help import SplashScreen
from .screens.main import MainScreen


class TermLoggerApp(App):
    """Main TermLogger application."""

    TITLE = "TermLogger"
    SUB_TITLE = "Amateur Radio Logger"
    CSS_PATH = Path(__file__).parent.parent.parent / "termlogger.css"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.config = load_config()
        self.db = Database(self.config.db_path)
        self.lookup_service = CallsignLookupService(self.config)

    def on_mount(self) -> None:
        """Initialize the application."""
        self.push_screen(MainScreen(self.db))
        # Show splash screen on startup
        self.push_screen(SplashScreen())

    async def on_unmount(self) -> None:
        """Clean up resources when app closes."""
        await self.lookup_service.close()


def main() -> None:
    """Run the TermLogger application."""
    app = TermLoggerApp()
    app.run()


if __name__ == "__main__":
    main()
