import asyncio

import pytest
from s2clientprotocol import sc2api_pb2 as sc_pb

from sc2.data import Status

from sc2.protocol import Protocol, ProtocolResponseTimeoutError, SC2ProcessExitedError


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


def test_protocol_constructs_single_flight_request_lock():
    protocol = Protocol(_NeverRespondingWebSocket())
    assert protocol._request_lock is not None


def test_protocol_serializes_concurrent_requests():
    websocket = _OverlapDetectingWebSocket()
    protocol = Protocol(websocket)

    async def run_requests():
        await asyncio.gather(protocol.ping(), protocol.ping())

    asyncio.run(run_requests())
    assert websocket.max_in_flight == 1


def test_protocol_response_timeout_is_bounded(monkeypatch):
    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "0.01")
    protocol = Protocol(_NeverRespondingWebSocket())

    async def run_request():
        await protocol.ping()

    with pytest.raises(ProtocolResponseTimeoutError, match="timed out"):
        asyncio.run(run_request())


def test_protocol_fails_immediately_when_sc2_process_has_exited():
    protocol = Protocol(_NeverRespondingWebSocket(), process=_DeadSC2Process())

    async def run_request():
        await protocol.ping()

    with pytest.raises(SC2ProcessExitedError, match="client crashed"):
        asyncio.run(run_request())
