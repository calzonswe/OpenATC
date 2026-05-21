<p align="center">
  <img src="https://img.shields.io/badge/status-alpha-yellow" alt="Status: Alpha"/>
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"/>
  <img src="https://img.shields.io/badge/python-3.12+-brightgreen" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/.NET-8.0-purple" alt=".NET 8"/>
  <img src="https://img.shields.io/badge/ollama-qwen2.5:7b-orange" alt="LLM: qwen2.5:7b"/>
</p>

<h1 align="center">✈️ OpenATC</h1>
<p align="center"><strong>AI-driven Air Traffic Control for Microsoft Flight Simulator</strong></p>
<p align="center">
  Speak to ATC naturally via PTT. The AI transcribes your transmission, understands your aircraft state, and responds with correct ICAO phraseology — in real time.
</p>

---

## Overview

OpenATC is a client-server system that brings AI-controlled air traffic control to MSFS 2020/2024.

| Component | What it does | Runs on |
|---|---|---|
| **Client** (WPF / C#) | PTT button, mic capture, SimConnect telemetry, audio playback | Gaming PC (Windows) |
| **Server** (Python / FastAPI) | Speech-to-text (Whisper), LLM reasoning (Ollama), Text-to-speech (Piper), nav database, trigger evaluation | Ubuntu server (or any Linux with Docker) |

The server handles all intelligence. The client is a thin relay that sends audio + telemetry and receives ATC responses.

### Key features

- 🎙️ **Push-to-talk** — keyboard or joystick button
- 🧠 **LLM-powered ATC** — qwen2.5:7b via Ollama understands context, altitude, heading, and flight phase
- 🗣️ **6 distinct ATC voices** — Delivery, Ground, Tower, Departure, Center, Approach (Piper TTS)
- 🌍 **European phraseology** — auto-adapts per country (DE, GB, FR, ES, IT) with correct QNH, transition altitudes, and callsign formats
- 🚦 **Proactive ATC** — server pushes altitude corrections, handoffs, approach clearances, squawk codes, and emergency handling
- 📡 **Real-time telemetry** — position, altitude, heading, speed, transponder — polled from SimConnect every 3 seconds
- 🗺️ **Built-in nav database** — 85,000+ airports, 48,000 runways, COM frequencies from OurAirports
- 🐳 **Docker Compose** — one-command server deployment

---

## Getting Started

### 1. Server (Ubuntu / Linux)

```bash
git clone https://github.com/calzonswe/OpenATC.git
cd OpenATC
bash setup.sh           # detects GPU, installs nvidia-container-toolkit if needed
bash run.sh             # starts Docker Compose — downloads models on first run
```

That's it. The first start downloads:
- The OpenATC server image (built from source)
- 6 Piper TTS voice models (~50 MB each)
- qwen2.5:7b LLM model from Ollama (~4 GB)

**First-time startup takes 2-5 minutes.** Subsequent starts are instant.

Verify:
```bash
curl http://localhost:8765/health
# → {"status":"ok","connections":0,"nav_airports":85193}
```

#### Port configuration

```bash
SERVER_PORT=8888 bash run.sh
```

#### GPU support

`setup.sh` auto-detects Nvidia GPUs and installs `nvidia-container-toolkit` (asks for `sudo`). On CPU-only hardware, the server falls back gracefully — slower but fully functional.

---

### 2. Client (Windows)

**Prerequisites:** Windows 10/11, Microsoft Flight Simulator 2020 or 2024, .NET 8 Desktop Runtime.

1. Download `OpenATC.Client.exe` from the [Releases](https://github.com/calzonswe/OpenATC/releases) page
2. Launch the client, click **Settings**
3. Set:
   - **Server Address** — IP of your Ubuntu server (e.g., `192.168.1.100`)
   - **Callsign** — your aircraft callsign (e.g., `DAL123`)
   - **PTT Key** — press a key to bind it
4. Start MSFS, then start the client

Press and hold PTT to speak. Release to hear the ATC response.

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Ubuntu Server                                   │
│                                                  │
│  ┌──────────────────────────────────────────────┐│
│  │  Docker Compose                              ││
│  │                                              ││
│  │  ┌──────────────┐    ┌──────────────────┐   ││
│  │  │   Ollama     │    │  openatc-server  │   ││
│  │  │ qwen2.5:7b  │◄───│  - Whisper STT   │   ││
│  │  │              │    │  - Piper TTS     │   ││
│  │  │  GPU prefer  │    │  - Nav DB        │   ││
│  │  └──────────────┘    │  - Triggers      │   ││
│  │                      └────────┬─────────┘   ││
│  │                        :8765  │              ││
│  └────────────────────────────────┼─────────────┘│
└───────────────────────────────────┼──────────────┘
                                    │
                           ┌────────▼─────────┐
                           │  Gaming PC       │
                           │  (Windows)       │
                           │                  │
                           │  MSFS + SimCon   │
                           │  OpenATC Client  │
                           └──────────────────┘
```

### WebSocket Protocol

```
Client → Server:
  • register     — callsign registration
  • telemetry    — position/altitude/heading (every 3s)
  • audio_start  — PTT pressed
  • audio_frame  — Opus-encoded 16kHz PCM (binary)
  • audio_end    — PTT released

Server → Client:
  • registered   — confirmation
  • atc_text     — LLM response (streamed tokens)
  • atc_audio_*  — TTS playback (bracketed binary)
  • push_instruction — unsolicited ATC (altitude correction, handoff, etc.)
  • error        — processing failure
```

Full protocol spec: [`docs/protocol.md`](docs/protocol.md)

---

## ATC Capabilities

### Roles (6 voices)

| Role | When used |
|---|---|
| Delivery | Pre-flight clearance at departure airport |
| Ground | Taxi instructions (on ground) |
| Tower | Takeoff/landing clearance (below 500 ft, within airport vicinity) |
| Departure | Initial climb after takeoff (up to FL100) |
| Center | En-route (above FL100, between airports) |
| Approach | Arrival sequencing (within 40 nm of destination, below FL200) |

### Server-initiated triggers (10 automatic conditions)

| Trigger | Example |
|---|---|
| Emergency squawk 7700 | "DAL123, squawk 7700, state your emergency" |
| Altitude deviation (>200 ft) | "DAL123, correct altitude FL350, you are at FL347" |
| Heading deviation (>10°) | "DAL123, turn left heading 270" |
| Departure handoff (above FL100) | "DAL123, contact Departure 119.250" |
| Approach handoff (40 nm, below FL200) | "DAL123, contact Approach 124.300" |
| Tower handoff (10 nm, below 5000 ft) | "DAL123, contact Tower 118.700" |
| ILS approach clearance (5 nm final) | "DAL123, cleared ILS approach, Runway 26R" |
| Squawk code assignment (first contact) | "DAL123, squawk 4721" |
| Airspace infringement | "DAL123, you are entering class C airspace" |
| Mayday/Pan-Pan detection | "DAL123, MAYDAY acknowledged, frequency clear" |

### Country-specific phraseology

| Country | Callsign | Transition alt | QNH |
|---|---|---|---|
| 🇩🇪 Germany | "München Radar" | FL100 | hPa |
| 🇬🇧 UK | "London Control" | 6000 ft | hPa |
| 🇫🇷 France | "Paris Approche" | FL60/FL100 | hPa |
| 🇪🇸 Spain | "Madrid Control" | FL130 | hPa |
| 🇮🇹 Italy | "Roma Control" | FL100 | hPa |

---

## Configuration

### Server (`server/config.toml`)

```toml
[server]
host = "0.0.0.0"
port = 8765

[models]
stt_model = "base"          # tiny, base, small, medium, large
llm_model = "qwen2.5:7b"
llm_host = "http://ollama:11434"

[atc]
trigger_cooldown = 15.0     # seconds between pushes
history_window = 15         # exchanges kept for LLM context
```

Override via environment variables:

| Env var | Overrides |
|---|---|
| `LLM_HOST` | `models.llm_host` |
| `LLM_MODEL` | `models.llm_model` |
| `SERVER_PORT` | `server.port` |

### Client (`settings.json`)

Saved alongside the EXE. Edit via the **Settings** window or directly:

```json
{
  "server_address": "192.168.1.100",
  "server_port": 8765,
  "callsign": "DAL123",
  "ptt_key": "LeftControl"
}
```

---

## Performance

| Scenario | With GPU (8GB+ VRAM) | CPU-only |
|---|---|---|
| Whisper transcription | 1-2s | 5-15s |
| LLM response (qwen2.5:7b) | 2-5s | 10-30s |
| TTS synthesis | 0.2-0.5s | 0.2-0.5s |
| **End-to-end (PTT release → audio)** | **~4-8s** | **~15-45s** |

TTS is always fast. The GPU benefit is in Whisper (batch size) and Ollama (prompt processing). A dedicated server GPU is recommended for the best experience.

---

## Development

```bash
# Server (without Docker)
cd server
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install faster-whisper ollama
python scripts/download_voices.py
uvicorn src.main:app --reload --port 8765

# Tests
pytest tests/
```

```bash
# Client (Windows, requires .NET 8 SDK)
cd client/OpenATC.Client
dotnet build
dotnet run
```

---

## License

MIT

---

## Disclaimer

OpenATC is a hobby project for flight simulation. It does **not** provide real-world air traffic control services. Do not use for actual aviation.
