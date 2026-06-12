"""ATC exchange orchestrator — ties STT + LLM + TTS + telemetry together."""

import logging
import re
import time
from typing import Optional

from src.models.state import CallsignState, ExchangeEntry
from src.services.airline_db import AirlineDB
from src.services.llm import LLMService
from src.services.nav import NavDatabase, _haversine
from src.services.stt import STTService
from src.services.tts import TTSService

logger = logging.getLogger("openatc.session")

_CALLSIGN_PARSE = re.compile(r"^([A-Za-z0-9]{2,3})(\d{1,4})$")


def _format_callsign(callsign: str, airline_db: AirlineDB) -> str:
    """Format a callsign for display in the prompt with telephony resolution."""
    resolved = airline_db.resolve(callsign)
    if resolved != callsign:
        return f"{callsign} ({resolved})"
    return callsign


class ATCSession:
    """Orchestrates one ATC exchange.

    1. Receive Opus audio buffer from client
    2. Decode -> STT transcription
    3. Determine ATC role from context (telemetry, position, nav data)
    4. Build LLM prompt with system prompt + country procedures + history
    5. Stream LLM response back to client as text
    6. Synthesize TTS audio from response
    7. Stream TTS audio back to client
    8. Store exchange in history
    """

    def __init__(
        self,
        stt: STTService,
        llm: LLMService,
        tts: TTSService,
        nav: NavDatabase,
        airline_db: AirlineDB,
    ):
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.nav = nav
        self.airline_db = airline_db

    def determine_role(self, state: CallsignState) -> str:
        """Determine which ATC role should handle this transmission.

        Uses altitude, position relative to airports, and flight phase.
        """
        tel = state.latest_telemetry
        if tel is None:
            return "center"

        alt = tel.altitude_ft
        on_ground = tel.on_ground
        if on_ground or alt < 500:
            # Find nearest airport for ground/tower/delivery
            apt = self.nav.nearest_airport(tel.latitude, tel.longitude, radius_nm=5)
            if apt:
                # Check for delivery (pre-flight clearance) — not yet in history
                if len(state.history) == 0:
                    return "delivery"
                # On ground → ground
                if on_ground:
                    return "ground"
                # Below 500ft and in pattern → tower
                return "tower"
            return "center"

        if alt <= 10000:
            # Within 40nm of destination → approach
            if tel.dest_icao:
                dest = self.nav.get_airport(tel.dest_icao)
                if dest:
                    d = _haversine(
                        tel.latitude, tel.longitude,
                        dest.latitude, dest.longitude
                    )
                    if d <= 40:
                        return "approach"
            # Near departure airport → departure
            if tel.origin_icao:
                origin = self.nav.get_airport(tel.origin_icao)
                if origin:
                    d = _haversine(
                        tel.latitude, tel.longitude,
                        origin.latitude, origin.longitude
                    )
                    if d <= 20:
                        return "departure"
            return "approach"

        return "center"

    @staticmethod
    def _nearest_atis_freq(nav: NavDatabase, tel) -> Optional[float]:
        if tel is None:
            return None
        apt = nav.nearest_airport(tel.latitude, tel.longitude, radius_nm=50)
        if not apt:
            return None
        return nav.get_frequency(apt.icao, "ATIS")

    def build_country_context(self, state: CallsignState) -> str:
        """Get country-specific phraseology from nearest airport."""
        tel = state.latest_telemetry
        if tel is None:
            return ""

        country = self.nav.country_from_position(tel.latitude, tel.longitude)
        if not country:
            return ""

        try:
            from pathlib import Path
            proc_path = (
                Path(__file__).parent.parent
                / "prompts" / "procedures" / f"{country.lower()}.md"
            )
            if proc_path.exists():
                return proc_path.read_text()
        except Exception:
            pass

        return ""

    def build_system_prompt(self, state: CallsignState, role: str) -> str:
        """Build the full system prompt with role, country context, and rules."""
        tel = state.latest_telemetry
        country_context = self.build_country_context(state)

        prompt_parts = [
            "You are an Air Traffic Controller. Follow these rules strictly:",
            "",
            "1. Use standard ICAO English phraseology at all times.",
            "2. Always address the aircraft by its full callsign on first contact.",
            "3. CALLSIGN FORMAT: callsigns consist of an airline code + flight number.",
            '   Say the airline telephony name followed by individual digits.',
            '   Example: "SK123" is spoken as "Scandinavian one two three",',
            '   and "DAL456" is spoken as "Delta four five six".',
            "   After first contact you may abbreviate (e.g., 'Speedbird one' after 'Speedbird one two three').",
            "4. Use 'FL' followed by three digits for altitudes above transition altitude.",
            "5. Use 'feet' for altitudes below transition altitude.",
            "6. Use 'left/right heading XXX' for heading instructions.",
            "7. Use 'reduce/increase speed to XXX knots' for speed.",
            "8. Use 'Contact [position] on XXX.XXX' for frequency changes.",
            "9. Do NOT add any meta-commentary, explanations, or text outside the ATC message.",
            "10. Do NOT ask questions — issue instructions.",
            "11. Keep responses concise — one or two sentences maximum.",
            "12. Never use casual language like 'okay', 'got it', 'sure', 'alright'.",
            "13. Never say 'thank you' or 'please'.",
            f"14. Your current role is: {role.upper()}",
            "",
        ]

        if country_context:
            prompt_parts.append("LOCAL PROCEDURES:")
            prompt_parts.append(country_context)
            prompt_parts.append("")

        # Add recent exchange history
        if state.history:
            prompt_parts.append("RECENT EXCHANGE HISTORY (most recent first):")
            for entry in reversed(state.history[-5:]):
                direction = "ATC" if entry.is_push else "PILOT"
                prompt_parts.append(f"  [{direction}] {entry.text}")
            prompt_parts.append("")

        # Add current aircraft state
        if tel:
            prompt_parts.append("CURRENT AIRCRAFT STATE:")
            prompt_parts.append(f"  Callsign: {_format_callsign(tel.callsign, self.airline_db)}")
            prompt_parts.append(f"  Position: {tel.latitude:.4f}, {tel.longitude:.4f}")
            prompt_parts.append(f"  Altitude: {tel.altitude_ft:.0f} ft")
            prompt_parts.append(f"  Heading: {tel.heading:.0f}°")
            prompt_parts.append(f"  Speed: {tel.speed_kts:.0f} kts")
            prompt_parts.append(f"  Vertical Speed: {tel.vertical_speed_fpm:.0f} fpm")
            prompt_parts.append(f"  On Ground: {'Yes' if tel.on_ground else 'No'}")
            if tel.origin_icao:
                prompt_parts.append(f"  Origin: {tel.origin_icao}")
            if tel.dest_icao:
                prompt_parts.append(f"  Destination: {tel.dest_icao}")
            if tel.flight_rules:
                prompt_parts.append(f"  Flight Rules: {tel.flight_rules}")
            if state.last_assigned_heading is not None:
                prompt_parts.append(f"  Last Assigned Heading: {state.last_assigned_heading}°")
            if state.last_assigned_alt is not None:
                prompt_parts.append(f"  Last Assigned Altitude: FL{state.last_assigned_alt // 100}")
            prompt_parts.append("")

        # Nearby ATIS frequency
        atis_freq = self._nearest_atis_freq(self.nav, tel)
        if atis_freq:
            prompt_parts.append(f"ATIS available on {atis_freq:.3f} MHz for the nearest airport.")

        # ATIS handling
        prompt_parts.append("ATIS (AUTOMATIC TERMINAL INFORMATION SERVICE):")
        prompt_parts.append("  - If the pilot requests ATIS, information, or airport weather,")
        prompt_parts.append("    generate a standard ATIS report.")
        prompt_parts.append("  - ATIS format: [airport] information [letter], [time] Zulu,")
        prompt_parts.append("    runway [number], wind [dir]/[speed], visibility [distance],")
        prompt_parts.append("    weather [conditions], temperature [temp], dewpoint [dew],")
        prompt_parts.append("    QNH [altimeter], advise pilot to advise on initial contact.")
        prompt_parts.append("  - If no ATIS frequency is listed, instruct pilot to monitor")
        prompt_parts.append("    the appropriate frequency for the information.")
        prompt_parts.append("  - Use realistic but varied weather that matches the aircraft's")
        prompt_parts.append("    location and season.")
        prompt_parts.append("  - Issue a new information letter each time (A, B, C...).")
        prompt_parts.append("")

        # Emergency detection
        prompt_parts.append("EMERGENCY HANDLING:")
        prompt_parts.append("  - If pilot says MAYDAY or PAN-PAN: acknowledge immediately,")
        prompt_parts.append("    clear the frequency, and provide emergency instructions.")
        prompt_parts.append("  - Prioritize emergency aircraft above all others.")
        prompt_parts.append("")

        prompt_parts.append(
            "Respond only with the ATC message. Do not prefix or suffix with anything else."
        )

        return "\n".join(prompt_parts)

    async def process_audio(
        self,
        state: CallsignState,
        audio_frames: list[bytes],
    ) -> tuple[str, str]:
        """Process audio transmission through STT + LLM + TTS.

        Args:
            state: Current callsign state
            audio_frames: List of raw Opus frame bytes from client

        Returns:
            Tuple of (transcription, atc_response)
        """
        role = self.determine_role(state)
        system_prompt = self.build_system_prompt(state, role)

        # STT
        logger.info(f"Transcribing audio for {state.callsign}...")
        transcription = self.stt.transcribe(audio_frames)
        logger.info(f"Transcription ({state.callsign}): {transcription}")

        # LLM
        llm_messages = [
            {"role": "user", "content": transcription},
        ]
        logger.info(f"Generating ATC response for {state.callsign}...")
        atc_response = await self.llm.generate_sync(system_prompt, llm_messages)
        logger.info(f"ATC response ({state.callsign}): {atc_response}")

        # Store exchange
        now = time.time()
        state.add_exchange(ExchangeEntry(
            role=role,
            text=transcription,
            timestamp=now,
            is_push=False,
        ))
        state.add_exchange(ExchangeEntry(
            role=role,
            text=atc_response,
            timestamp=now,
            is_push=True,
        ))

        return transcription, atc_response
