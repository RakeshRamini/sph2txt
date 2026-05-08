"""
sph2txt — Main entry point and orchestrator.

Initializes all components and runs the application loop:
  1. Load config
  2. Initialize Whisper model (GPU)
  3. Start system tray
  4. Listen for hotkey
  5. On trigger: capture audio → transcribe → inject text
"""

import logging
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

logger = logging.getLogger(__name__)


def main():
    """Application entry point."""
    # --- Single-instance lock ---
    lock_path = os.path.join(_project_root, ".sph2txt.lock")
    try:
        _lock_fh = open(lock_path, "w")
        import msvcrt
        msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
    except (OSError, IOError):
        print("sph2txt is already running.")
        return

    # --- Logging ---
    config = load_config()
    log_dir = resolve_path(config, "log_dir")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "sph2txt.log"),
                                encoding="utf-8"),
        ],
    )
    logger.info("sph2txt starting...")

    # --- Components ---
    transcriber = Transcriber(config)
    recorder = AudioRecorder()
    quit_event = threading.Event()
    tray = TrayIcon(on_quit=quit_event)

    # --- Pipeline callbacks ---
    def on_hotkey_press():
        tray.set_state("recording")
        recorder.start()

    def on_hotkey_release():
        audio = recorder.stop()
        if len(audio) == 0:
            logger.warning("No audio captured, skipping.")
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

    # --- System tray (blocks until quit) ---
    logger.info("Ready. Press Alt+X to speak.")
    try:
        tray.start()  # blocks here
    except KeyboardInterrupt:
        pass
    finally:
        hotkey.stop()
        quit_event.set()
        logger.info("sph2txt stopped.")


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
