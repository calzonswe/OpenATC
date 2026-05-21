"""Speech-to-Text service using faster-whisper."""

import logging
import subprocess
import tempfile
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

    def _decode_opus_to_pcm(self, opus_data: bytes) -> bytes:
        """Decode Opus bytes to raw PCM 16-bit mono 16kHz using ffmpeg."""
        with tempfile.NamedTemporaryFile(suffix=".opus") as tmp:
            tmp.write(opus_data)
            tmp.flush()
            try:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp.name,
                     "-f", "s16le", "-acodec", "pcm_s16le",
                     "-ar", "16000", "-ac", "1",
                     "-loglevel", "error", "pipe:1"],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    logger.error(f"ffmpeg Opus decode failed: {result.stderr.decode()}")
                    return opus_data  # fallback — may produce garbage
                return result.stdout
            except FileNotFoundError:
                logger.warning("ffmpeg not found, passing raw Opus to Whisper")
                return opus_data

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe audio to text.

        Accepts Opus-encoded bytes (from client) or raw PCM 16-bit mono.
        If input is Opus, decodes via ffmpeg first.

        Args:
            audio_bytes: Opus or raw PCM 16-bit mono audio data
            sample_rate: Expected sample rate of the audio (default 16000)

        Returns:
            Transcribed text string
        """
        self._load_model()

        import numpy as np

        # Try to detect Opus header and decode
        if len(audio_bytes) > 3 and audio_bytes[:3] == b"Ogg":
            pcm = self._decode_opus_to_pcm(audio_bytes)
        else:
            pcm = audio_bytes

        # Convert bytes to float32 array (faster-whisper expects [-1, 1] float32)
        audio_int16 = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
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
