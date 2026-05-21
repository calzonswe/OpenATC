# OpenATC — Implementation Plan

**Status: 2026-05-21 — 33 server tests passing, all core files written, Docker deployment ready**

| Phase | Status |
|---|---|
| Phase 0 — Server scaffolding | ✅ Done |
| Phase 0 — Client scaffolding | ✅ Done |
| Phase 1 — Nav database | ✅ Done |
| Phase 2 — Protocol & WS | ✅ Done |
| Phase 3 — Telemetry pipeline | ✅ Done |
| Phase 4/5 — STT+LLM+TTS services | ✅ Done |
| Phase 4/5 — ATC session orchestrator | ✅ Done |
| Phase 6 — Country phraseology | ✅ Done (5 countries) |
| Phase 7 — Server-initiated triggers | ✅ Done (10 trigger types) |
| Phase 8 — Client audio/UI | ✅ Done |
| Phase 9 — Prompt tuning | 🔄 Ongoing |
| Phase 10 — Packaging & docs | ✅ Done (Docker, setup.sh, protocol.md, setup.md) |

**What remains for production:**
- Build the Windows client with `dotnet build` (requires .NET 8 SDK on Windows)
- Tune the system prompt in `src/services/atc_session.py:build_system_prompt()`
- Add tests for ATC session and phraseology services

---

## 1. Repository Structure

```
OpenATC/
├── server/                          # Python FastAPI server
│   ├── src/
│   │   ├── main.py                  # Entry point, FastAPI app, WebSocket router
│   │   ├── config.py                # Pydantic config (port, model names, voice dir, etc.)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── telemetry.py         # Telemetry dataclass
│   │   │   ├── protocol.py          # WS message types (JSON schemas)
│   │   │   └── state.py             # Per-callsign state (history, assigned heading/alt)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── stt.py               # faster-whisper wrapper
│   │   │   ├── llm.py               # Ollama client wrapper
│   │   │   ├── tts.py               # Piper TTS manager (multi-voice)
│   │   │   ├── nav.py               # OurAirports loader + spatial queries
│   │   │   ├── phraseology.py       # Country procedure snippets
│   │   │   ├── triggers.py          # Server-initiated condition evaluator
│   │   │   └── atc_session.py       # Orchestrator for one ATC exchange
│   │   ├── store/
│   │   │   ├── __init__.py
│   │   │   ├── connection_store.py  # WS connection -> callsign mapping
│   │   │   └── history_store.py     # Per-callsign exchange history (sliding window)
│   │   └── prompts/
│   │       ├── system.md            # Base system prompt (ICAO phrases, roles)
│   │       └── procedures/          # Country-specific procedure snippets
│   │           ├── base.md
│   │           ├── germany.md
│   │           ├── uk.md
│   │           ├── france.md
│   │           ├── spain.md
│   │           └── italy.md
│   ├── data/
│   │   ├── airports.csv             # OurAirports filtered to Europe (+ Morocco/Turkey)
│   │   ├── runways.csv              # OurAirports runways
│   │   ├── com_frequencies.csv      # OurAirports COM frequencies
│   │   └── waypoints.csv            # Optional: user-supplied waypoints near home airports
│   ├── voices/                      # Auto-downloaded Piper models (gitignored)
│   ├── tests/
│   │   ├── test_triggers.py
│   │   ├── test_llm.py
│   │   ├── test_nav.py
│   │   ├── test_phraseology.py
│   │   └── test_protocol.py
│   ├── scripts/
│   │   └── download_voices.py       # Downloads Piper models on first run
│   ├── requirements.txt
│   └── config.toml                  # User-editable server config
│
├── client/                          # C# .NET 8 WPF app
│   ├── OpenATC.Client/
│   │   ├── OpenATC.Client.csproj
│   │   ├── Program.cs
│   │   ├── App.xaml / App.xaml.cs
│   │   ├── MainWindow.xaml / MainWindow.xaml.cs
│   │   ├── Services/
│   │   │   ├── SimConnectService.cs     # MSFS connection, telemetry polling
│   │   │   ├── AudioCaptureService.cs   # NAudio loopback (mic) capture
│   │   │   ├── OpusCodec.cs            # Opus encode/decode via libopus
│   │   │   ├── WebSocketService.cs      # Client WS connection, send/receive
│   │   │   ├── JoystickService.cs       # DirectInput / joystick PTT detection
│   │   │   ├── SettingsService.cs       # Read/write settings.json
│   │   │   └── AutoConnectService.cs    # Connection retry loop
│   │   ├── Models/
│   │   │   ├── Telemetry.cs
│   │   │   ├── Settings.cs
│   │   │   └── ATCResponse.cs
│   │   ├── ViewModels/
│   │   │   ├── MainViewModel.cs
│   │   │   └── SettingsViewModel.cs
│   │   └── Views/
│   │       └── SettingsWindow.xaml
│   └── OpenATC.Client.sln
│
└── docs/
    ├── protocol.md                  # WS message format specification
    └── setup.md                     # How to install and run
```

