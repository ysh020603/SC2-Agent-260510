import asyncio

import pytest
from s2clientprotocol import sc2api_pb2 as sc_pb

from sc2.data import Status

from sc2.protocol import (
    Protocol,
    ProtocolError,
    ProtocolResponsePendingError,
    ProtocolResponseTimeoutError,
    SC2MatchFatalError,
    SC2ProcessExitedError,
)


class _NeverRespondingWebSocket:
    async def send_bytes(self, _payload):
        return None

    async def receive_bytes(self):
        await asyncio.Event().wait()


class _DeadSC2Process:
    def diagnostic_snapshot(self):
        return {
            "pid": 123,
            "port": 456,
            "returncode": -9,
            "stderr_tail": "client crashed",
        }


class _OverlapDetectingWebSocket:
    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0

    async def send_bytes(self, _payload):
        return None

    async def receive_bytes(self):
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            return sc_pb.Response(status=Status.launched.value).SerializeToString()
        finally:
            self.in_flight -= 1


class _ControllableWebSocket:
    def __init__(self):
        self.release = asyncio.Event()
        self.receive_cancelled = False
        self.send_count = 0

    async def send_bytes(self, _payload):
        self.send_count += 1

    async def receive_bytes(self):
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.receive_cancelled = True
            raise
        return sc_pb.Response(status=Status.launched.value).SerializeToString()


@pytest.mark.parametrize(
    "error_type", (ProtocolResponseTimeoutError, SC2ProcessExitedError)
)
def test_transport_failures_cannot_be_swallowed_by_business_handlers(error_type):
    assert issubclass(error_type, SC2MatchFatalError)
    assert issubclass(error_type, BaseException)
    assert not issubclass(error_type, Exception)
    assert not issubclass(error_type, ProtocolError)

    business_handler_ran = False
    try:
        raise error_type("fatal transport")
    except Exception:
        business_handler_ran = True
    except SC2MatchFatalError:
        pass

    assert business_handler_ran is False


def test_protocol_constructs_single_flight_request_lock_lazily():
    protocol = Protocol(_NeverRespondingWebSocket())
    assert protocol._request_lock is None


def test_protocol_serializes_concurrent_requests():
    websocket = _OverlapDetectingWebSocket()
    protocol = Protocol(websocket)

    async def run_requests():
        await asyncio.gather(protocol.ping(), protocol.ping())

    asyncio.run(run_requests())
    assert protocol._request_lock is not None
    assert websocket.max_in_flight == 1


def test_protocol_response_timeout_is_bounded(monkeypatch):
    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "0.01")
    protocol = Protocol(_NeverRespondingWebSocket())

    async def run_request():
        await protocol.ping()

    with pytest.raises(
        ProtocolResponseTimeoutError, match="request_type=ping"
    ):
        asyncio.run(run_request())


def test_timeout_without_owned_process_cancels_receiver(monkeypatch):
    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "0.01")

    async def run_request():
        websocket = _ControllableWebSocket()
        protocol = Protocol(websocket)
        with pytest.raises(ProtocolResponseTimeoutError):
            await protocol.ping()
        assert protocol.has_pending_response is False
        assert websocket.receive_cancelled is True
        assert websocket.send_count == 1

    asyncio.run(run_request())


def test_observation_timeout_has_a_safer_default(monkeypatch):
    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "90")
    monkeypatch.delenv("SC2_PROTOCOL_OBSERVATION_TIMEOUT_SECONDS", raising=False)
    assert Protocol._timeout_seconds("ping") == 90
    assert Protocol._timeout_seconds("observation") == 120
    monkeypatch.setenv("SC2_PROTOCOL_OBSERVATION_TIMEOUT_SECONDS", "45")
    assert Protocol._timeout_seconds("observation") == 45


def test_protocol_fails_immediately_when_sc2_process_has_exited():
    protocol = Protocol(_NeverRespondingWebSocket(), process=_DeadSC2Process())

    async def run_request():
        await protocol.ping()

    with pytest.raises(SC2ProcessExitedError, match="client crashed"):
        asyncio.run(run_request())
