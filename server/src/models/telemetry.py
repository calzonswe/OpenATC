from typing import Optional

from pydantic import BaseModel


class Telemetry(BaseModel):
    callsign: str
    latitude: float
    longitude: float
    altitude_ft: float
    heading: float
    speed_kts: float
    vertical_speed_fpm: float
    on_ground: bool
    transponder_code: Optional[int] = None
    origin_icao: Optional[str] = None
    dest_icao: Optional[str] = None
    flight_rules: Optional[str] = None  # IFR / VFR
    timestamp: float = 0.0