---

## 2. Implementation Phases

### Phase 0 — Project Scaffolding (estimated: 1 session)

**Server:**
- [ ] `requirements.txt`: `fastapi`, `uvicorn[standard]`, `websockets`, `pydantic`, `httpx`, `toml`, `pyyaml`
- [ ] Create `src/main.py` — minimal FastAPI app with one health-check GET endpoint
- [ ] Create `src/config.py` — loads `config.toml` with sensible defaults
- [ ] Create `config.toml` — port, ollama model name, voice dir, log level
- [ ] Create `scripts/download_voices.py` — downloads Piper models from HuggingFace to `voices/`

**Client:**
- [ ] Create `OpenATC.Client/` from WPF project template (`.NET 8`)
- [ ] Add NuGet refs: `Microsoft.FlightSimulator.SimConnect`, `NAudio`, `Concentus.Opus` (Opus for .NET)
- [ ] Create `Models/Settings.cs` — plain class with JSON serialization
- [ ] Create `Services/SettingsService.cs` — reads/writes `settings.json`
- [ ] Create `MainWindow.xaml` — minimal UI with status label and "Settings" button
- [ ] Wire up `App.xaml.cs` auto-start and dependency injection container

**Verification:**
- [ ] Server: `uvicorn src.main:app` boots, `GET /health` returns 200
- [ ] Client: WPF window opens, `settings.json` created with defaults

---

### Phase 1 — Nav Database (Server)

Requirement: Server can answer "which airports/runways are near this position?" and "what country is this?"

- [ ] Load `airports.csv` and `runways.csv` from OurAirports into memory (SQLite optional, dict is fine for <10k rows)
- [ ] Implement `services/nav.py`:
  - `get_nearest_airport(lat, lon, radius_nm)` -> `Airport | None`
  - `get_airport_by_icao(icao)` -> `Airport`
  - `get_country_code(lat, lon)` -> `str` (via nearest airport)
  - `get_runway_by_ident(icao, runway)` -> `Runway` (heading, length, ILS freq)
  - `get_com_frequency(icao, type)` -> `float` (e.g., tower, ground, approach)
- [ ] Filter OurAirports Europe extract: `continent == "EU"` plus Turkey (`TR`), Morocco (`MA`)
- [ ] Write tests in `tests/test_nav.py`

**Verification:**
- [ ] `get_nearest_airport(48.14, 11.56, 50)` returns EDDM (Munich)
- [ ] `get_runway_by_ident("EDDM", "26R")` returns heading ~258, ILF freq ~109.5

---

### Phase 2 — Protocol & Connection Store (Server)

Requirement: Server can accept WebSocket connections and understand the message format.

- [ ] Define message types in `models/protocol.py`:
  - `register` (client -> server, callsign)
  - `telemetry` (client -> server, full sim snapshot)
  - `audio_start` / `audio_frame` / `audio_end` (client -> server, binary Opus)
  - `atc_text` (server -> client, streaming response text)
  - `atc_audio_start` / `atc_audio_frame` / `atc_audio_end` (server -> client, binary Opus TTS)
  - `push_instruction` (server -> client, unsolicited ATC message)
  - `error` (both directions)
- [ ] Implement `store/connection_store.py`:
  - `ConnectionStore` class — dict of `{ws_id: ConnectionInfo}` with callsign, connect time
  - `register(ws, callsign)` — register or reject
  - `find_by_callsign(callsign)` -> `ws`
  - `unregister(ws)`
- [ ] WebSocket handler in `main.py`:
  - On connect: await register message, or disconnect
  - Route subsequent messages by type to handlers
  - Handle disconnect (unregister)
- [ ] Write tests in `tests/test_protocol.py`

**Verification:**
- [ ] Client connects, sends register with callsign, server responds with `{ "type": "registered" }`
- [ ] Second client connecting with same callsign is rejected
- [ ] Sending telemetry is accepted without error

---

### Phase 3 — Telemetry Pipeline (Client + Server)

Requirement: Client polls SimConnect every 3s and sends telemetry. Server stores latest snapshot.

