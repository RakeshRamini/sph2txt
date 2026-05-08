"""
sph2txt — System tray UI.

Displays a system tray icon with status indicators:
  - Green: idle, ready
  - Red: recording
  - Yellow: processing/transcribing

Right-click menu: Pause, Sleep, Resume, Quit, Settings.
"""

import logging
import os
import threading

from PIL import Image
import pystray

logger = logging.getLogger(__name__)

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class TrayIcon:
    """System tray icon with status updates and a quit callback."""

    def __init__(self, on_quit: threading.Event):
        self._quit_event = on_quit
        self._icons = {
            "idle": Image.open(os.path.join(_ASSETS, "icon_idle.png")),
            "recording": Image.open(os.path.join(_ASSETS, "icon_recording.png")),
            "processing": Image.open(os.path.join(_ASSETS, "icon_processing.png")),
        }
        self._tray: pystray.Icon | None = None
        self._settings_ui = None
        self._hotkey_listener = None  # set by main.py after construction

    def start(self) -> None:
        """Create and run the tray icon (blocks on the calling thread)."""
        menu = pystray.Menu(
            pystray.MenuItem("sph2txt — Idle", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Settings...", self._on_settings),
            pystray.MenuItem("Quit", self._on_quit),
        )
        self._tray = pystray.Icon(
            name="sph2txt",
            icon=self._icons["idle"],
            title="sph2txt — Ready",
            menu=menu,
        )
        logger.info("System tray icon started.")
        self._tray.run()

    def set_state(self, state: str) -> None:
        """Update icon and tooltip. state: 'idle' | 'recording' | 'processing'."""
        if not self._tray:
            return
        titles = {
            "idle": "sph2txt — Ready",
            "recording": "sph2txt — Recording...",
            "processing": "sph2txt — Processing...",
        }
        self._tray.icon = self._icons.get(state, self._icons["idle"])
        self._tray.title = titles.get(state, titles["idle"])

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._tray:
            self._tray.stop()

    def _on_settings(self, icon, item):
        """Open the Settings UI in a background thread."""
        from src.ui import SettingsUI
        if self._settings_ui is None or not self._settings_ui._log_tail_running:
            logger.info("Opening settings window.")
            self._settings_ui = SettingsUI(
                on_activate=self._activate_hotkey,
                on_deactivate=self._deactivate_hotkey,
                initially_active=self._hotkey_listener.enabled if self._hotkey_listener else False,
            )
            self._settings_ui.show_nonblocking()

    def _activate_hotkey(self):
        if self._hotkey_listener:
            self._hotkey_listener.enabled = True

    def _deactivate_hotkey(self):
        if self._hotkey_listener:
            self._hotkey_listener.enabled = False

    def _on_quit(self, icon, item):
        logger.info("Quit requested from tray menu.")
        self._quit_event.set()
        self.stop()
