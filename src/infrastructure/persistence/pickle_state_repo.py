"""
Pickle-based session state repository.
"""

import pickle
from pathlib import Path
from typing import Dict, Any, Optional
from ...core.interfaces.storage import IStateRepository
from ...core.constants import STATE_FILE


class PickleStateRepository(IStateRepository):
    """Handles loading and saving transient session state to a Pickle file."""

    def __init__(self, file_path: Path = STATE_FILE):
        self.file_path = Path(file_path)

    def load(self) -> Optional[Dict[str, Any]]:
        if self.file_path.exists():
            try:
                with open(self.file_path, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                print(f"[PickleStateRepository] Load error: {e}")
        return None

    def save(self, state: Dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'wb') as f:
                pickle.dump(state, f)
        except Exception as e:
            print(f"[PickleStateRepository] Save error: {e}")

    def reset(self) -> None:
        if self.file_path.exists():
            try:
                self.file_path.unlink()
            except Exception as e:
                print(f"[PickleStateRepository] Reset error: {e}")

    # Aliases for convenience
    load_state = load
    save_state = save