**Client:**
- [ ] `Services/SimConnectService.cs`:
  - Connect to MSFS (SimConnect `DISPATCH_OBJECT`)
  - Poll at 3s interval: position (lat/lon/alt), heading, speed (IAS/GS), vertical speed, on_ground, flaps, gear, transponder, flight plan (origin/dest ICAO strings)
  - Convert to `Models/Telemetry` object
  - Fire `TelemetryUpdated` event
- [ ] `Services/WebSocketService.cs`:
  - Send telemetry JSON every 3s: `{ "type": "telemetry", ... }`
  - Implement reconnect with exponential backoff

**Server:**
- [ ] Add `callsign_telemetry` dict to connection store — `{callsign: latest Telemetry}`
- [ ] Telemetry handler updates it on receipt

**Verification:**
- [ ] Client logs: "Connected to MSFS", then telemetry appears every 3s
- [ ] Server logs: "Telemetry from DAL123: lat=48.1, lon=11.5, alt=35000"

---

### Phase 4 — PTT + Audio Pipeline (Client)

Requirement: Player presses PTT -> client captures mic audio, encodes Opus, streams to server.

- [ ] `Services/JoystickService.cs`:
  - Use `SharpDX.DirectInput` to enumerate devices
  - Allow user to select a joystick button in settings
  - Expose `ButtonStateChanged` event
- [ ] `Services/AudioCaptureService.cs`:
  - Use NAudio `WaveInEvent` (or WASAPI loopback if needed) to capture mic
  - Sample rate: 16kHz, 16-bit, mono
  - Expose `AudioDataAvailable(byte[] pcm)` event
  - Start/stop capture methods
- [ ] `Services/OpusCodec.cs`:
  - Use Concentus.Opus or bind libopus via P/Invoke
  - Encode PCM -> Opus packets (60ms frames)
  - Decode Opus -> PCM (for receiving ATC responses)
- [ ] Integrate PTT flow:
  - PTT down -> `AudioCaptureService.Start()` + send `{ "type": "audio_start", "callsign" }`
  - On each mic chunk -> Opus encode -> send binary WS frame (type tag byte + opus data)
  - PTT up -> send `{ "type": "audio_end" }` + stop capture
- [ ] Visual indicator in main window: green mic icon while transmitting

**Verification:**
- [ ] PTT key/button starts recording, UI shows active mic
- [ ] Server receives audio_start, binary Opus frames, audio_end
- [ ] Server can decode and play the Opus locally (test with a dump-to-file)

---

### Phase 5 — STT + LLM + TTS Pipeline (Server)

Requirement: Server receives audio -> transcribes -> LLM generates response -> TTS speaks -> sends back.

- [ ] `services/stt.py`:
  - Load `faster-whisper` model (`base` or `small`, configurable)
  - `transcribe(audio_bytes: bytes) -> str`
  - Handle streaming: buffer Opus frames, decode to PCM, feed to Whisper on `audio_end`
  - Accept a `vad_filter=True` to trim silence
  
- [ ] `services/llm.py`:
  - Ollama Python client: `ollama.chat(model="qwen2.5:7b", messages=[...])`
  - Accept `List[ChatMessage]` (system + history + user)
  - Return streamed tokens via async generator

- [ ] `services/tts.py`:
  - Load Piper TTS model per role: `delivery`, `ground`, `tower`, `departure`, `center`, `approach`
  - `synthesize(text: str, role: str) -> bytes` (Opus or PCM)
  - Cache loaded model in dict
  - Convert Piper raw PCM output -> Opus before sending to client

- [ ] `services/atc_session.py` — orchestrator for one exchange:
  1. On `audio_end`:
     - Decode buffered Opus -> PCM -> transcribe with Whisper
     - Determine relevant ATC role from current telemetry + context
     - Build LLM prompt: system + country procedure + exchange history + player transcription
     - Stream LLM response tokens as `atc_text` messages to client
     - When LLM completes, pass full text to TTS for the role
     - Stream TTS audio frames as `atc_audio_*` back to client
     - Store the exchange in `history_store.py`

- [ ] `store/history_store.py`:
  - Per-callsign: list of `{role: str, text: str, timestamp: float, assigned_heading: int | None, assigned_alt: int | None}`
  - Keep last 15 exchanges, drop older
  - Parse LLM output for assigned heading/alt and store for trigger evaluation

**Verification:**
- [ ] Client speaks -> server transcribes -> text appears in server log
- [ ] Server generates ATC response -> text appears in client UI
- [ ] Server sends TTS audio -> client can play it (playback via NAudio `WaveOut`)

---

### Phase 6 — Country Phraseology Injection (Server)

