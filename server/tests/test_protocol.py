"""Protocol tests — connection store logic and message serialization.

WebSocket integration tests use pytest-asyncio with a live test server.
"""
import json

from src.models.protocol import ClientMessage, MessageType, ServerMessage
from src.models.state import CallsignState, ExchangeEntry
from src.models.telemetry import Telemetry
from src.store.connection_store import ConnectionStore


class FakeWebSocket:
    def __init__(self):
        self.sent: list = []
    async def send_text(self, text: str):
        self.sent.append(("text", text))
    async def send_bytes(self, data: bytes):
        self.sent.append(("bytes", data))
    async def send_json(self, data):
        self.sent.append(("json", data))
    async def close(self):
        self.sent.append(("close",))


def fake_ws():
    return FakeWebSocket()


# --- Message model tests ---

def test_client_message_register():
    msg = ClientMessage(type=MessageType.REGISTER, callsign="DAL123")
    assert msg.type == MessageType.REGISTER
    assert msg.callsign == "DAL123"


def test_client_message_telemetry():
    msg = ClientMessage(
        type=MessageType.TELEMETRY,
        callsign="DAL123",
        payload={"latitude": 48.35, "longitude": 11.78},
    )
    assert msg.type == MessageType.TELEMETRY
    assert msg.payload["latitude"] == 48.35


def test_client_message_serialization():
    msg = ClientMessage(type=MessageType.REGISTER, callsign="DAL123")
    data = msg.model_dump_json()
    decoded = json.loads(data)
    assert decoded["type"] == "register"
    assert decoded["callsign"] == "DAL123"


def test_server_message():
    msg = ServerMessage(
        type=MessageType.ATC_TEXT,
        callsign="DAL123",
        text="DAL123, descend to FL180",
    )
    data = msg.model_dump_json()
    decoded = json.loads(data)
    assert decoded["text"] == "DAL123, descend to FL180"


# --- Connection store tests ---

def test_register_and_count():
    store = ConnectionStore()
    ws = fake_ws()
    ok = store.register(id(ws), ws, "DAL123")  # type: ignore
    assert ok is True
    assert store.count() == 1


def test_register_duplicate():
    store = ConnectionStore()
    ws1 = fake_ws()
    ws2 = fake_ws()
    store.register(id(ws1), ws1, "DAL123")  # type: ignore
    ok = store.register(id(ws2), ws2, "DAL123")  # type: ignore
    assert ok is False
    assert store.count() == 1


def test_unregister():
    store = ConnectionStore()
    ws = fake_ws()
    store.register(id(ws), ws, "DAL123")  # type: ignore
    store.unregister("DAL123")
    assert store.count() == 0


def test_get_state():
    store = ConnectionStore()
    ws = fake_ws()
    store.register(id(ws), ws, "DAL123")  # type: ignore
    state = store.get_state("DAL123")
    assert state is not None
    assert state.callsign == "DAL123"


def test_update_telemetry():
    store = ConnectionStore()
    ws = fake_ws()
    store.register(id(ws), ws, "DAL123")  # type: ignore

    tel = Telemetry(
        callsign="DAL123",
        latitude=48.35,
        longitude=11.78,
        altitude_ft=35000,
        heading=270,
        speed_kts=450,
        vertical_speed_fpm=0,
        on_ground=False,
    )
    store.update_telemetry("DAL123", tel)
    state = store.get_state("DAL123")
    assert state is not None
    assert state.latest_telemetry is not None
    assert state.latest_telemetry.altitude_ft == 35000


# --- CallsignState tests ---

def test_callsign_state_history():
    state = CallsignState("DAL123")
    state.add_exchange(ExchangeEntry("center", "DAL123, climb to FL350", 1000.0, assigned_alt=35000))
    assert len(state.history) == 1
    assert state.last_assigned_alt == 35000

    state.add_exchange(ExchangeEntry("center", "DAL123, turn left heading 270", 1001.0, assigned_heading=270))
    assert len(state.history) == 2
    assert state.last_assigned_heading == 270
    assert state.last_assigned_alt == 35000


def test_callsign_state_history_window():
    state = CallsignState("DAL123")
    for i in range(20):
        state.add_exchange(ExchangeEntry("center", f"msg {i}", float(i)), max_window=10)
    assert len(state.history) == 10
    assert state.history[0].text == "msg 10"
    assert state.history[-1].text == "msg 19"
