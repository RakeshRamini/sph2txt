"""
sph2txt — Configuration management.

Loads config.json from project root, provides defaults,
and exposes settings to all other modules.
"""

import json
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")

_DEFAULTS = {
    "model": "large-v3-turbo",
    "device": "cuda",
    "compute_type": "float16",
    "language": "en",
    "hotkey": ["alt", "x"],
    "mode": "push_to_talk",
    "beam_size": 5,
    "vad_filter": True,
    "injection_mode": "clipboard",
    "typing_speed": 0.01,
    "restore_clipboard": True,
    "voice_commands": {
        "new line": "\n",
        "new paragraph": "\n\n",
        "tab": "\t",
    },
    "paths": {
        "model_cache": "models/huggingface",
        "data_root": "data",
        "log_dir": "logs",
    },
    "logging": {
        "enabled": True,
        "log_target_app": True,
        "log_window_title": False,
        "retention_days": 90,
        "max_db_size_mb": 500,
    },
    "storage": {
        "auto_cleanup": True,
        "cleanup_on_startup": True,
    },
}


def load_config() -> dict:
    """Load config.json, falling back to defaults for missing keys."""
    config = dict(_DEFAULTS)
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config.update(user_config)
    return config


def resolve_path(config: dict, key: str) -> str:
    """Resolve a relative path from config.paths to an absolute path."""
    rel = config.get("paths", {}).get(key, _DEFAULTS["paths"][key])
    return os.path.join(_PROJECT_ROOT, rel)
