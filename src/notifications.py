"""
sph2txt — Notification sounds.

Plays short audio cues on startup-ready and transcription-complete events.
Uses Python's built-in winsound module (Windows only, zero dependencies).
Sounds are non-blocking (SND_ASYNC) and respect Windows volume mixer.
Disabled gracefully on non-Windows or when config disables sounds.
"""

import logging
import os

logger = logging.getLogger(__name__)

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

try:
    import winsound
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False
    logger.debug("winsound not available — notification sounds disabled.")


def _play(filename: str) -> None:
    """Play a WAV file from assets/ asynchronously."""
    if not _AVAILABLE:
        return
    path = os.path.join(_ASSETS, filename)
    if not os.path.isfile(path):
        logger.debug("Sound file not found: %s", path)
        return
    try:
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        logger.debug("Failed to play sound: %s", filename)


def play_ready(enabled: bool = True) -> None:
    """Play the startup-ready chime."""
    if enabled:
        _play("ready.wav")


def play_complete(enabled: bool = True) -> None:
    """Play the transcription-complete chime."""
    if enabled:
        _play("complete.wav")