Requirement: Server automatically adjusts ATC phraseology per country.

- [ ] Create `prompts/procedures/` files:
  - `base.md`: "Use standard ICAO English phraseology. Callsign format: [airline][flight_number]."
  - `germany.md`: "Region: Germany. Transition altitude FL100. QNH in hPa. Center called 'München Radar', tower called '[Airport] Tower'. Use German locality names."
  - `uk.md`: "Region: UK. Transition altitude varies (6000ft at EGLL, 5000ft at EGKK). QNH in hPa. Center called 'London Control' / 'London Information'."
  - `france.md`: "Region: France. Transition altitude FL60/FL100 depending on sector. QNH in hPa. Use French locality names. 'Approche' for approach."
  - `spain.md`: / `italy.md`: analogous
- [ ] In `services/phraseology.py`:
  - `get_country_procedure(country_code: str) -> str`
  - On telemetry update: look up nearest airport country, cache it
  - Call this when building the LLM system prompt

**Verification:**
- [ ] Client over EDDM -> LLM response uses "München Radar" and "QNH 1023"
- [ ] Client over EGLL -> LLM response uses "London Control" and transition altitude 6000ft

---

### Phase 7 — Server-Initiated Triggers (Server)

Requirement: Server evaluates telemetry and pushes unsolicited ATC instructions.

- [ ] `services/triggers.py`:
  - Background asyncio task runs every 5s
  - For each connected callsign, load latest telemetry + history
  - Evaluate trigger conditions in priority order:
    1. **Emergency** — transcription flag or transponder 7700
    2. **Altitude deviation** — current alt vs last assigned alt, diff > 200ft
    3. **Heading deviation** — current heading vs last assigned, diff > 10° for >30s
    4. **Airspace infringement** — near controlled airport without clearance (no recent tower/gnd exchange)
    5. **Approach handoff** — within 40nm of destination, below 20k ft (if flight plan exists)
    6. **Tower handoff** — within 10nm, below 5000ft
    7. **Departure handoff** — above 10k ft climbing
    8. **Squawk assignment** — no squawk set (first contact)
    9. **VFR zone entry** — VFR callsign entering class C/D airspace
    10. **Frequency change** — distance/time from last push > 60s
  - If trigger fires:
    - Build LLM context for push instruction (include trigger reason)
    - Call LLM to generate the ATC text
    - Synthesize TTS for the appropriate role
    - Send push_instruction to client
    - Update exchange history
  - Minimum 15s cooldown between pushes per callsign

**Verification:**
- [ ] Client climbs through FL100 -> server pushes "Contact Departure 119.2"
- [ ] Client drifts off altitude -> server pushes altitude correction
- [ ] No push more than once per 15s

---

### Phase 8 — Client Audio Playback & UI Polish (Client)

Requirement: Client can receive and play ATC audio, display ATC text, and show status.

- [ ] `MainWindow.xaml`: Add:
  - Connection status indicator (green dot / red dot)
  - "Calling..." popup when server pushes an instruction
  - "Listening..." indicator during PTT
  - ATC text log (scrollable list of recent exchanges)
  - Volume slider for ATC audio
- [ ] Playback: decode incoming Opus frames -> PCM -> play via NAudio `WaveOut`
- [ ] Handle server-initiated push: play audio immediately, show text overlay

**Settings UI:**
- [ ] `SettingsWindow.xaml`:
  - Server address (text)
  - PTT key binder (press a key or button to bind)
  - Joystick selector (dropdown of detected joysticks + button selector)
  - Callsign (text)
  - Audio input device (dropdown)
  - Volume slider

**Verification:**
- [ ] Full roundtrip works: PTT -> speak -> hear ATC response
- [ ] Server push appears as popup + audio

---

### Phase 9 — Prompts & Phraseology Tuning (Server)

Requirement: ATC responses sound realistic and follow procedures.

- [ ] `prompts/system.md` — detailed system prompt for the LLM:
  - Role description: "You are an Air Traffic Controller at a European airport/center."
  - Response format: strictly phraseology, no meta-commentary
  - Callsign usage rules: always full callsign on first contact, abbreviated after
  - Altitude format: FL + 3 digits above transition, "xxx feet" below
  - Heading format: "turn left/right heading xxx"
  - Speed format: "reduce/increase speed to xxx knots"
  - Frequency format: "Contact [position] on 1xx.xxx"
  - Squawk format: "Squawk xxxx"
  - Readback expectations (not needed, player is the pilot)
  - Emergency handling: "MAYDAY MAYDAY MAYDAY" -> prioritize, standard emergency phraseology
  - If player transmission is unclear, ask for confirmation
