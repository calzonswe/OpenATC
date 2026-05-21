import csv
import math
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class Airport:
    icao: str
    name: str
    latitude: float
    longitude: float
    elevation_ft: Optional[float]
    continent: str
    country_code: str
    has_tower: bool
    has_approach: bool
    type: str  # large_airport, medium_airport, small_airport, heliport, closed


@dataclass
class Runway:
    airport_icao: str
    ident: str  # "08L", "26R", etc.
    length_ft: Optional[float]
    latitude: float
    longitude: float
    heading_deg: Optional[float]
    ils_freq: Optional[float]


@dataclass
class ComFrequency:
    airport_icao: str
    type: str  # TOWER, GROUND, APPROACH, DEPARTURE, CENTER, ATIS, etc.
    frequency_mhz: float


@dataclass
class Navaid:
    ident: str
    name: str
    type: str  # VOR, NDB, ILS, DME, etc.
    latitude: float
    longitude: float
    frequency_khz: Optional[float]


AIRPORT_TYPES_RELEVANT = {
    "large_airport",
    "medium_airport",
    "small_airport",
}


def _load_airports(path: str) -> dict[str, Airport]:
    airports: dict[str, Airport] = {}
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            icao = (row.get("ident") or "").strip().upper()
            if not icao or row.get("type") == "closed":
                continue
            airports[icao] = Airport(
                icao=icao,
                name=row.get("name", ""),
                latitude=float(row.get("latitude_deg") or 0),
                longitude=float(row.get("longitude_deg") or 0),
                elevation_ft=float(row["elevation_ft"]) if row.get("elevation_ft") else None,
                continent=row.get("continent", ""),
                country_code=row.get("iso_country", ""),
                has_tower=False,
                has_approach=False,
                type=row.get("type", ""),
            )
    return airports


def _load_runways(path: str) -> list[Runway]:
    runways: list[Runway] = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ils = float(row["ils_frequency"]) if row.get("ils_frequency") else None
            ident = (row.get("le_ident") or "").strip().upper()
            if not ident:
                continue
            runways.append(Runway(
                airport_icao=row.get("airport_ident", "").upper(),
                ident=ident,
                length_ft=float(row["length_ft"]) if row.get("length_ft") else None,
                latitude=float(row.get("le_latitude_deg") or 0),
                longitude=float(row.get("le_longitude_deg") or 0),
                heading_deg=float(row["le_heading_deg"]) if row.get("le_heading_deg") else None,
                ils_freq=ils if ils and ils > 0 else None,
            ))
    return runways


def _load_com_frequencies(path: str) -> list[ComFrequency]:
    freqs: list[ComFrequency] = []
    if not Path(path).exists():
        return freqs
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            freqs.append(ComFrequency(
                airport_icao=row.get("airport_ident", "").upper(),
                type=row.get("type", "").upper(),
                frequency_mhz=float(row.get("frequency_mhz", 0)),
            ))
    return freqs


