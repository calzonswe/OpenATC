"""Speech-to-Text service using faster-whisper."""

import logging
import struct
import subprocess
import tempfile
import zlib
from typing import Union

logger = logging.getLogger("openatc.stt")


def _raw_opus_to_ogg(frames: list[bytes], sample_rate: int = 16000) -> bytes:
    """Wrap raw Opus frames into a valid Ogg Opus container.

    Accepts individual Opus packets (as sent by the client) and produces
    a complete Ogg bitstream that ffmpeg can decode.

    Args:
        frames: List of raw Opus packet bytes (60ms each).
        sample_rate: Input sample rate (used for OpusHead header only).

    Returns:
        Complete Ogg Opus byte stream.
    """
    serial = 0x4F504E  # "OPN" — arbitrary serial
    frame_samples = 2880  # 60 ms at 48 kHz (Opus internal rate)

    def _page(packets: list[bytes], header_type: int,
              granule: int, seq: int) -> bytes:
        body = b"".join(packets)
        seg_table = bytearray()
        for p in packets:
            remaining = len(p)
            while remaining > 255:
                seg_table.append(255)
                remaining -= 255
            seg_table.append(remaining)

        hdr = b"OggS"
        hdr += struct.pack("B", 0)
        hdr += struct.pack("B", header_type)
        hdr += struct.pack("<q", granule)
        hdr += struct.pack("<I", serial)
        hdr += struct.pack("<I", seq)
        hdr += struct.pack("<I", 0)
        hdr += struct.pack("B", len(seg_table))
        hdr += bytes(seg_table)

        crc = zlib.crc32(hdr + body) & 0xFFFFFFFF
        hdr = hdr[:22] + struct.pack("<I", crc) + hdr[26:]
        return hdr + body

    out = bytearray()

    # Page 0: OpusHead (ID header)
    id_packet = b"OpusHead"
    id_packet += struct.pack("B", 1)          # version
    id_packet += struct.pack("B", 1)          # output channel count
    id_packet += struct.pack("<H", 0)         # pre-skip (0 for streaming)
    id_packet += struct.pack("<I", sample_rate)  # input sample rate
    id_packet += struct.pack("<h", 0)         # output gain
    id_packet += struct.pack("B", 0)          # channel mapping family
    out.extend(_page([bytes(id_packet)], 0x02, 0, 0))

    # Page 1: OpusTags (comment header)
    vendor = "OpenATC"
    comment_pkt = b"OpusTags"
    comment_pkt += struct.pack("<I", len(vendor))
    comment_pkt += vendor.encode()
    comment_pkt += struct.pack("<I", 0)      # user comment count
    out.extend(_page([bytes(comment_pkt)], 0x00, 0, 1))

    # Audio pages
    granule = 0
    for i, frame in enumerate(frames):
        granule += frame_samples
        hdr_type = 0x04 if i == len(frames) - 1 else 0x00
        out.extend(_page([frame], hdr_type, granule, i + 2))

    return bytes(out)


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
        """Decode Opus bytes to raw PCM 16-bit mono 16kHz using ffmpeg.

        Handles both Ogg-wrapped Opus and raw Opus packets (from client).
        """
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
                    logger.error(f"ffmpeg decode failed: {result.stderr.decode()}")
                    return b""
                return result.stdout
            except FileNotFoundError:
                logger.warning("ffmpeg not found, cannot decode Opus audio")
                return b""

    @staticmethod
    def _is_opus_data(data: bytes) -> bool:
        """Heuristic: check if data looks like raw Opus packets.

        Raw Opus packets start with a TOC byte where the top 3 bits
        (code) are 0-3 for various frame types. We check the first byte.
        """
        if not data:
            return False
        toc = data[0]
        config = toc >> 3
        # Valid Opus packet config values: 0..15 (mono) or 16..31 (stereo)
        return config <= 31

    def transcribe(self, audio: Union[bytes, list[bytes]], sample_rate: int = 16000) -> str:
        """Transcribe audio to text.

        Accepts raw Opus packets (as a list of frame bytes from the client),
        Ogg-wrapped Opus, or raw PCM 16-bit mono. Opus is decoded via ffmpeg.

        Args:
            audio: Raw PCM 16-bit mono bytes, or a list of raw Opus frame bytes.
            sample_rate: Expected sample rate of PCM audio (default 16000).

        Returns:
            Transcribed text string.
        """
        self._load_model()
        import numpy as np

        if isinstance(audio, list):
            if not audio:
                return ""
            if self._is_opus_data(audio[0]):
                ogg_data = _raw_opus_to_ogg(audio)
                pcm = self._decode_opus_to_pcm(ogg_data)
            else:
                pcm = b"".join(audio)
        elif len(audio) > 3 and audio[:3] == b"Ogg":
            pcm = self._decode_opus_to_pcm(audio)
        elif self._is_opus_data(audio):
            ogg_data = _raw_opus_to_ogg([audio])
            pcm = self._decode_opus_to_pcm(ogg_data)
        else:
            pcm = audio

        if not pcm:
            logger.warning("No PCM data to transcribe")
            return ""

        audio_int16 = np.frombuffer(pcm, dtype=np.int16).astype(np.float32)
        audio_float32 = audio_int16 / 32768.0

        segments, _ = self._model.transcribe(
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
