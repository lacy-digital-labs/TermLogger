"""TermLogger - Terminal Amateur Radio Logging Application."""

import logging
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
    CSS_PATH = Path(__file__).parent / "termlogger.css"

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
    # Load config to check debug logging settings
    config = load_config()

    # Configure logging if enabled
    if config.debug_logging_enabled:
        # Get log level from config (default to INFO if invalid)
        log_level = getattr(logging, config.debug_log_level, logging.INFO)

        logging.basicConfig(
            filename=config.debug_log_file,
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        logger = logging.getLogger(__name__)
        logger.info(f"TermLogger starting with debug logging enabled (level: {config.debug_log_level})")

    app = TermLoggerApp()
    app.run()


if __name__ == "__main__":
    main()
