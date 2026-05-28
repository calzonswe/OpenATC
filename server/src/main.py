import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from src.config import Settings
from src.store.connection_store import ConnectionStore
from src.models.protocol import MessageType, ClientMessage, ServerMessage
from src.models.telemetry import Telemetry
from src.models.state import ExchangeEntry
from src.services.stt import STTService
from src.services.llm import LLMService
from src.services.tts import TTSService
from src.services.nav import NavDatabase
from src.services.atc_session import ATCSession
from src.services.triggers import TriggerEvaluator, TriggerResult

logger = logging.getLogger("openatc")

settings = Settings.from_toml()
app = FastAPI(title="OpenATC Server", version="0.1.0")
connection_store = ConnectionStore()

# Lazy-init services
nav: Optional[NavDatabase] = None
stt: Optional[STTService] = None
llm: Optional[LLMService] = None
tts: Optional[TTSService] = None
atc_session: Optional[ATCSession] = None
trigger_evaluator: Optional[TriggerEvaluator] = None
_trigger_task: Optional[asyncio.Task] = None


def _init_services():
    global nav, stt, llm, tts, atc_session, trigger_evaluator
    if nav is not None:
        return

    logger.info("Initializing services...")
    nav = NavDatabase(data_dir="data")
    logger.info(f"NavDB loaded: {len(nav.airports)} airports, {len(nav.runways)} runways")

    stt = STTService(
        model_name=settings.models__stt_model,
        language=settings.models__stt_language,
    )
    llm = LLMService(
        model=settings.models__llm_model,
        host=settings.models__llm_host,
    )
    tts = TTSService(
        voices_dir=settings.voices__directory,
        sample_rate=settings.models__tts_sample_rate,
    )
    atc_session = ATCSession(stt=stt, llm=llm, tts=tts, nav=nav)
    trigger_evaluator = TriggerEvaluator(nav=nav)
    logger.info("All services initialized")


@app.on_event("startup")
async def startup():
    _init_services()


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down OpenATC server...")
    # Cancel background tasks
    global _trigger_task
    if _trigger_task and not _trigger_task.done():
        _trigger_task.cancel()
        try:
            await _trigger_task
        except asyncio.CancelledError:
            pass
    # Unload ML models to free VRAM
    if stt:
        stt.unload()
    # Close all WebSocket connections
    for callsign in connection_store.all_callsigns():
        ws = connection_store.get_ws(callsign)
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        connection_store.unregister(callsign)
    logger.info("Shutdown complete")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "connections": connection_store.count(),
        "nav_airports": len(nav.airports) if nav else 0,
    }


async def process_audio_for_callsign(callsign: str):
    """Run STT -> LLM -> TTS pipeline for a completed audio recording."""
    state = connection_store.get_state(callsign)
    if not state or not state.audio_buffer:
        return

    # Pass individual Opus frames (STT handles Ogg wrapping internally)
    audio_frames = list(state.audio_buffer)
    state.audio_buffer.clear()

    ws = connection_store.get_ws(callsign)
    if not ws:
        return

    try:
        # Send "thinking" indicator
        await ws.send_text(ServerMessage(
            type=MessageType.ATC_TEXT,
            callsign=callsign,
            text="...",
        ).model_dump_json())

        transcription, atc_response = await atc_session.process_audio(state, audio_frames)

        # Send the ATC text response
        await ws.send_text(ServerMessage(
            type=MessageType.ATC_TEXT,
            callsign=callsign,
            text=atc_response,
        ).model_dump_json())

        # Synthesize and send TTS audio
        role = atc_session.determine_role(state)
        audio_pcm = await tts.synthesize(atc_response, role=role)
        if audio_pcm:
            await ws.send_text(ServerMessage(
                type=MessageType.ATC_AUDIO_START,
                callsign=callsign,
            ).model_dump_json())
            # Send in chunks
            chunk_size = 4096
            for i in range(0, len(audio_pcm), chunk_size):
                chunk = audio_pcm[i:i + chunk_size]
                await ws.send_bytes(chunk)
            await ws.send_text(ServerMessage(
                type=MessageType.ATC_AUDIO_END,
                callsign=callsign,
            ).model_dump_json())

    except Exception as e:
        logger.error(f"Audio processing failed for {callsign}: {e}")
        await ws.send_text(ServerMessage(
            type=MessageType.ERROR,
            callsign=callsign,
            text=f"Processing error: {e}",
        ).model_dump_json())


