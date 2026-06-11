"""Tests for ATC trigger evaluator."""

import time

import pytest

from src.models.state import CallsignState, ExchangeEntry
from src.models.telemetry import Telemetry
from src.services.triggers import TriggerEvaluator


class FakeNav:
    def get_airport(self, icao):
        return None
    def get_country_code(self, icao):
        return None
    def nearest_airport(self, lat, lon, radius_nm=50, min_type="small_airport", exclude_icao=None):
        return None
    def nearest_airports(self, lat, lon, radius_nm=50, limit=5):
        return []
    def get_runways(self, icao):
        return []
    def get_frequency(self, icao, freq_type):
        return None
    def country_from_position(self, lat, lon):
        return None


@pytest.fixture
def evaluator():
    return TriggerEvaluator(nav=FakeNav())


def make_state(
    callsign="DAL123",
    alt=35000,
    heading=270,
    speed=450,
    vs=0,
    on_ground=False,
    squawk=None,
) -> CallsignState:
    state = CallsignState(callsign)
    state.latest_telemetry = Telemetry(
        callsign=callsign,
        latitude=48.35,
        longitude=11.78,
        altitude_ft=alt,
        heading=heading,
        speed_kts=speed,
        vertical_speed_fpm=vs,
        on_ground=on_ground,
        transponder_code=squawk,
        flight_rules="IFR",
    )
    return state


def test_emergency_squawk_7700(evaluator):
    state = make_state(squawk=7700)
    result = evaluator.check_emergency(state)
    assert result.should_fire is True
    assert "7700" in result.reason


def test_emergency_mayday_in_history(evaluator):
    state = make_state()
    state.add_exchange(ExchangeEntry("center", "MAYDAY MAYDAY MAYDAY engine failure", 1000))
    result = evaluator.check_emergency(state)
    assert result.should_fire is True


def test_no_emergency(evaluator):
    state = make_state(squawk=1234)
    result = evaluator.check_emergency(state)
    assert result.should_fire is False


def test_altitude_deviation(evaluator):
    state = make_state(alt=35250)
    state.last_assigned_alt = 35000
    result = evaluator.check_altitude_deviation(state)
    assert result.should_fire is True
    assert "altitude deviation" in result.reason.lower()


def test_no_altitude_deviation(evaluator):
    state = make_state(alt=35050)
    state.last_assigned_alt = 35000
    result = evaluator.check_altitude_deviation(state)
    assert result.should_fire is False


def test_heading_deviation(evaluator):
    state = make_state(heading=290)
    state.last_assigned_heading = 270
    result = evaluator.check_heading_deviation(state)
    assert result.should_fire is True
    assert "heading deviation" in result.reason.lower()


def test_no_heading_deviation(evaluator):
    state = make_state(heading=275)
    state.last_assigned_heading = 270
    result = evaluator.check_heading_deviation(state)
    assert result.should_fire is False


def test_squawk_assignment(evaluator):
    state = make_state(squawk=0)
    result = evaluator.check_squawk_assignment(state)
    assert result.should_fire is True


def test_squawk_already_assigned(evaluator):
    state = make_state(squawk=4721)
    state.add_exchange(ExchangeEntry("center", "DAL123, squawk 4721", 1000, is_push=True))
    result = evaluator.check_squawk_assignment(state)
    assert result.should_fire is False


def test_evaluate_all_cooldown(evaluator):
    state = make_state(squawk=0)
    state.last_push_time = time.time()  # just now
    result = evaluator.evaluate_all(state)
    assert result is None  # cooldown active


def test_evaluate_all_no_telemetry(evaluator):
    state = CallsignState("DAL123")
    result = evaluator.evaluate_all(state)
    assert result is None
