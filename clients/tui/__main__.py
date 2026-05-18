"""
This module serves as the main entry point for the TUI application.

To run the application, execute this module directly:
    python -m clients.tui

It loads the application configuration from environment variables and then
starts the Textual application.
"""

from clients.tui.app import ExchangeApp
from clients.tui.config import load_config


def main() -> None:
    """Load configuration and run the main application."""
    config = load_config()
    app = ExchangeApp(config)
    app.run()


if __name__ == '__main__':
    main()
