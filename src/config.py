"""
sph2txt — Configuration management.

Loads config.json from project root, provides defaults,
and exposes settings to all other modules.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "config.json")

_DEFAULTS = {
    "model": "large-v3-turbo",
    "device": "cuda",
    "compute_type": "float16",
    "language": "en",
    "hotkey": ["alt", "x"],
    "mode": "push_to_talk",
    "beam_size": 3,
    "vad_filter": True,
    "injection_mode": "clipboard",
    "typing_speed": 0.01,
    "restore_clipboard": True,
    "clipboard_restore_delay_ms": 500,
    "gpu_keepalive": True,
    "keepalive_interval_sec": 180,
    "warmup_on_startup": True,
    "resampler": "soxr",
    "notification_sounds": True,
    "silence_rejection": True,
    "silence_threshold": 0.001,
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
        "max_log_files": 5,
        "max_log_size_mb": 10,
    },
    "storage": {
        "auto_cleanup": True,
        "cleanup_on_startup": True,
    },
}

# Nested keys that should be deep-merged (not replaced wholesale)
_NESTED_KEYS = {"voice_commands", "paths", "logging", "storage"}


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Recursively merge overrides into defaults for known nested keys."""
    merged = dict(defaults)
    for key, value in overrides.items():
        if key in _NESTED_KEYS and isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _validate_config(config: dict) -> None:
    """Log warnings for clearly invalid config values."""
    if not isinstance(config.get("beam_size"), int) or config["beam_size"] < 1:
        logger.warning("Invalid beam_size=%r, falling back to 3.", config.get("beam_size"))
        config["beam_size"] = 3
    if config.get("device") not in ("cuda", "cpu"):
        logger.warning("Invalid device=%r, falling back to 'cuda'.", config.get("device"))
        config["device"] = "cuda"
    if not isinstance(config.get("hotkey"), list) or len(config["hotkey"]) < 1:
        logger.warning("Invalid hotkey=%r, falling back to ['alt', 'x'].", config.get("hotkey"))
        config["hotkey"] = ["alt", "x"]
    if config.get("mode") not in ("push_to_talk", "toggle"):
        logger.warning("Invalid mode=%r, falling back to 'push_to_talk'.", config.get("mode"))
        config["mode"] = "push_to_talk"
    if config.get("injection_mode") not in ("clipboard", "keystrokes"):
        logger.warning("Invalid injection_mode=%r, falling back to 'clipboard'.", config.get("injection_mode"))
        config["injection_mode"] = "clipboard"
    threshold = config.get("silence_threshold")
    if not isinstance(threshold, (int, float)) or threshold < 0:
        logger.warning("Invalid silence_threshold=%r, falling back to 0.001.", threshold)
        config["silence_threshold"] = 0.001


def load_config() -> dict:
    """Load config.json, falling back to defaults for missing keys."""
    config = dict(_DEFAULTS)
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        config = _deep_merge(config, user_config)
    _validate_config(config)
    return config


def resolve_path(config: dict, key: str) -> str:
    """Resolve a relative path from config.paths to an absolute path."""
    rel = config.get("paths", {}).get(key, _DEFAULTS["paths"][key])
    return os.path.join(_PROJECT_ROOT, rel)
