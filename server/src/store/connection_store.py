from typing import Optional

from fastapi import WebSocket

from src.models.state import CallsignState
from src.models.telemetry import Telemetry


class ConnectionInfo:
    def __init__(self, ws_id: int, ws: WebSocket, callsign: str):
        self.ws_id = ws_id
        self.ws = ws
        self.callsign = callsign
        self.state = CallsignState(callsign)


class ConnectionStore:
    def __init__(self):
        self._by_callsign: dict[str, ConnectionInfo] = {}
        self._by_ws_id: dict[int, str] = {}

    def register(self, ws_id: int, ws: WebSocket, callsign: str) -> bool:
        if callsign in self._by_callsign:
            return False
        info = ConnectionInfo(ws_id, ws, callsign)
        self._by_callsign[callsign] = info
        self._by_ws_id[ws_id] = callsign
        return True

    def unregister(self, callsign: str):
        if callsign in self._by_callsign:
            info = self._by_callsign.pop(callsign)
            self._by_ws_id.pop(info.ws_id, None)

    def get_ws(self, callsign: str) -> Optional[WebSocket]:
        info = self._by_callsign.get(callsign)
        return info.ws if info else None

    def get_state(self, callsign: str) -> Optional[CallsignState]:
        info = self._by_callsign.get(callsign)
        return info.state if info else None

    def update_telemetry(self, callsign: str, telemetry: Telemetry):
        state = self.get_state(callsign)
        if state:
            state.latest_telemetry = telemetry

    def count(self) -> int:
        return len(self._by_callsign)

    def all_callsigns(self) -> list[str]:
        return list(self._by_callsign)
