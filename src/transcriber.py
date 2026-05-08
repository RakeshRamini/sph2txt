"""
sph2txt — Whisper inference engine.

Loads the faster-whisper model once and keeps it in GPU memory.
Provides a transcribe(audio_buffer) method that returns text.
Uses project-local model cache (models/huggingface/).
"""

import logging
import numpy as np
from faster_whisper import WhisperModel

from src.config import resolve_path

logger = logging.getLogger(__name__)


class Transcriber:
    """Loads and holds the Whisper model, exposes transcribe()."""

    def __init__(self, config: dict):
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
        self._beam_size = config.get("beam_size", 5)
        self._language = config.get("language", "en")
        self._vad_filter = config.get("vad_filter", True)

        logger.info("Model loaded successfully.")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a numpy audio array (float32, 16 kHz, mono) to text.

        Returns the concatenated text segments stripped and joined.
        """
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
