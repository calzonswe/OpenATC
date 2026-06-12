"""Airline callsign database — maps ICAO/IATA codes to telephony names."""

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("openatc.airline")


class AirlineDB:
    def __init__(self, data_dir: str = "data"):
        self._mapping: dict[str, str] = {}
        self._load(Path(data_dir) / "airline_callsigns.json")

    def _load(self, path: Path):
        if not path.exists():
            logger.warning(f"Airline callsign DB not found: {path}")
            return
        try:
            with open(path) as f:
                self._mapping = json.load(f)
            logger.info(f"Loaded {len(self._mapping)} airline callsign mappings")
        except Exception as e:
            logger.error(f"Failed to load airline callsign DB: {e}")

    def resolve(self, raw_callsign: str) -> str:
        """Resolve a raw callsign to its telephony format.

        E.g. "SK123" -> "Scandinavian 123", "DAL456" -> "Delta 456".

        Tries first 3 chars as ICAO code, then first 2 as IATA code.
        Falls back to raw callsign if no mapping found.
        """
        s = raw_callsign.strip().upper()

        # Try 3-letter ICAO prefix first (DAL123 -> DAL + 123)
        m3 = re.match(r"^([A-Z0-9]{3})(\d{1,4})$", s)
        if m3:
            prefix, number = m3.group(1), m3.group(2)
            telephony = self._mapping.get(prefix)
            if telephony:
                return f"{telephony} {number}"

        # Try 2-letter IATA prefix (SK123 -> SK + 123)
        m2 = re.match(r"^([A-Z0-9]{2})(\d{1,4})$", s)
        if m2:
            prefix, number = m2.group(1), m2.group(2)
            telephony = self._mapping.get(prefix)
            if telephony:
                return f"{telephony} {number}"

        return raw_callsign
