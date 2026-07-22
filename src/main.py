"""
sph2txt — Main entry point and orchestrator.

Initializes all components and runs the application loop:
  1. Load & validate config
  2. Initialize Whisper model (GPU) + warmup
  3. Start system tray (background thread)
  4. Listen for hotkey
  5. On trigger: capture audio → silence check → transcribe → inject text
  6. Main thread handles settings UI requests and quit signal
"""

import atexit
import logging
import logging.handlers
import os
import sys
import threading

# Redirect HuggingFace cache into project-local models/ folder
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["HF_HOME"] = os.path.join(_project_root, "models", "huggingface")

# Add NVIDIA cuDNN/cuBLAS DLL paths so CTranslate2 can find them
_nvidia_dll_loaded = False
try:
    import nvidia.cudnn
    import nvidia.cublas
    for pkg in (nvidia.cudnn, nvidia.cublas):
        dll_dir = os.path.join(pkg.__path__[0], "bin")
        if os.path.isdir(dll_dir):
            os.add_dll_directory(dll_dir)
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")
    _nvidia_dll_loaded = True
except ImportError:
    pass

# Fallback: scan user site-packages for nvidia DLLs (packages may be outside venv)
if not _nvidia_dll_loaded:
    _user_site = os.path.join(
        os.path.expanduser("~"),
        "AppData", "Local", "Packages",
        "PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0",
        "LocalCache", "local-packages", "Python313", "site-packages", "nvidia",
    )
    for sub in ("cudnn", "cublas"):
        dll_dir = os.path.join(_user_site, sub, "bin")
        if os.path.isdir(dll_dir):
            os.add_dll_directory(dll_dir)
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ.get("PATH", "")

from src.config import load_config, resolve_path
from src.transcriber import Transcriber
from src.audio import AudioRecorder
from src.postprocess import postprocess
from src.injector import inject
from src.hotkey import HotkeyListener
from src.tray import TrayIcon
from src.notifications import play_ready, play_complete

logger = logging.getLogger(__name__)

# Module-level lock file handle — prevents GC from releasing the lock
_lock_fh = None


def main():
    """Application entry point."""
    global _lock_fh

    # --- Single-instance lock ---
    lock_path = os.path.join(_project_root, ".sph2txt.lock")
    try:
        _lock_fh = open(lock_path, "w")
        import msvcrt
        msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
    except (OSError, IOError):
        print("sph2txt is already running.")
        return

    # Clean up lock file on exit
    def _cleanup_lock():
        try:
            if _lock_fh:
                _lock_fh.close()
            if os.path.exists(lock_path):
                os.remove(lock_path)
        except OSError:
            pass
    atexit.register(_cleanup_lock)

    # --- Config ---
    config = load_config()

    # --- Logging (with rotation) ---
    log_dir = resolve_path(config, "log_dir")
    os.makedirs(log_dir, exist_ok=True)
    log_cfg = config.get("logging", {})
    max_bytes = log_cfg.get("max_log_size_mb", 10) * 1024 * 1024
    max_files = log_cfg.get("max_log_files", 5)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, "sph2txt.log"),
                maxBytes=max_bytes,
                backupCount=max_files,
                encoding="utf-8",
            ),
        ],
    )
    logger.info("sph2txt starting...")

    # --- Components ---
    transcriber = Transcriber(config)

    # Warmup
    if config.get("warmup_on_startup", True):
        transcriber.warmup()

    # GPU keepalive
    transcriber.start_keepalive()

    recorder = AudioRecorder(resampler=config.get("resampler", "soxr"))
    quit_event = threading.Event()
    tray = TrayIcon(on_quit=quit_event)

    sounds_enabled = config.get("notification_sounds", True)
    silence_rejection = config.get("silence_rejection", True)
    silence_threshold = config.get("silence_threshold", 0.001)

    # Log unhandled exceptions in daemon threads instead of silently dropping them
    _orig_excepthook = threading.excepthook
    def _thread_excepthook(args):
        if args.exc_type is SystemExit:
            return
        logger.error("Unhandled exception in thread %s", args.thread,
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
        _orig_excepthook(args)
    threading.excepthook = _thread_excepthook

    # --- Pipeline callbacks ---
    def on_hotkey_press():
        if tray.app_mode != "active":
            return
        tray.set_state("recording")
        try:
            recorder.start()
        except Exception:
            logger.exception("Failed to start audio recording")
            tray.set_state("idle")

    def on_hotkey_release():
        if tray.app_mode != "active":
            return
        try:
            audio = recorder.stop()
        except Exception:
            logger.exception("Failed to stop audio recording")
            tray.set_state("idle")
            return
        if len(audio) == 0:
            logger.warning("No audio captured, skipping.")
            tray.set_state("idle")
            return

        # Silence rejection — skip inference on accidental hotkey presses
        if silence_rejection and AudioRecorder.is_silent(audio, silence_threshold):
            logger.info("Audio below silence threshold (RMS < %.4f), skipping.", silence_threshold)
            tray.set_state("idle")
            return

        tray.set_state("processing")
        try:
            text = transcriber.transcribe(audio)
            logger.info("Raw transcription: %r", text)
            text = postprocess(text, config)
            if text:
                inject(text, config)
                logger.info("Injected: %s", text)
                play_complete(sounds_enabled)
            else:
                logger.info("Transcription was empty after post-processing.")
        except Exception:
            logger.exception("Pipeline error")
        finally:
            tray.set_state("idle")

    # --- Hotkey listener ---
    hotkey = HotkeyListener(config, on_press=on_hotkey_press,
                            on_release=on_hotkey_release)
    hotkey.start()
    tray._hotkey_listener = hotkey
    tray._transcriber = transcriber

    # --- System tray (background thread) ---
    def _run_tray():
        try:
            tray.start()
            logger.warning("Tray icon exited unexpectedly.")
        except Exception:
            logger.exception("Tray icon crashed")

    tray_thread = threading.Thread(target=_run_tray, daemon=True)
    tray_thread.start()
    # Give the tray a moment to initialize before proceeding
    import time
    time.sleep(0.5)

    # --- Startup complete ---
    logger.info("Ready. Press Alt+X to speak.")
    play_ready(sounds_enabled)

    # --- Main thread event loop ---
    # Handles settings UI requests (tkinter must run on main thread)
    # and waits for quit signal.
    try:
        while not quit_event.is_set():
            # Restart tray if its thread died unexpectedly
            if not tray_thread.is_alive() and not quit_event.is_set():
                logger.warning("Tray thread died — restarting.")
                tray_thread = threading.Thread(target=_run_tray, daemon=True)
                tray_thread.start()
                time.sleep(0.5)
            # Check if settings were requested
            if tray.settings_event.wait(timeout=0.5):
                tray.settings_event.clear()
                _open_settings(hotkey)
    except KeyboardInterrupt:
        pass
    finally:
        transcriber.stop_keepalive()
        hotkey.stop()
        quit_event.set()
        logger.info("sph2txt stopped.")


def _open_settings(hotkey_listener):
    """Open settings UI on the main thread (tkinter-safe)."""
    from src.ui import SettingsUI
    logger.info("Opening settings window.")

    def _activate():
        hotkey_listener.enabled = True

    def _deactivate():
        hotkey_listener.enabled = False

    ui = SettingsUI(
        on_activate=_activate,
        on_deactivate=_deactivate,
        initially_active=hotkey_listener.enabled,
    )
    ui.show()  # blocks until window is closed


if __name__ == "__main__":
    main()
