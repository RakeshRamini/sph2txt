"""
sph2txt — Text injection at cursor position.

Default mode: clipboard paste (Ctrl+V) with clipboard save/restore.
Fallback mode: character-by-character keystroke simulation via pynput.
Clipboard restore uses a configurable delay with cancellable timer.
"""

import logging
import threading
import time

import pyperclip
from pynput.keyboard import Controller, Key

logger = logging.getLogger(__name__)

_kb = Controller()
_restore_timer: threading.Timer | None = None
_restore_lock = threading.Lock()
_inject_lock = threading.Lock()  # prevent overlapping clipboard paste operations


def inject(text: str, config: dict) -> None:
    """Inject text at the current cursor position."""
    if not text:
        return

    mode = config.get("injection_mode", "clipboard")
    if mode == "clipboard":
        with _inject_lock:
            _inject_clipboard(text, config)
    else:
        _inject_keystrokes(text, config)


def _inject_clipboard(text: str, config: dict) -> None:
    """Copy text to clipboard, paste with Ctrl+V, restore original clipboard."""
    global _restore_timer
    restore = config.get("restore_clipboard", True)
    delay_ms = config.get("clipboard_restore_delay_ms", 500)
    original = None

    # Cancel any pending clipboard restore from a previous injection
    with _restore_lock:
        if _restore_timer is not None:
            _restore_timer.cancel()
            _restore_timer = None

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
        with _restore_lock:
            _restore_timer = threading.Timer(
                delay_ms / 1000.0,
                _deferred_restore,
                args=(original,),
            )
            _restore_timer.daemon = True
            _restore_timer.start()

    logger.info("Injected %d chars via clipboard paste.", len(text))


def _deferred_restore(original: str) -> None:
    """Restore the original clipboard contents after a delay."""
    global _restore_timer
    try:
        pyperclip.copy(original)
    except Exception:
        logger.debug("Failed to restore clipboard.")
    with _restore_lock:
        _restore_timer = None


def _inject_keystrokes(text: str, config: dict) -> None:
    """Type text character-by-character via pynput."""
    delay = config.get("typing_speed", 0.01)
    for char in text:
        _kb.type(char)
        if delay > 0:
            time.sleep(delay)
    logger.info("Injected %d chars via keystroke simulation.", len(text))
