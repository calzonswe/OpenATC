#!/usr/bin/env python3
"""Download Piper TTS voice models for all ATC roles.

Downloads from HuggingFace or rhasspy/piper-voices releases.
"""

import json
import logging
import shutil
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("download_voices")

# Voice models per role — using Piper's default US English voices
# Source: https://huggingface.co/rhasspy/piper-voices/tree/main
VOICES = {
    "delivery": {
        "model": "en_US-lessac-medium.onnx",
        "config": "en_US-lessac-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium",
    },
    "ground": {
        "model": "en_US-libritts_r-medium.onnx",
        "config": "en_US-libritts_r-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/libritts_r/medium",
    },
    "tower": {
        "model": "en_US-ryan-medium.onnx",
        "config": "en_US-ryan-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium",
    },
    "departure": {
        "model": "en_US-joe-medium.onnx",
        "config": "en_US-joe-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/joe/medium",
    },
    "center": {
        "model": "en_US-ryan-medium.onnx",
        "config": "en_US-ryan-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/medium",
    },
    "approach": {
        "model": "en_US-lessac-medium.onnx",
        "config": "en_US-lessac-medium.onnx.json",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium",
    },
}


def download_file(url: str, dest: Path):
    """Download a file with progress indication."""
    logger.info(f"Downloading {dest.name}...")
    req = Request(url, headers={"User-Agent": "OpenATC/0.1"})
    try:
        with urlopen(req) as response:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = int(100 * downloaded / total)
                        sys.stdout.write(f"\r  {dest.name}: {pct}% ({downloaded // 1024}KB / {total // 1024}KB)")
                        sys.stdout.flush()
            print()
        logger.info(f"  Done: {dest.name}")
    except HTTPError as e:
        logger.error(f"  Failed to download {url}: {e}")


def main():
    voices_dir = Path("voices")
    voices_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading {len(VOICES)} voice models to {voices_dir.resolve()}")

    for role, info in VOICES.items():
        model_file = voices_dir / f"{role}_{info['model']}"
        config_file = voices_dir / f"{role}_{info['config']}"

        if model_file.exists() and config_file.exists():
            logger.info(f"  {role}: already downloaded, skipping")
            continue

        # Determine role prefix for filename
        model_url = f"{info['url']}/{info['model']}"
        config_url = f"{info['url']}/{info['config']}"

        download_file(model_url, model_file)
        download_file(config_url, config_file)

    logger.info("All voices downloaded!")
    logger.info(f"Available roles: {', '.join(VOICES.keys())}")


if __name__ == "__main__":
    main()
