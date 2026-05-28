"""Server-initiated ATC triggers.

Evaluates telemetry against conditions and pushes unsolicited ATC instructions.
"""

import logging
import time
from typing import Optional

from src.models.state import CallsignState
from src.services.nav import NavDatabase, _haversine

logger = logging.getLogger("openatc.triggers")


class TriggerResult:
    def __init__(self, should_fire: bool, reason: str = "", role: str = "center"):
        self.should_fire = should_fire
        self.reason = reason
        self.role = role


class TriggerEvaluator:
    """Evaluates telemetry against ATC trigger conditions."""

    def __init__(self, nav: NavDatabase):
        self.nav = nav
        self.cooldown = 15.0  # seconds between pushes

    def check_emergency(self, state: CallsignState) -> TriggerResult:
        """Check if aircraft has declared an emergency."""
        tel = state.latest_telemetry
        if tel and tel.transponder_code == 7700:
            return TriggerResult(True, "Aircraft squawking 7700 emergency", "center")

        # Check last pilot transmission for MAYDAY/PAN-PAN
        for entry in reversed(state.history):
            if not entry.is_push:
                text = entry.text.upper()
                if "MAYDAY" in text or "PAN-PAN" in text:
                    return TriggerResult(
                        True,
                        "Pilot declared emergency in last transmission",
                        "center",
                    )
        return TriggerResult(False)

    def check_altitude_deviation(self, state: CallsignState) -> TriggerResult:
        """Check if aircraft deviates from last assigned altitude."""
        if state.last_assigned_alt is None:
            return TriggerResult(False)
        tel = state.latest_telemetry
        if tel is None:
            return TriggerResult(False)
        deviation = abs(tel.altitude_ft - state.last_assigned_alt)
        if deviation >= 200:
            return TriggerResult(
                True,
                f"Altitude deviation: assigned {state.last_assigned_alt:.0f} ft, "
                f"currently {tel.altitude_ft:.0f} ft (deviation {deviation:.0f} ft)",
                "center",
            )
        return TriggerResult(False)

    def check_heading_deviation(self, state: CallsignState) -> TriggerResult:
        """Check if aircraft deviates from last assigned heading."""
        if state.last_assigned_heading is None:
            return TriggerResult(False)
        tel = state.latest_telemetry
        if tel is None:
            return TriggerResult(False)
        diff = abs(tel.heading - state.last_assigned_heading)
        diff = min(diff, 360 - diff)  # normalize
        if diff > 10:
            # Check how long this has been going on — simplified: fire immediately
            return TriggerResult(
                True,
                f"Heading deviation: assigned {state.last_assigned_heading}°, "
                f"currently {tel.heading:.0f}° (diff {diff:.0f}°)",
                "center",
            )
        return TriggerResult(False)

    def check_departure_handoff(self, state: CallsignState) -> TriggerResult:
        """Handoff to departure when climbing through 10,000 ft."""
        tel = state.latest_telemetry
        if tel is None:
            return TriggerResult(False)
        if tel.vertical_speed_fpm > 0 and tel.altitude_ft >= 10000:
            # Check if already handed off
            for entry in reversed(state.history):
                if entry.is_push and "departure" in entry.role:
                    return TriggerResult(False)
            return TriggerResult(
                True,
                f"Aircraft climbed through FL100, handoff to departure",
                "departure",
            )
        return TriggerResult(False)

    def check_approach_handoff(self, state: CallsignState) -> TriggerResult:
        """Handoff to approach when within 40nm descending."""
        tel = state.latest_telemetry
        if tel is None or not tel.dest_icao:
            return TriggerResult(False)
        dest = self.nav.get_airport(tel.dest_icao)
        if not dest:
            return TriggerResult(False)

        d = _haversine(tel.latitude, tel.longitude, dest.latitude, dest.longitude)

        if d <= 40 and tel.altitude_ft <= 20000:
            for entry in reversed(state.history):
                if entry.is_push and "approach" in entry.role:
                    return TriggerResult(False)
            return TriggerResult(
                True,
                f"Aircraft {d:.0f}nm from {tel.dest_icao}, below FL200, handoff to approach",
                "approach",
            )
        return TriggerResult(False)

    def check_tower_handoff(self, state: CallsignState) -> TriggerResult:
        """Handoff to tower when within 10nm below 5,000 ft."""
        tel = state.latest_telemetry
        if tel is None or not tel.dest_icao:
            return TriggerResult(False)
        dest = self.nav.get_airport(tel.dest_icao)
        if not dest:
            return TriggerResult(False)

        d = _haversine(tel.latitude, tel.longitude, dest.latitude, dest.longitude)

        if d <= 10 and tel.altitude_ft <= 5000:
            for entry in reversed(state.history):
                if entry.is_push and "tower" in entry.role:
                    return TriggerResult(False)
            # Get tower frequency
            freq = self.nav.get_frequency(tel.dest_icao, "TOWER")
            freq_str = f" on {freq:.3f}" if freq else ""
            return TriggerResult(
                True,
                f"Aircraft {d:.0f}nm from {tel.dest_icao}, below 5000ft, handoff to tower{freq_str}",
                "tower",
            )
        return TriggerResult(False)

    def check_approach_clearance(self, state: CallsignState) -> TriggerResult:
        """Clear for ILS approach when on final."""
        tel = state.latest_telemetry
        if tel is None or not tel.dest_icao or tel.altitude_ft > 1000:
            return TriggerResult(False)
        dest = self.nav.get_airport(tel.dest_icao)
        if not dest:
            return TriggerResult(False)

        d = _haversine(tel.latitude, tel.longitude, dest.latitude, dest.longitude)

        if d <= 5:
            for entry in reversed(state.history):
                if "cleared" in entry.text.lower() and "approach" in entry.text.lower():
                    return TriggerResult(False)
            # Find best runway by heading alignment
            runways = self.nav.get_runways(tel.dest_icao)
            best_rwy = None
            best_diff = 360
            for rw in runways:
                if rw.heading_deg is not None:
                    diff = abs(tel.heading - rw.heading_deg)
                    diff = min(diff, 360 - diff)
                    if diff < best_diff:
                        best_diff = diff
                        best_rwy = rw
            rwy_str = f" Runway {best_rwy.ident}" if best_rwy else ""
            return TriggerResult(
                True,
                f"Aircraft on final approach to {tel.dest_icao}{rwy_str}, "
                f"{d:.0f}nm, cleared ILS approach",
                "tower",
            )
        return TriggerResult(False)

    def check_squawk_assignment(self, state: CallsignState) -> TriggerResult:
        """Assign squawk code on first contact."""
        tel = state.latest_telemetry
        if tel is None:
            return TriggerResult(False)
        if not tel.transponder_code or tel.transponder_code == 0:
            # Check if already assigned
            for entry in state.history:
                if "squawk" in entry.text.lower():
                    return TriggerResult(False)
            return TriggerResult(
                True,
                f"Aircraft {tel.callsign} has no transponder code, assign squawk",
                "center",
            )
        return TriggerResult(False)

    def check_airspace_infringement(self, state: CallsignState) -> TriggerResult:
        """Warn if aircraft enters controlled airspace without clearance."""
        tel = state.latest_telemetry
        if tel is None:
            return TriggerResult(False)

        # Find nearby controlled airports
        nearby = self.nav.nearest_airports(tel.latitude, tel.longitude, radius_nm=15, limit=3)
        for apt, d in nearby:
            if d < 5 and apt.type in ("large_airport", "medium_airport"):
                # Check if we've contacted them
                contacted = False
                for entry in state.history:
                    if apt.icao in entry.text.upper():
                        contacted = True
                        break
                if not contacted:
                    return TriggerResult(
                        True,
                        f"Aircraft within {d:.0f}nm of {apt.icao} "
                        f"({apt.name}) without clearance — possible airspace infringement",
                        "center",
                    )
        return TriggerResult(False)

    def evaluate_all(self, state: CallsignState) -> Optional[TriggerResult]:
        """Evaluate all triggers in priority order. Returns first that fires."""
        tel = state.latest_telemetry
        if tel is None:
            return None

        # Cooldown check
        now = time.time()
        if now - state.last_push_time < self.cooldown:
            return None

        triggers = [
            self.check_emergency,
            self.check_altitude_deviation,
            self.check_heading_deviation,
            self.check_airspace_infringement,
            self.check_approach_handoff,
            self.check_tower_handoff,
            self.check_approach_clearance,
            self.check_departure_handoff,
            self.check_squawk_assignment,
        ]

        for trigger_fn in triggers:
            result = trigger_fn(state)
            if result.should_fire:
                return result

        return None
