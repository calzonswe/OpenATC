# OpenATC — Agent Guide

## Project structure

Monorepo with two independent deployable components:

- `server/` — Python 3.12+ FastAPI server (primary dev area). All core logic: WebSocket handler, STT/LLM/TTS services, nav DB, triggers.
- `client/` — C# .NET 8 WPF app (Windows-only, requires MSFS + SimConnect). Thin relay: mic capture + telemetry → ATC audio/via WebSocket.

## Server commands (run from `server/`)

```bash
# Install
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
pip install faster-whisper ollama  # optional ML deps, lazy-loaded at runtime

# Voice models (auto-downloads or skip if cached)
python scripts/download_voices.py

# Run dev server
uvicorn src.main:app --reload --port 8765

# Test (all 33 tests)
PYTHONPATH=. pytest tests/ -v

# Single test file
PYTHONPATH=. pytest tests/test_nav.py -v
```

## Key architecture facts

- **Entrypoint:** `server/src/main.py:app` — FastAPI with two startup events (service init, trigger loop), one WebSocket endpoint at `/ws`, one health endpoint at `/health`.
- **Config:** `server/config.toml` loaded by `src/config.py:Settings.from_toml()`. Env vars override: `LLM_HOST`, `LLM_MODEL`, `SERVER_PORT`, `SERVER_HOST`, `STT_MODEL`.
- **Services lazy-loaded** on startup in `_init_services()` (nav → stt → llm → tts → atc_session → trigger_evaluator). Each ML service loads its model on first call, not at init.
- **WebSocket protocol:** JSON text frames for control messages, raw binary frames for audio. No base64. Audio flow: `audio_start` (text) → binary Opus frames → `audio_end` (text) triggers async `process_audio_for_callsign()` → `atc_text` + binary PCM TTS frames.
- **Audio:** Client sends Opus-encoded 16kHz 16-bit mono. Server sends raw PCM 22050Hz 16-bit mono (Piper output). No Opus decode on server side — current code passes raw Opus to Whisper which expects PCM (a bug vector: need to decode Opus → PCM before STT).
- **Nav database:** `src/services/nav.py` — reads static CSVs from `server/data/` (tracked, ~18MB total). Provides haversine-based spatial queries. No SQLite.
- **Triggers:** 10 conditions evaluated every 5s in background `trigger_loop()`. 15s cooldown per callsign between pushes. Priority order: emergency → altitude → heading → airspace → approach → tower → clearance → departure → squawk.
- **ATC role detection** (`atc_session.py:determine_role`): delivery (no history, on ground) → ground (on ground) → tower (<500ft near airport) → departure (<10000ft near origin) → approach (<20000ft within 40nm of dest) → center (default).

## Phraseology system

- Country procedures: plain Markdown files in `src/prompts/procedures/{country_code}.md`.
- Country resolved from nearest airport via nav DB, injected into LLM system prompt on every exchange.
- To add a country: create `xx.md` in `src/prompts/procedures/` and it is auto-discovered.

## Docker deployment

- `docker-compose.yml` — 2 containers (ollama + openatc-server), shared volumes for models.
- `docker-compose.gpu.yml` — overlay that adds Nvidia device reservation (applied by `run.sh`).
- `setup.sh` — run once: detects GPU, optionally installs nvidia-container-toolkit, writes `run.sh`.
- `server/Dockerfile` — multi-stage build: downloads Piper binary, installs Python deps, copies nav data.
- Entrypoint (`scripts/entrypoint.sh`): auto-downloads TTS voices → waits for Ollama health → pulls LLM model → starts uvicorn.

## Non-obvious

- `faster-whisper` and `ollama` packages are **not** in `requirements.txt`. Install manually for local dev. The Docker image installs them via a commented section that must be uncommented or the pip install must be added.
- CSVs in `server/data/` are tracked in git (not `.gitignore`d) and must be updated if nav coverage changes.
- Piper TTS runs via `subprocess.run(["piper", ...])` in the Docker container, not as a Python library. Requires the `piper` binary on PATH.
- The client project requires .NET 8 Desktop Runtime (not just Console) and the `Microsoft.FlightSimulator.SimConnect` NuGet package which only resolves on Windows.
- The `IMPLEMENTATION_PLAN.md` is a historical design document, not a living task tracker. Consult `AGENTS.md` for workflow, not the plan.
