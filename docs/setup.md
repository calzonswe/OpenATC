# OpenATC — Setup Guide

## Prerequisites

| Component | Requirement |
|---|---|
| **Server** | Ubuntu 22.04+ (or any Linux with Docker), optionally with Nvidia GPU |
| **Client** | Windows 10/11 with Microsoft Flight Simulator 2020/2024 |
| **Network** | Both machines on the same LAN (or VPN) |

## Server Setup (Ubuntu)

### 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in, or run: newgrp docker
```

### 2. Clone and run setup

```bash
git clone https://github.com/your-org/OpenATC.git
cd OpenATC
bash setup.sh
```

The setup script will:
- Detect Nvidia GPU
- Install `nvidia-container-toolkit` if needed (asks for sudo)
- Write a `run.sh` script with the correct Docker Compose command

### 3. Start the server

```bash
bash run.sh
```

First start will download:
- The OpenATC server Docker image (built from source)
- TTS voice models (~300MB, 6 voices)
- Ollama LLM model (qwen2.5:7b, ~4GB)

This takes 2-5 minutes depending on your internet connection.

### 4. Verify it's running

```bash
curl http://localhost:8765/health
```

Response: `{"status":"ok","connections":0,"nav_airports":85000}`

### Port configuration

Default port is 8765. Override with:

```bash
SERVER_PORT=8888 bash run.sh    # Start on port 8888
```

---

## Client Setup (Windows)

### 1. Install .NET 8 Runtime

Download from: https://dotnet.microsoft.com/en-us/download/dotnet/8.0/runtime

You need the **Desktop Runtime** (not just the Console runtime), because the client is a WPF app.

### 2. Download the client

Grab `OpenATC.Client.exe` from the latest release, or build from source:

```bash
# On Windows with .NET 8 SDK
cd client/OpenATC.Client
dotnet publish -r win-x64 --self-contained true -p:PublishSingleFile=true
# Output: bin/Release/net8.0-windows/win-x64/publish/OpenATC.Client.exe
```

### 3. Configure

Launch the client. Click **Settings** and set:

| Field | Value |
|---|---|
| Server Address | IP address of the Ubuntu server (e.g., `192.168.1.100`) |
| Server Port | `8765` (default) |
| Callsign | Your aircraft callsign (e.g., `DAL123`) |
| PTT Key | Press a key to bind (e.g., `LeftControl`) |
| Joystick | Optional — select your joystick and button |
| Audio Device | Your microphone |

### 4. Connect

Start Microsoft Flight Simulator, then start the client. It will automatically connect to SimConnect and the OpenATC server.

Press and hold PTT to speak. Release to hear the ATC response.

---

## Architecture

```
                    ┌──────────────────────┐
                    │   Gaming PC (Win)    │
                    │                      │
                    │  MSFS + SimConnect   │
                    │  OpenATC.Client.exe  │
                    └──────────┬───────────┘
                               │ WebSocket :8765
                               │ Telemetry / Audio
                    ┌──────────▼───────────┐
                    │   Ubuntu Server      │
                    │                      │
                    │  ┌──────────────┐    │
                    │  │ openatc-server│    │
                    │  │ - Whisper STT │    │
                    │  │ - Piper TTS  │    │
                    │  │ - Nav DB     │    │
                    │  │ - Triggers   │    │
                    │  └──────┬───────┘    │
                    │         │            │
                    │  ┌──────▼───────┐    │
                    │  │  Ollama      │    │
                    │  │ qwen2.5:7b   │    │
                    │  └──────────────┘    │
                    └─────────────────────┘
```

---

## Docker Management

```bash
# View logs
docker compose logs -f openatc-server
docker compose logs -f ollama

# Stop
docker compose down

# Update to latest
git pull
docker compose build openatc-server
bash run.sh

# Full reset (deletes volumes)
docker compose down -v
```

## Performance Notes

| Component | With GPU | CPU-only |
|---|---|---|
| Whisper STT | ~1-2s | ~5-15s |
| Ollama LLM | ~2-5s | ~10-30s |
| Piper TTS | ~0.5s | ~0.5s |
| End-to-end latency | ~4-8s | ~15-45s |

TTS is always fast — it's the LLM inference that benefits most from a GPU. A dedicated Nvidia GPU with 8GB+ VRAM is recommended.
