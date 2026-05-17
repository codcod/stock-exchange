from clients.tui.app import ExchangeApp
from clients.tui.config import load_config


def main() -> None:
    config = load_config()
    app = ExchangeApp(config)
    app.run()


if __name__ == '__main__':
    main()
