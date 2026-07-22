"""
sph2txt — System tray UI.

Displays a system tray icon with status indicators:
  - Green: idle, ready
  - Red: recording
  - Yellow: processing/transcribing

Right-click menu: Pause, Sleep, Resume, Settings, Quit.
Thread-safe icon updates via queue.
"""

import logging
import os
import queue
import threading

from PIL import Image
import pystray

logger = logging.getLogger(__name__)

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


class TrayIcon:
    """System tray icon with status updates and a quit callback."""

    # Possible app modes: active, paused, sleeping
    _APP_MODES = ("active", "paused", "sleeping")

    def __init__(self, on_quit: threading.Event):
        self._quit_event = on_quit
        self._icons = {
            "idle": Image.open(os.path.join(_ASSETS, "icon_idle.png")),
            "recording": Image.open(os.path.join(_ASSETS, "icon_recording.png")),
            "processing": Image.open(os.path.join(_ASSETS, "icon_processing.png")),
        }
        self._tray: pystray.Icon | None = None
        self._state_queue: queue.Queue = queue.Queue()
        self._settings_event = threading.Event()  # signal main thread to open settings
        self._hotkey_listener = None  # set by main.py after construction
        self._transcriber = None      # set by main.py after construction
        self._app_mode = "active"

    def start(self) -> None:
        """Create and run the tray icon (blocks on the calling thread)."""
        self._tray = pystray.Icon(
            name="sph2txt",
            icon=self._icons["idle"],
            title="sph2txt — Ready",
            menu=self._build_menu(),
        )
        logger.info("System tray icon started.")
        self._tray.run(setup=self._poll_state_queue)

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("sph2txt", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause",
                self._on_pause,
                visible=lambda item: self._app_mode == "active",
            ),
            pystray.MenuItem(
                "Sleep (free GPU)",
                self._on_sleep,
                visible=lambda item: self._app_mode in ("active", "paused"),
            ),
            pystray.MenuItem(
                "Resume",
                self._on_resume,
                visible=lambda item: self._app_mode in ("paused", "sleeping"),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Export History...", self._on_export),
            pystray.MenuItem("Settings...", self._on_settings),
            pystray.MenuItem("Quit", self._on_quit),
        )

    def set_state(self, state: str) -> None:
        """Thread-safe icon/tooltip update. state: 'idle'|'recording'|'processing'."""
        self._state_queue.put(state)

    def _poll_state_queue(self, icon) -> None:
        """Drain state queue and apply updates on the tray's own thread."""
        icon.visible = True
        self._drain_queue()
        # Re-schedule polling every 200ms using a single daemon timer
        self._schedule_poll(icon)

    def _schedule_poll(self, icon) -> None:
        """Schedule the next state poll, avoiding timer accumulation."""
        if not self._tray:
            return
        try:
            t = threading.Timer(0.2, self._poll_tick, args=(icon,))
            t.daemon = True
            t.start()
        except Exception:
            logger.debug("Failed to reschedule tray poll.")

    def _poll_tick(self, icon) -> None:
        """Single poll tick: drain queue then reschedule."""
        self._drain_queue()
        self._schedule_poll(icon)

    def _drain_queue(self) -> None:
        """Process all pending state updates."""
        try:
            while True:
                state = self._state_queue.get_nowait()
                self._apply_state(state)
        except queue.Empty:
            pass
        except Exception:
            logger.exception("Error processing tray state update")

    def _apply_state(self, state: str) -> None:
        """Actually update the icon — must run on tray thread."""
        if not self._tray:
            return
        mode_prefix = {
            "active": "",
            "paused": " [Paused]",
            "sleeping": " [Sleeping]",
        }
        suffix = mode_prefix.get(self._app_mode, "")
        titles = {
            "idle": f"sph2txt — Ready{suffix}",
            "recording": "sph2txt — Recording...",
            "processing": "sph2txt — Processing...",
        }
        try:
            self._tray.icon = self._icons.get(state, self._icons["idle"])
            self._tray.title = titles.get(state, titles["idle"])
            self._tray.update_menu()
        except Exception:
            logger.debug("Failed to update tray state (icon may be shutting down).")

    @property
    def app_mode(self) -> str:
        return self._app_mode

    @property
    def settings_event(self) -> threading.Event:
        return self._settings_event

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._tray:
            self._tray.stop()

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _on_pause(self, icon, item):
        """Disable hotkey listener. Model stays loaded."""
        logger.info("Paused — hotkey disabled, model stays in GPU.")
        self._app_mode = "paused"
        if self._hotkey_listener:
            self._hotkey_listener.enabled = False
        self.set_state("idle")

    def _on_sleep(self, icon, item):
        """Unload model from GPU. Frees VRAM."""
        logger.info("Sleeping — unloading model from GPU.")
        self._app_mode = "sleeping"
        if self._hotkey_listener:
            self._hotkey_listener.enabled = False
        if self._transcriber:
            self._transcriber.unload()
        self.set_state("idle")

    def _on_resume(self, icon, item):
        """Resume from pause or sleep."""
        if self._app_mode == "sleeping" and self._transcriber:
            logger.info("Resuming from sleep — reloading model...")
            self.set_state("processing")  # show yellow while loading
            threading.Thread(target=self._resume_from_sleep, daemon=True).start()
        else:
            logger.info("Resuming from pause.")
            self._app_mode = "active"
            if self._hotkey_listener:
                self._hotkey_listener.enabled = True
            self.set_state("idle")

    def _resume_from_sleep(self):
        """Reload model in background, then re-enable hotkey."""
        try:
            self._transcriber.reload()
        except Exception:
            logger.exception("Failed to reload model.")
        self._app_mode = "active"
        if self._hotkey_listener:
            self._hotkey_listener.enabled = True
        self.set_state("idle")
        logger.info("Resumed from sleep — ready.")

    def _on_export(self, icon, item):
        """Export transcription history to CSV."""
        threading.Thread(target=self._do_export, daemon=True).start()

    def _do_export(self):
        """Run export in background thread."""
        try:
            from src.export import export_csv
            path = export_csv()
            os.startfile(os.path.dirname(path))
        except Exception:
            logger.exception("Export failed")

    def _on_settings(self, icon, item):
        """Signal main thread to open Settings UI."""
        self._settings_event.set()

    def _on_quit(self, icon, item):
        logger.info("Quit requested from tray menu.")
        self._quit_event.set()
        self.stop()
