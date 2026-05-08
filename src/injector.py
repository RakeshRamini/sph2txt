"""
sph2txt — Text injection at cursor position.

Default mode: clipboard paste (Ctrl+V) with clipboard save/restore.
Fallback mode: character-by-character keystroke simulation via pynput.
"""

import logging
import time

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

_kb = Controller()


def inject(text: str, config: dict) -> None:
    """Inject text at the current cursor position."""
    if not text:
        return

    mode = config.get("injection_mode", "clipboard")
    if mode == "clipboard":
        _inject_clipboard(text, config)
    else:
        _inject_keystrokes(text, config)


def _inject_clipboard(text: str, config: dict) -> None:
    """Copy text to clipboard, paste with Ctrl+V, restore original clipboard."""
    restore = config.get("restore_clipboard", True)
    original = None

    if restore:
        try:
            original = pyperclip.paste()
        except Exception:
            original = None

    pyperclip.copy(text)
    time.sleep(0.05)  # small delay for clipboard to settle

    _kb.press(Key.ctrl)
    _kb.press('v')
    _kb.release('v')
    _kb.release(Key.ctrl)
    time.sleep(0.05)

    if restore and original is not None:
        time.sleep(0.1)  # wait for paste to complete before restoring
        pyperclip.copy(original)

    logger.info("Injected %d chars via clipboard paste.", len(text))


def _inject_keystrokes(text: str, config: dict) -> None:
    """Type text character-by-character via pynput."""
    delay = config.get("typing_speed", 0.01)
    for char in text:
        _kb.type(char)
        if delay > 0:
            time.sleep(delay)
    logger.info("Injected %d chars via keystroke simulation.", len(text))
