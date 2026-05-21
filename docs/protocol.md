# OpenATC WebSocket Protocol

## Connection

```
ws://<server>:<port>/ws
```

The client connects and immediately sends a `register` message. No authentication is required (LAN-only).

## Message Format

### Text Messages (JSON)

All text messages follow this structure:

```json
{
  "type": "<message_type>",
  "callsign": "<callsign>",
  "text": "<optional_text>",
  "payload": { }
}
```

### Binary Messages

Binary frames carry audio data (Opus-encoded PCM, or raw PCM for TTS). A text `audio_start` / `audio_end` frame brackets each audio stream.

---

## Client → Server Messages

### Register

```
{ "type": "register", "callsign": "DAL123" }
```

Sent immediately after WebSocket connect. Server responds with `registered`.

### Telemetry

```
{
  "type": "telemetry",
  "callsign": "DAL123",
  "payload": {
    "callsign": "DAL123",
    "latitude": 48.35,
    "longitude": 11.78,
    "altitude_ft": 35000,
    "heading": 270.0,
    "speed_kts": 450.0,
    "vertical_speed_fpm": 0.0,
    "on_ground": false,
    "transponder_code": 4721,
    "origin_icao": "EDDM",
    "dest_icao": "EGLL",
    "flight_rules": "IFR"
  }
}
```

Sent every 3 seconds while connected. Server updates per-callsign state.

### Audio Start

```
{ "type": "audio_start", "callsign": "DAL123" }
```

Sent when player presses PTT. Server begins buffering binary frames.

### Audio Frames (Binary)

Sent as raw binary WebSocket frames — Opus-encoded 16kHz 16-bit mono audio, 60ms frames.

### Audio End

```
{ "type": "audio_end", "callsign": "DAL123" }
```

Sent when player releases PTT. Server processes buffered audio through STT → LLM → TTS.

### Pong

```
{ "type": "pong" }
```

Optional keepalive response.

---

## Server → Client Messages

### Registered

```
{ "type": "registered", "callsign": "DAL123" }
```

Confirms the client is registered.

### ATC Text

```
{
  "type": "atc_text",
  "callsign": "DAL123",
  "text": "DAL123, descend to FL180, heading 220"
}
```

Sent when the LLM completes its response. May be sent as tokens stream in (one per chunk).

### ATC Audio Start / End

```
{ "type": "atc_audio_start", "callsign": "DAL123" }
...binary PCM frames...
{ "type": "atc_audio_end", "callsign": "DAL123" }
```

Brackets the TTS audio stream. Binary frames are raw 16-bit PCM at 22050Hz (configurable).

### Push Instruction

```
{
  "type": "push_instruction",
  "callsign": "DAL123",
  "text": "DAL123, contact München Radar on 119.250",
  "payload": {
    "role": "departure",
    "reason": "Aircraft climbed through FL100, handoff to departure"
  }
}
```

Sent unsolicited when the trigger evaluator detects a condition (altitude deviation, handoff, etc.).

### Error

```
{
  "type": "error",
  "callsign": "DAL123",
  "text": "Processing error: ..."
}
```

Sent when an internal error occurs during audio processing.
