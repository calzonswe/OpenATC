import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from src.config import Settings
from src.models.protocol import ClientMessage, MessageType, ServerMessage
from src.models.state import CallsignState, ExchangeEntry
from src.models.telemetry import Telemetry
from src.services.atc_session import ATCSession
from src.services.llm import LLMService
from src.services.nav import NavDatabase
from src.services.stt import STTService
from src.services.triggers import TriggerEvaluator
from src.services.tts import TTSService
from src.store.connection_store import ConnectionStore

logger = logging.getLogger("openatc")


def _setup_logging():
    level = getattr(logging, settings.server__log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    for lib in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(lib).setLevel(logging.WARNING)


settings = Settings.from_toml()
_setup_logging()
app = FastAPI(title="OpenATC Server", version="0.2.0")
connection_store = ConnectionStore()

MAX_CONNECTIONS = 32
_rate_limit: dict[str, float] = {}
_processing_callsigns: set[str] = set()


def _check_rate_limit(callsign: str, min_interval: float = 1.0) -> bool:
    now = time.time()
    last = _rate_limit.get(callsign, 0.0)
    if now - last < min_interval:
        return False
    _rate_limit[callsign] = now
    return True

# Lazy-init services
nav: Optional[NavDatabase] = None
stt: Optional[STTService] = None
llm: Optional[LLMService] = None
tts: Optional[TTSService] = None
atc_session: Optional[ATCSession] = None
trigger_evaluator: Optional[TriggerEvaluator] = None
_trigger_task: Optional[asyncio.Task] = None
_TRIGGER_CONCURRENCY = 8


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
    global _trigger_task
    _trigger_task = asyncio.create_task(trigger_loop())
    logger.info("Startup complete — services initialized, trigger loop started")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down OpenATC server...")
    global _trigger_task
    if _trigger_task and not _trigger_task.done():
        _trigger_task.cancel()
        try:
            await _trigger_task
        except asyncio.CancelledError:
            pass
    if stt:
        stt.unload()
    for callsign in connection_store.all_callsigns():
        ws = connection_store.get_ws(callsign)
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        connection_store.unregister(callsign)
        _rate_limit.pop(callsign, None)
        _processing_callsigns.discard(callsign)
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
        await ws.send_text(ServerMessage(
            type=MessageType.ATC_TEXT,
            callsign=callsign,
            text="...",
        ).model_dump_json())

        timeout = 60.0
        transcription, atc_response = await asyncio.wait_for(
            atc_session.process_audio(state, audio_frames),
            timeout=timeout,
        )

        if transcription.strip():
            await ws.send_text(ServerMessage(
                type=MessageType.ATC_TEXT,
                callsign=callsign,
                text=f"[YOU] {transcription}",
                payload={"kind": "transcription"},
            ).model_dump_json())

        await ws.send_text(ServerMessage(
            type=MessageType.ATC_TEXT,
            callsign=callsign,
            text=atc_response,
            payload={"kind": "response"},
        ).model_dump_json())

        role = atc_session.determine_role(state)
        audio_pcm = await tts.synthesize(atc_response, role=role)
        if audio_pcm:
            await ws.send_text(ServerMessage(
                type=MessageType.ATC_AUDIO_START,
                callsign=callsign,
            ).model_dump_json())
            chunk_size = 4096
            for i in range(0, len(audio_pcm), chunk_size):
                chunk = audio_pcm[i:i + chunk_size]
                await ws.send_bytes(chunk)
            await ws.send_text(ServerMessage(
                type=MessageType.ATC_AUDIO_END,
                callsign=callsign,
            ).model_dump_json())

    except asyncio.TimeoutError:
        logger.error(f"Audio processing timed out for {callsign}")
        await ws.send_text(ServerMessage(
            type=MessageType.ERROR,
            callsign=callsign,
            text="Processing timed out — please try again",
        ).model_dump_json())
    except Exception as e:
        logger.error(f"Audio processing failed for {callsign}: {e}")
        await ws.send_text(ServerMessage(
            type=MessageType.ERROR,
            callsign=callsign,
            text=f"Processing error: {e}",
        ).model_dump_json())
    finally:
        _processing_callsigns.discard(callsign)


async def _push_trigger(callsign: str, state: CallsignState, result) -> None:
    """Execute one trigger push: LLM + send + TTS."""
    try:
        system_prompt = atc_session.build_system_prompt(state, result.role)
        prompt = (
            f"ATC Trigger: {result.reason}\n\n"
            f"Generate an appropriate ATC instruction for {callsign}. "
            f"Use correct ICAO phraseology."
        )
        messages = [{"role": "user", "content": prompt}]
        response = await llm.generate_sync(system_prompt, messages)

        ws = connection_store.get_ws(callsign)
        if not ws:
            return

        await ws.send_text(ServerMessage(
            type=MessageType.PUSH_INSTRUCTION,
            callsign=callsign,
            text=response,
            payload={"role": result.role, "reason": result.reason},
        ).model_dump_json())

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


async def trigger_loop():
    """Background task: evaluate triggers for all connected aircraft."""
    sem = asyncio.Semaphore(_TRIGGER_CONCURRENCY)
    while True:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Trigger loop cancelled")
            return
        if not trigger_evaluator or not atc_session or not llm or not tts:
            continue

        tasks = []
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
            async with sem:
                tasks.append(asyncio.create_task(_push_trigger(callsign, state, result)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    callsign: Optional[str] = None

    if connection_store.count() >= MAX_CONNECTIONS:
        await ws.send_text(ServerMessage(
            type=MessageType.ERROR,
            text="Server full — max connections reached",
        ).model_dump_json())
        await ws.close()
        return

    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.info(f"Connection timeout for {callsign or 'unknown'}")
                break

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
                        if callsign in _processing_callsigns:
                            await ws.send_text(ServerMessage(
                                type=MessageType.ERROR,
                                callsign=callsign,
                                text="Previous transmission still processing",
                            ).model_dump_json())
                            continue
                        state = connection_store.get_state(callsign)
                        if state:
                            state.is_recording = True
                            state.audio_buffer = []

                    elif msg.type == MessageType.AUDIO_END and callsign:
                        state = connection_store.get_state(callsign)
                        if state:
                            state.is_recording = False
                            if _check_rate_limit(callsign, min_interval=2.0):
                                _processing_callsigns.add(callsign)
                                asyncio.create_task(process_audio_for_callsign(callsign))
                            else:
                                logger.warning(f"Rate limited audio from {callsign}")
                                await ws.send_text(ServerMessage(
                                    type=MessageType.ERROR,
                                    callsign=callsign,
                                    text="Please wait before sending again",
                                ).model_dump_json())

                    elif msg.type == MessageType.PONG:
                        pass

                elif "bytes" in raw and callsign:
                    state = connection_store.get_state(callsign)
                    if state and state.is_recording:
                        state.audio_buffer.append(raw["bytes"])

    except (WebSocketDisconnect, Exception) as e:
        logger.info(f"Disconnected: {callsign} ({e})")
    finally:
        if callsign:
            connection_store.unregister(callsign)
            _rate_limit.pop(callsign, None)
            _processing_callsigns.discard(callsign)