async def trigger_loop():
    """Background task: evaluate triggers for all connected aircraft."""
    while True:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Trigger loop cancelled")
            return
        if not trigger_evaluator:
            continue

        for callsign in connection_store.all_callsigns():
            state = connection_store.get_state(callsign)
            if not state or not state.latest_telemetry:
                continue

            try:
                result = trigger_evaluator.evaluate_all(state)
            except Exception as e:
                logger.error(f"Trigger eval failed for {callsign}: {e}")
                continue

            if result is None:
                continue

            logger.info(f"Trigger fired for {callsign}: {result.reason}")
            state.last_push_time = time.time()

            ws = connection_store.get_ws(callsign)
            if not ws:
                continue

            try:
                system_prompt = atc_session.build_system_prompt(state, result.role)
                prompt = (
                    f"ATC Trigger: {result.reason}\n\n"
                    f"Generate an appropriate ATC instruction for {callsign}. "
                    f"Use correct ICAO phraseology."
                )
                messages = [{"role": "user", "content": prompt}]
                response = await llm.generate_sync(system_prompt, messages)

                await ws.send_text(ServerMessage(
                    type=MessageType.PUSH_INSTRUCTION,
                    callsign=callsign,
                    text=response,
                    payload={"role": result.role, "reason": result.reason},
                ).model_dump_json())

                # Synthesize TTS for push
                audio_pcm = await tts.synthesize(response, role=result.role)
                if audio_pcm:
                    await ws.send_text(ServerMessage(
                        type=MessageType.ATC_AUDIO_START,
                        callsign=callsign,
                    ).model_dump_json())
                    chunk_size = 4096
                    for i in range(0, len(audio_pcm), chunk_size):
                        await ws.send_bytes(audio_pcm[i:i + chunk_size])
                    await ws.send_text(ServerMessage(
                        type=MessageType.ATC_AUDIO_END,
                        callsign=callsign,
                    ).model_dump_json())

                state.add_exchange(ExchangeEntry(
                    role=result.role,
                    text=response,
                    timestamp=time.time(),
                    is_push=True,
                ))

            except Exception as e:
                logger.error(f"Trigger push failed for {callsign}: {e}")


@app.on_event("startup")
async def start_trigger_loop():
    global _trigger_task
    _trigger_task = asyncio.create_task(trigger_loop())


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    callsign: Optional[str] = None

    try:
        while True:
            raw = await ws.receive()
            event_type = raw.get("type", "")

            if event_type == "websocket.disconnect":
                break

            if event_type == "websocket.receive":
                if "text" in raw:
                    data = json.loads(raw["text"])
                    msg = ClientMessage(**data)

                    if msg.type == MessageType.REGISTER:
                        callsign = msg.callsign or "UNKNOWN"
                        conn_id = id(ws)
                        if not connection_store.register(conn_id, ws, callsign):
                            logger.warning(f"Duplicate registration attempt: {callsign}")
                            await ws.send_text(
                                ServerMessage(
                                    type=MessageType.ERROR,
                                    callsign=callsign,
                                    text=f"Callsign '{callsign}' already connected",
                                ).model_dump_json()
                            )
                            continue
                        await ws.send_text(
                            ServerMessage(
                                type=MessageType.REGISTERED,
                                callsign=callsign,
                            ).model_dump_json()
                        )
                        logger.info(f"Registered: {callsign}")

                    elif msg.type == MessageType.TELEMETRY and callsign:
                        tel = Telemetry(**msg.payload)
                        connection_store.update_telemetry(callsign, tel)

                    elif msg.type == MessageType.AUDIO_START and callsign:
                        state = connection_store.get_state(callsign)
                        if state:
                            state.is_recording = True
                            state.audio_buffer = []

                    elif msg.type == MessageType.AUDIO_END and callsign:
                        state = connection_store.get_state(callsign)
                        if state:
                            state.is_recording = False
                            # Process the audio async
                            asyncio.create_task(process_audio_for_callsign(callsign))

                    elif msg.type == MessageType.PONG:
                        pass

                elif "bytes" in raw and callsign:
                    state = connection_store.get_state(callsign)
                    if state and state.is_recording:
                        state.audio_buffer.append(raw["bytes"])

    except (WebSocketDisconnect, Exception) as e:
        logger.info(f"Disconnected: {callsign} ({e})")
        if callsign:
            connection_store.unregister(callsign)
