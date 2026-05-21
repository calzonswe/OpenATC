"""Per-callsign exchange history with sliding window."""

from src.models.state import ExchangeEntry


class HistoryStore:
    """Thread-safe store of ATC exchange history per callsign.

    Maintains a sliding window of recent exchanges for LLM context.
    """

    def __init__(self, max_window: int = 15):
        self._history: dict[str, list[ExchangeEntry]] = {}
        self.max_window = max_window

    def add(self, callsign: str, entry: ExchangeEntry):
        if callsign not in self._history:
            self._history[callsign] = []
        self._history[callsign].append(entry)
        if len(self._history[callsign]) > self.max_window:
            self._history[callsign] = self._history[callsign][-self.max_window:]

    def get(self, callsign: str) -> list[ExchangeEntry]:
        return self._history.get(callsign, [])

    def clear(self, callsign: str):
        self._history.pop(callsign, None)

    def last_assigned(self, callsign: str) -> tuple:
        """Return (heading, altitude) last assigned to this callsign."""
        heading = None
        altitude = None
        for entry in reversed(self._history.get(callsign, [])):
            if heading is None and entry.assigned_heading is not None:
                heading = entry.assigned_heading
            if altitude is None and entry.assigned_alt is not None:
                altitude = entry.assigned_alt
            if heading is not None and altitude is not None:
                break
        return heading, altitude