- [ ] Iterative tuning via test cases (at least 20 scenarios)

**Verification:**
- [ ] LLM output consistently meets phraseology standards
- [ ] Output validator (regex) catches: missing callsign, informal language, wrong format

---

### Phase 10 — Integration, Packaging & Documentation

Requirement: Ship-ready system.

- [ ] Server:
  - `uvicorn` with `--reload` for dev, systemd service template for prod
  - Graceful shutdown: flush TTS, clean WS connections
  - Logging: structured logging (structlog), per-callsign log IDs
  - Error recovery: if Ollama/Whisper/Piper crash, log and continue

- [ ] Client:
  - MSI installer (WiX Toolset) or ClickOnce publish
  - Icon and branding
  - Auto-start with Windows option
  - Error notification toasts

- [ ] Documentation:
  - `docs/setup.md`: server setup (Python install, Ollama install, model pulls, run), client setup (install, configure)
  - `docs/protocol.md`: WebSocket protocol reference
  - `README.md`: brief overview + badges (status, license)

- [ ] Tests:
  - Server: `pytest` for nav, triggers, phraseology, protocol parsing
  - Client: smoke test (manual) — verify connect, PTT, audio roundtrip

---

## 3. Dependencies

### Server (`requirements.txt`)
```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
websockets>=13.0
pydantic>=2.9.0
pydantic-settings>=2.5.0
httpx>=0.28.0
toml>=0.10.2
faster-whisper>=1.1.0
ollama>=0.4.0
piper-tts>=1.2.0       # or piper-phonemize + onnxruntime
soundfile>=0.12.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

### Client (NuGet packages)
```
Microsoft.FlightSimulator.SimConnect
NAudio
Concentus.Opus                 # Opus codec for .NET
System.Net.WebSockets.Client
System.Text.Json
SharpDX.DirectInput            # Joystick support
Microsoft.Extensions.DependencyInjection
```

---

## 4. Rollout Order (Dependency-Aware)

```
Phase 0 (Scaffold) ───────────────────────────────────────┐
                                                           │
Phase 1 (Nav DB) ← ─ depends on Phase 0 server structure  │
                                                           │
Phase 2 (Protocol/WS) ← depends on Phase 0                ├─ can run in parallel
                                                           │
Phase 3 (Telemetry) ← depends on Phase 2 server + client  │
                                                           │
Phase 4 (PTT/Audio) ← depends on Phase 2                  │
                                                           │
Phase 5 (STT/LLM/TTS) ← depends on Phase 4 (audio in)     │
                                                           │
Phase 6 (Phraseology) ← depends on Phase 5                 │
                                                           │
Phase 7 (Triggers) ← depends on Phase 3 (telemetry)        │
                    ← depends on Phase 5 (LLM)             │
                    ← depends on Phase 6 (phraseology)    │
                                                           │
Phase 8 (Client UI) ← depends on Phase 4                 │
                                                           │
Phase 9 (Tuning) ← depends on Phase 5 + 6 + 7            │
                                                           │
Phase 10 (Package/Doc) ← depends on everything            │
```

**Parallel tracks possible:**
- Server: Phases 1+2 (nav + protocol) can be done together
- Client: Phase 3 (telemetry) can start once protocol is defined, before audio is ready
- Server: Phase 7 (triggers) can start as soon as telemetry + LLM work, independently of audio

---

## 5. Key Risks & Mitigations

| Risk | Mitigation |
|---|---|
| SimConnect unreliable or crashes MSFS | `AutoConnectService` retries with backoff; client runs independently of sim |
| Piper TTS voice quality varies | Start with one well-rated voice; swap model easily |
| LLM hallucinates procedures | Output validator (regex) catches bad format; country injection constrains output |
| Whisper fails on accent/mic quality | Use `base.en` or `small.en` model; add VAD filtering |
| Opus encode/decode latency | Keep frame size to 60ms; pre-allocate buffers |
| Joystick PTT not detected | Support keyboard PTT as fallback; log joystick detection |
| VRAM overflow (6 voices + LLM + Whisper) | Add `--lazy-voices` flag; allow configuring fewer TTS voices |
| Docker GPU passthrough fails | setup.sh detects nvidia-container-toolkit; generates correct Compose command |
| Docker Compose version too old | setup.sh checks `docker compose version` and exits with upgrade message |
| First startup takes too long (model downloads) | All downloads are cached in Docker volumes; only slow on first run |
| Port conflict on host | Exposed port overridable via `SERVER_PORT` env var |
