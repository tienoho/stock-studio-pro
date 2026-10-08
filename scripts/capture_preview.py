import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.ui.main_window import AutoStockMainWindow

def capture():
    app = QApplication.instance() or QApplication(sys.argv)
    window = AutoStockMainWindow()
    window.resize(1366, 768)
    window.show()

    # Load mock scene data into downloader tab
    mock_scenes = [
        {
            "id": 1,
            "time_start": "00:00:01",
            "time_end": "00:00:05",
            "dialogue": "AI và tương lai của công nghệ tự động hóa",
            "primary_keywords": ["artificial intelligence", "robotics", "future technology", "cyber"],
            "secondary_keywords": ["tech", "innovation", "code"],
        },
        {
            "id": 2,
            "time_start": "00:00:05",
            "time_end": "00:00:10",
            "dialogue": "Tối ưu hóa quy trình làm việc với studio chuyên nghiệp",
            "primary_keywords": ["digital workflow", "business analytics", "office productivity"],
            "secondary_keywords": ["modern office", "corporate"],
        }
    ]
    window.downloader_tab.load_scenes(mock_scenes)
    # Switch active scene
    window.downloader_tab._on_scene_clicked(mock_scenes[0])

    app.processEvents()

    artifact_dir = Path(r"C:\Users\Tien LeVe\.gemini\antigravity-ide\brain\2c684224-3805-4572-a85b-d62e3ce2cad5")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    out_path = artifact_dir / "buttons_perfect_preview.png"

    pixmap = window.grab()
    pixmap.save(str(out_path))
    print(f"Captured: {out_path}")
    window.close()

if __name__ == "__main__":
    capture()
