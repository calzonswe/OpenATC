"""Speech-to-Text service using faster-whisper."""

import logging
from typing import Optional

logger = logging.getLogger("openatc.stt")


class STTService:
    """Transcribes audio using faster-whisper.

    Model is loaded lazily on first call to avoid consuming VRAM on startup.
    """

    def __init__(self, model_name: str = "base", language: str = "en"):
        self.model_name = model_name
        self.language = language
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel
            logger.info(f"Loading Whisper model: {self.model_name}")
            self._model = WhisperModel(self.model_name, device="auto", compute_type="auto")
            logger.info("Whisper model loaded")
        except ImportError:
            logger.error(
                "faster-whisper not installed. Install with: "
                "pip install faster-whisper"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe PCM 16-bit mono audio to text.

        Args:
            audio_bytes: Raw PCM 16-bit mono audio data
            sample_rate: Sample rate of the audio (default 16000)

        Returns:
            Transcribed text string
        """
        self._load_model()

        import numpy as np

        # Convert bytes to float32 array (faster-whisper expects [-1, 1] float32)
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        audio_float32 = audio_int16 / 32768.0

        segments, info = self._model.transcribe(
            audio_float32,
            language=self.language,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=300,
                threshold=0.5,
            ),
        )

        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        return " ".join(text_parts)

    def unload(self):
        """Unload model from memory to free VRAM."""
        self._model = None
        logger.info("Whisper model unloaded")
