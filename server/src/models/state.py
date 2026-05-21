from typing import Optional


class ExchangeEntry:
    def __init__(
        self,
        role: str,
        text: str,
        timestamp: float,
        assigned_heading: Optional[int] = None,
        assigned_alt: Optional[int] = None,
        is_push: bool = False,
    ):
        self.role = role
        self.text = text
        self.timestamp = timestamp
        self.assigned_heading = assigned_heading
        self.assigned_alt = assigned_alt
        self.is_push = is_push


class CallsignState:
    def __init__(self, callsign: str):
        self.callsign = callsign
        self.latest_telemetry = None
        self.history: list[ExchangeEntry] = []
        self.last_push_time: float = 0.0
        self.last_assigned_heading: Optional[int] = None
        self.last_assigned_alt: Optional[int] = None
        self.current_role: str = "center"
        self.audio_buffer: list[bytes] = []
        self.is_recording: bool = False

    def add_exchange(self, entry: ExchangeEntry, max_window: int = 15):
        self.history.append(entry)
        if len(self.history) > max_window:
            self.history = self.history[-max_window:]
        if entry.assigned_heading is not None:
            self.last_assigned_heading = entry.assigned_heading
        if entry.assigned_alt is not None:
            self.last_assigned_alt = entry.assigned_alt
