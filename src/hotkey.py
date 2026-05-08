"""
sph2txt — Global hotkey listener.

Registers a system-wide hotkey (default: Alt+X) using pynput.
Supports two modes:
  - push_to_talk: hold to record, release to transcribe
  - toggle: press to start, press again to stop
"""

import logging
import threading
from typing import Callable

from pynput import keyboard

logger = logging.getLogger(__name__)

# Map config strings → pynput Key objects
_KEY_MAP = {
    "alt": keyboard.Key.alt,
    "alt_l": keyboard.Key.alt_l,
    "alt_r": keyboard.Key.alt_r,
    "ctrl": keyboard.Key.ctrl,
    "ctrl_l": keyboard.Key.ctrl_l,
    "ctrl_r": keyboard.Key.ctrl_r,
    "shift": keyboard.Key.shift,
    "shift_l": keyboard.Key.shift_l,
    "shift_r": keyboard.Key.shift_r,
    "cmd": keyboard.Key.cmd,
}


def _parse_hotkey(hotkey_list: list[str]) -> tuple:
    """Convert config hotkey list like ['alt', 'x'] into pynput key objects."""
    keys = []
    for k in hotkey_list:
        k_lower = k.lower()
        if k_lower in _KEY_MAP:
            keys.append(_KEY_MAP[k_lower])
        elif len(k_lower) == 1:
            keys.append(keyboard.KeyCode.from_char(k_lower))
        else:
            raise ValueError(f"Unknown hotkey component: {k!r}")
    return tuple(keys)


class HotkeyListener:
    """Listens for a global hotkey and calls back on press/release."""

    def __init__(self, config: dict,
                 on_press: Callable[[], None],
                 on_release: Callable[[], None]):
        hotkey_cfg = config.get("hotkey", ["alt", "x"])
        self._mode = config.get("mode", "push_to_talk")
        self._hotkey_keys = set(_parse_hotkey(hotkey_cfg))
        self._on_press = on_press
        self._on_release = on_release

        self._pressed_keys: set = set()
        self._active = False  # for toggle mode
        self._recording = False  # guard against repeat key events
        self._enabled = True  # can be toggled from UI
        self._lock = threading.Lock()  # protect _recording flag
        self._listener: keyboard.Listener | None = None

        logger.info("Hotkey: %s, mode: %s", hotkey_cfg, self._mode)

    def start(self) -> None:
        """Start listening for the hotkey in a daemon thread."""
        self._listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._listener.daemon = True
        self._listener.start()
        logger.info("Hotkey listener started.")

    def stop(self) -> None:
        """Stop the hotkey listener."""
        if self._listener:
            self._listener.stop()
            self._listener = None
            logger.info("Hotkey listener stopped.")

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        logger.info("Hotkey listener %s.", "enabled" if value else "disabled")

    def _normalize(self, key) -> keyboard.Key | keyboard.KeyCode:
        """Normalize left/right modifier variants to generic ones."""
        alias = {
            keyboard.Key.alt_l: keyboard.Key.alt,
            keyboard.Key.alt_r: keyboard.Key.alt,
            keyboard.Key.alt_gr: keyboard.Key.alt,
            keyboard.Key.ctrl_l: keyboard.Key.ctrl,
            keyboard.Key.ctrl_r: keyboard.Key.ctrl,
            keyboard.Key.shift_l: keyboard.Key.shift,
            keyboard.Key.shift_r: keyboard.Key.shift,
            keyboard.Key.cmd_l: keyboard.Key.cmd,
            keyboard.Key.cmd_r: keyboard.Key.cmd,
        }
        return alias.get(key, key)

    def _hotkey_matched(self) -> bool:
        normalized = {self._normalize(k) for k in self._pressed_keys}
        return self._hotkey_keys.issubset(normalized)

    def _on_key_press(self, key):
        self._pressed_keys.add(key)
        if not self._enabled or not self._hotkey_matched():
            return

        with self._lock:
            if self._mode == "push_to_talk":
                if not self._recording:
                    self._recording = True
                else:
                    return
            else:  # toggle
                if self._active:
                    self._active = False
                    self._recording = False
                else:
                    self._active = True
                    self._recording = True

        if self._mode == "push_to_talk":
            self._fire_press()
        elif self._active:
            self._fire_press()
        else:
            self._fire_release()

    def _on_key_release(self, key):
        self._pressed_keys.discard(key)
        if self._mode == "push_to_talk" and not self._hotkey_matched():
            with self._lock:
                if not self._recording:
                    return
                self._recording = False
            self._fire_release()

    def _fire_press(self):
        logger.debug("Hotkey pressed → recording start")
        threading.Thread(target=self._on_press, daemon=True).start()

    def _fire_release(self):
        logger.debug("Hotkey released → recording stop")
        threading.Thread(target=self._on_release, daemon=True).start()
