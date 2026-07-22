"""
sph2txt — Microphone audio capture.

Captures audio from the default microphone via sounddevice.
Records at the device's native sample rate (+48 kHz typically),
then resamples to 16 kHz mono float32 for Whisper.
Supports high-quality soxr resampling with np.interp fallback.
"""

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

WHISPER_RATE = 16_000  # Whisper's required sample rate
DTYPE = "float32"

# Try to import soxr for high-quality resampling
try:
    import soxr as _soxr
    _HAS_SOXR = True
    logger.debug("soxr available — using high-quality resampling.")
except ImportError:
    _soxr = None
    _HAS_SOXR = False


class AudioRecorder:
    """Records microphone audio into an in-memory numpy buffer."""

    def __init__(self, resampler: str = "soxr"):
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False
        self._device_rate: int = WHISPER_RATE
        self._use_soxr = (resampler == "soxr" and _HAS_SOXR)
        if resampler == "soxr" and not _HAS_SOXR:
            logger.warning("soxr requested but not installed; falling back to linear interpolation.")

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        """Start capturing audio from the default microphone."""
        with self._lock:
            if self._recording:
                return
            self._chunks.clear()
            device = self._find_input_device()
            # Use the device's native sample rate to avoid PortAudio errors
            dev_info = sd.query_devices(device)
            self._device_rate = int(dev_info["default_samplerate"])
            stream = sd.InputStream(
                device=device,
                samplerate=self._device_rate,
                channels=1,
                dtype=DTYPE,
                callback=self._audio_callback,
            )
            try:
                stream.start()
            except Exception:
                stream.close()
                raise
            self._stream = stream
            self._recording = True
            logger.info("Recording started (device=%s, rate=%d Hz).",
                        dev_info["name"], self._device_rate)

    def stop(self) -> np.ndarray:
        """Stop recording and return 16 kHz mono float32 audio for Whisper."""
        with self._lock:
            if not self._recording:
                return np.array([], dtype=np.float32)
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                logger.warning("Error closing audio stream.", exc_info=True)
            self._stream = None
            self._recording = False

        if not self._chunks:
            logger.warning("No audio chunks captured (stream may have failed to deliver data).")
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self._chunks, axis=0).flatten()
        self._chunks.clear()

        # Resample to 16 kHz if the device recorded at a different rate
        if self._device_rate != WHISPER_RATE:
            audio = self._resample(audio, self._device_rate, WHISPER_RATE)

        duration = len(audio) / WHISPER_RATE
        logger.info("Recording stopped. Captured %.1fs of audio.", duration)
        return audio

    def _audio_callback(self, indata: np.ndarray, frames: int,
                        time_info, status) -> None:
        """Called by sounddevice for each audio block."""
        if status:
            logger.warning("Audio stream status: %s", status)
        self._chunks.append(indata.copy())

    def _resample(self, audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """Resample audio using soxr (if available) or linear interpolation."""
        if self._use_soxr:
            return _soxr.resample(audio, src_rate, dst_rate).astype(np.float32)
        # Fallback: linear interpolation (introduces aliasing but works)
        ratio = dst_rate / src_rate
        n_samples = int(len(audio) * ratio)
        indices = np.arange(n_samples) / ratio
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    @staticmethod
    def is_silent(audio: np.ndarray, threshold: float = 0.001) -> bool:
        """Check if audio is effectively silence (RMS below threshold)."""
        if len(audio) == 0:
            return True
        rms = np.sqrt(np.mean(audio ** 2))
        return rms < threshold

    @staticmethod
    def _find_input_device() -> int | None:
        """Return the default input device, or the first available one."""
        default = sd.default.device[0]
        if default >= 0:
            return int(default)
        # No default set — pick the first device that has input channels
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                logger.info("No default input device; using '%s' (id=%d).",
                            dev["name"], i)
                return i
        raise RuntimeError("No audio input device found.")
