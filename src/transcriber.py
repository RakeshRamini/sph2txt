"""
sph2txt — Whisper inference engine.

Loads the faster-whisper model once and keeps it in GPU memory.
Provides a transcribe(audio_buffer) method that returns text.
Uses project-local model cache (models/huggingface/).
Supports warmup, sleep (unload), and resume (reload).
"""

import logging
import threading
import time

import numpy as np
from faster_whisper import WhisperModel

from src.config import resolve_path

logger = logging.getLogger(__name__)

WARMUP_DURATION = 0.5  # seconds of silence for warmup
WARMUP_RATE = 16_000


class Transcriber:
    """Loads and holds the Whisper model, exposes transcribe()."""

    def __init__(self, config: dict):
        self._config = config
        self._lock = threading.Lock()
        self._model: WhisperModel | None = None
        self._keepalive_timer: threading.Timer | None = None
        self._keepalive_running = False
        self._load_model(config)

    def _load_model(self, config: dict) -> None:
        model_name = config.get("model", "large-v3-turbo")
        device = config.get("device", "cuda")
        compute_type = config.get("compute_type", "float16")
        download_root = resolve_path(config, "model_cache")

        logger.info(
            "Loading model '%s' on %s (%s) → cache: %s",
            model_name, device, compute_type, download_root,
        )

        self._model = WhisperModel(
            model_name,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )
        self._beam_size = config.get("beam_size", 3)
        self._language = config.get("language", "en")
        self._vad_filter = config.get("vad_filter", True)

        logger.info("Model loaded successfully.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def warmup(self) -> None:
        """Run a dummy inference to warm up CUDA JIT caches."""
        if not self._model:
            return
        logger.info("Warming up model (%.1fs silent audio)...", WARMUP_DURATION)
        silent = np.zeros(int(WARMUP_RATE * WARMUP_DURATION), dtype=np.float32)
        try:
            segments, _ = self._model.transcribe(
                silent, beam_size=1, language=self._language, vad_filter=False,
            )
            # Consume the generator to force execution
            for _ in segments:
                pass
        except Exception:
            logger.debug("Warmup inference produced no output (expected).")
        logger.info("Model warmup complete.")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a numpy audio array (float32, 16 kHz, mono) to text.

        Returns the concatenated text segments stripped and joined.
        """
        with self._lock:
            if not self._model:
                raise RuntimeError("Model is not loaded (app may be in sleep mode).")
            # Reset keepalive timer on real usage
            self._reset_keepalive()

            segments, info = self._model.transcribe(
                audio,
                beam_size=self._beam_size,
                language=self._language,
                vad_filter=self._vad_filter,
            )

            text = " ".join(seg.text.strip() for seg in segments)
        logger.debug(
            "Transcribed %.1fs audio → %d chars (lang=%s, prob=%.2f)",
            info.duration, len(text), info.language, info.language_probability,
        )
        return text

    # ------------------------------------------------------------------
    # Sleep / Resume
    # ------------------------------------------------------------------

    def unload(self) -> None:
        """Unload model from GPU memory (sleep mode)."""
        with self._lock:
            self.stop_keepalive()
            if self._model is not None:
                del self._model
                self._model = None
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass
                logger.info("Model unloaded from GPU (sleep mode).")

    def reload(self) -> None:
        """Reload model into GPU memory (resume from sleep)."""
        with self._lock:
            if self._model is not None:
                return
        logger.info("Reloading model (resume from sleep)...")
        self._load_model(self._config)
        self.warmup()
        self.start_keepalive()

    # ------------------------------------------------------------------
    # GPU Keepalive
    # ------------------------------------------------------------------

    def start_keepalive(self) -> None:
        """Start the periodic GPU keepalive timer."""
        if not self._config.get("gpu_keepalive", True):
            logger.info("GPU keepalive is disabled by config.")
            return
        self._keepalive_running = True
        self._schedule_keepalive()
        logger.info("GPU keepalive started (interval=%ds).",
                     self._config.get("keepalive_interval_sec", 180))

    def stop_keepalive(self) -> None:
        """Stop the GPU keepalive timer."""
        self._keepalive_running = False
        if self._keepalive_timer is not None:
            self._keepalive_timer.cancel()
            self._keepalive_timer = None

    def _schedule_keepalive(self) -> None:
        if not self._keepalive_running:
            return
        interval = self._config.get("keepalive_interval_sec", 180)
        self._keepalive_timer = threading.Timer(interval, self._keepalive_pulse)
        self._keepalive_timer.daemon = True
        self._keepalive_timer.start()

    def _reset_keepalive(self) -> None:
        """Reset the keepalive timer after real usage."""
        if self._keepalive_running:
            if self._keepalive_timer is not None:
                self._keepalive_timer.cancel()
            self._schedule_keepalive()

    def _keepalive_pulse(self) -> None:
        """Run a tiny dummy inference to keep the GPU context warm."""
        with self._lock:
            if not self._model or not self._keepalive_running:
                return
            try:
                silent = np.zeros(int(WARMUP_RATE * 0.1), dtype=np.float32)
                segments, _ = self._model.transcribe(
                    silent, beam_size=1, language=self._language, vad_filter=False,
                )
                for _ in segments:
                    pass
                logger.debug("GPU keepalive pulse completed.")
            except Exception:
                logger.debug("GPU keepalive pulse failed (non-critical).")
        self._schedule_keepalive()
