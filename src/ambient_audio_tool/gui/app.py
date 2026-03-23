from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print(
            "GUI launch failed: PySide6 is not installed.\n"
            "Install GUI dependencies with: pip install -e .[gui]"
        )
        return 1

    from .main_window import MainWindow

    app = QApplication(argv or sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


def entrypoint() -> None:
    raise SystemExit(main())
