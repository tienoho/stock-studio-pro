"""
JSON-based configuration repository with obfuscation for API keys.
"""

import json
import base64
from pathlib import Path
from typing import Dict, Any
from ...core.interfaces.storage import IConfigRepository
from ...core.constants import CONFIG_FILE, DEFAULT_OUTPUT_DIR


def obfuscate(text: str) -> str:
    if not text:
        return ""
    return base64.b64encode(text.encode('utf-8')).decode('utf-8')


def deobfuscate(text: str) -> str:
    if not text:
        return ""
    try:
        return base64.b64decode(text.encode('utf-8')).decode('utf-8')
    except Exception:
        return text


class JsonConfigRepository(IConfigRepository):
    """Handles loading and saving app configuration to a JSON file."""

    DEFAULT_CONFIG = {
        "pexels_keys": [],
        "pixabay_keys": [],
        "vecteezy_keys": [],
        "coverr_keys": [],
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "search_prefs": {},
    }

    def __init__(self, file_path: Path = CONFIG_FILE):
        self.file_path = Path(file_path)

    def load(self) -> Dict[str, Any]:
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                for key_list in ["pexels_keys", "pixabay_keys", "coverr_keys", "vecteezy_keys"]:
                    for k in config.get(key_list, []):
                        k["key"] = deobfuscate(k.get("key", ""))

                merged = {**self.DEFAULT_CONFIG, **config}
                return merged
            except Exception as e:
                print(f"[JsonConfigRepository] Load error: {e}")

        return self.DEFAULT_CONFIG.copy()

    def save(self, config: Dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            to_save = {}
            for k, v in config.items():
                if k in ["pexels_keys", "pixabay_keys", "coverr_keys", "vecteezy_keys"]:
                    to_save[k] = [
                        {**item, "key": obfuscate(item.get("key", ""))}
                        for item in v
                    ]
                else:
                    to_save[k] = v

            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[JsonConfigRepository] Save error: {e}")

    # Aliases for convenience
    load_config = load
    save_config = save