def _load_navaids(path: str) -> list[Navaid]:
    navaids: list[Navaid] = []
    if not Path(path).exists():
        return navaids
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            navaids.append(Navaid(
                ident=row.get("ident", "").upper(),
                name=row.get("name", ""),
                type=row.get("type", ""),
                latitude=float(row.get("latitude_deg") or 0),
                longitude=float(row.get("longitude_deg") or 0),
                frequency_khz=float(row["frequency_khz"]) if row.get("frequency_khz") else None,
            ))
    return navaids


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3440.065  # nautical miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class NavDatabase:
    """Spatial navigation database for OpenATC.

    Loads airport, runway, frequency, and navaid data from OurAirports CSV files
    and provides spatial queries for ATC operations.
    """

    def __init__(self, data_dir: str = "data"):
        data_path = Path(data_dir)
        airports_csv = str(data_path / "airports.csv")
        runways_csv = str(data_path / "runways.csv")
        freqs_csv = str(data_path / "com_frequencies.csv")
        navaids_csv = str(data_path / "navaids.csv")

        self.airports = _load_airports(airports_csv)
        self.runways = _load_runways(runways_csv)
        self.frequencies = _load_com_frequencies(freqs_csv)
        self.navaids = _load_navaids(navaids_csv)
        self._airport_list = list(self.airports.values())

        # Index runways and frequencies by airport ICAO
        self._runways_by_airport: dict[str, list[Runway]] = {}
        for rw in self.runways:
            self._runways_by_airport.setdefault(rw.airport_icao, []).append(rw)

        self._freqs_by_airport: dict[str, list[ComFrequency]] = {}
        for f in self.frequencies:
            self._freqs_by_airport.setdefault(f.airport_icao, []).append(f)

    def get_airport(self, icao: str) -> Optional[Airport]:
        return self.airports.get(icao.upper())

    def get_runways(self, icao: str) -> list[Runway]:
        return self._runways_by_airport.get(icao.upper(), [])

    def get_runway(self, icao: str, ident: str) -> Optional[Runway]:
        ident = ident.upper()
        for rw in self.get_runways(icao):
            if rw.ident == ident:
                return rw
        return None

    def get_frequencies(self, icao: str, freq_type: Optional[str] = None) -> list[ComFrequency]:
        freqs = self._freqs_by_airport.get(icao.upper(), [])
        if freq_type:
            return [f for f in freqs if f.type == freq_type.upper()]
        return freqs

    def get_frequency(self, icao: str, freq_type: str) -> Optional[float]:
        freqs = self.get_frequencies(icao, freq_type)
        if freqs:
            return freqs[0].frequency_mhz
        return None

    def get_country_code(self, icao: str) -> Optional[str]:
        apt = self.get_airport(icao)
        return apt.country_code if apt else None

    def nearest_airport(
        self, lat: float, lon: float, radius_nm: float = 50.0,
        min_type: str = "small_airport",
        exclude_icao: Optional[str] = None,
    ) -> Optional[Airport]:
        best: Optional[Airport] = None
        best_dist = float("inf")
        type_rank = {"large_airport": 0, "medium_airport": 1, "small_airport": 2, "heliport": 3}

        target_rank = type_rank.get(min_type, 2)

        for apt in self._airport_list:
            if apt.type not in AIRPORT_TYPES_RELEVANT:
                continue
            if apt.type == "closed":
                continue
            if apt.type not in type_rank:
                continue
            if type_rank.get(apt.type, 99) > target_rank:
                continue
            if exclude_icao and apt.icao == exclude_icao.upper():
                continue
            d = _haversine(lat, lon, apt.latitude, apt.longitude)
            if d <= radius_nm and d < best_dist:
                best = apt
                best_dist = d
        return best

    def nearest_airports(
        self, lat: float, lon: float, radius_nm: float = 50.0,
        limit: int = 5,
    ) -> list[tuple[Airport, float]]:
        results: list[tuple[Airport, float]] = []
        for apt in self._airport_list:
            if apt.type not in AIRPORT_TYPES_RELEVANT:
                continue
            if apt.type == "closed":
                continue
            d = _haversine(lat, lon, apt.latitude, apt.longitude)
            if d <= radius_nm:
                results.append((apt, d))
        results.sort(key=lambda x: x[1])
        return results[:limit]

    def nearest_navaid(self, lat: float, lon: float, radius_nm: float = 50.0) -> Optional[Navaid]:
        best: Optional[Navaid] = None
        best_dist = float("inf")
        for nav in self.navaids:
            d = _haversine(lat, lon, nav.latitude, nav.longitude)
            if d <= radius_nm and d < best_dist:
                best = nav
                best_dist = d
        return best

    def country_from_position(self, lat: float, lon: float) -> Optional[str]:
        """Returns the country code based on the nearest medium/large airport."""
        apt = self.nearest_airport(lat, lon, radius_nm=50.0, min_type="medium_airport")
        return apt.country_code if apt else None
