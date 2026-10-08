"""
AutoStock Studio - Modern Clean Code & SOLID Architecture Entry Point.
"""

import sys
import os
import traceback
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

from src.core.constants import APP_NAME, APP_VERSION
from src.ui.main_window import AutoStockMainWindow


def excepthook(exc_type, exc_value, exc_tb):
    """Global exception handler to capture unhandled errors gracefully."""
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(f"[FATAL ERROR] {tb_text}", file=sys.stderr)
    try:
        app = QApplication.instance()
        if app:
            QMessageBox.critical(
                None,
                "Lỗi Hệ Thống",
                f"Đã xảy ra lỗi không mong muốn:\n\n{exc_value}\n\nXem console để biết chi tiết."
            )
    except Exception:
        pass


def main():
    sys.excepthook = excepthook

    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName(f"{APP_NAME} v{APP_VERSION}")

    window = AutoStockMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
