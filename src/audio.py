"""
sph2txt — Microphone audio capture.

Captures audio from the default microphone via sounddevice.
Records at the device's native sample rate (+48 kHz typically),
then resamples to 16 kHz mono float32 for Whisper.
"""

import logging
import threading

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)

WHISPER_RATE = 16_000  # Whisper's required sample rate
DTYPE = "float32"


class AudioRecorder:
    """Records microphone audio into an in-memory numpy buffer."""

    def __init__(self):
        self._chunks: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()
        self._recording = False
        self._device_rate: int = WHISPER_RATE

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
            self._stream = sd.InputStream(
                device=device,
                samplerate=self._device_rate,
                channels=1,
                dtype=DTYPE,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._recording = True
            logger.info("Recording started (device=%s, rate=%d Hz).",
                        dev_info["name"], self._device_rate)

    def stop(self) -> np.ndarray:
        """Stop recording and return 16 kHz mono float32 audio for Whisper."""
        with self._lock:
            if not self._recording:
                return np.array([], dtype=np.float32)
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._recording = False

        if not self._chunks:
            logger.warning("No audio captured.")
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

    @staticmethod
    def _resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        """Resample audio using linear interpolation (no extra deps)."""
        ratio = dst_rate / src_rate
        n_samples = int(len(audio) * ratio)
        indices = np.arange(n_samples) / ratio
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

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
