from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel


class MessageType(str, Enum):
    REGISTER = "register"
    TELEMETRY = "telemetry"
    AUDIO_START = "audio_start"
    AUDIO_FRAME = "audio_frame"
    AUDIO_END = "audio_end"
    ATC_TEXT = "atc_text"
    ATC_AUDIO_START = "atc_audio_start"
    ATC_AUDIO_FRAME = "atc_audio_frame"
    ATC_AUDIO_END = "atc_audio_end"
    PUSH_INSTRUCTION = "push_instruction"
    ERROR = "error"
    REGISTERED = "registered"
    PONG = "pong"


class ClientMessage(BaseModel):
    type: MessageType
    callsign: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class ServerMessage(BaseModel):
    type: MessageType
    callsign: Optional[str] = None
    text: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
