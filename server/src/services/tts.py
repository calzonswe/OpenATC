"""Text-to-Speech service using Piper TTS."""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger("openatc.tts")


class TTSService:
    """Multi-voice TTS using Piper.

    Loads voice models on first use and caches them.
    Outputs PCM 16-bit mono at configurable sample rate.
    """

    def __init__(self, voices_dir: str = "voices", sample_rate: int = 22050):
        self.voices_dir = Path(voices_dir)
        self.sample_rate = sample_rate
        self._voice_models: dict[str, Path] = {}
        self._voice_paths: dict[str, Path] = {}

    def _discover_voices(self):
        """Scan voices directory for .onnx files and map roles."""
        if not self.voices_dir.exists():
            logger.warning(f"Voices directory not found: {self.voices_dir}")
            return

        for onnx_file in self.voices_dir.glob("*.onnx"):
            # File format: role_voice.onnx (e.g., tower_kathleen.onnx)
            stem = onnx_file.stem  # e.g., "tower_kathleen"
            # Also look for corresponding .json config
            json_file = onnx_file.with_suffix(".json")
            if not json_file.exists():
                logger.warning(f"No config file for voice: {onnx_file}")
                continue

            # Extract role from filename (before first underscore)
            role = stem.split("_")[0] if "_" in stem else stem
            self._voice_models[role] = onnx_file
            logger.info(f"Discovered voice '{role}': {onnx_file.name}")

    def get_available_roles(self) -> list[str]:
        """Return list of available voice roles (e.g., tower, center)."""
        if not self._voice_models:
            self._discover_voices()
        return list(self._voice_models.keys())

    def _synthesize_sync(self, text: str, role: str) -> Optional[bytes]:
        """Synchronous Piper TTS call (used internally by async wrapper)."""
        model_path = self._voice_models.get(role)
        if model_path is None:
            if self._voice_models:
                model_path = next(iter(self._voice_models.values()))
                logger.warning(f"No voice for role '{role}', using {model_path.name}")
            else:
                logger.error(f"No Piper voices found in {self.voices_dir}")
                return None

        json_path = model_path.with_suffix(".json")
        try:
            result = subprocess.run(
                [
                    "piper",
                    "--model", str(model_path),
                    "--config", str(json_path),
                    "--output-raw",
                    "--output-type", "raw",
                ],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"Piper TTS failed (role={role}): {result.stderr.decode()}")
                return None
            return result.stdout
        except FileNotFoundError:
            logger.error("Piper TTS not found in PATH. Install from https://github.com/rhasspy/piper")
            return None
        except subprocess.TimeoutExpired:
            logger.error(f"Piper TTS timed out (role={role})")
            return None
        except Exception as e:
            logger.error(f"Piper TTS error (role={role}): {e}")
            return None

    async def synthesize(self, text: str, role: str = "center") -> Optional[bytes]:
        """Synthesize text to PCM audio using Piper (non-blocking).

        Runs the Piper subprocess in a thread executor to avoid blocking
        the asyncio event loop.

        Args:
            text: Text to speak
            role: ATC role voice to use (tower, center, approach, etc.)

        Returns:
            Raw PCM 16-bit mono audio bytes, or None on failure
        """
        if not self._voice_models:
            self._discover_voices()

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._synthesize_sync, text, role)

    async def synthesize_to_wav(self, text: str, role: str = "center") -> Optional[bytes]:
        """Synthesize text to WAV bytes (with header)."""
        raw = await self.synthesize(text, role)
        if raw is None:
            return None

        import wave
        import io

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(self.sample_rate)
            wav.writeframes(raw)

        return buf.getvalue()
