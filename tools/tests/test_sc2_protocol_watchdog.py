import asyncio

import pytest

from sc2.protocol import Protocol, ProtocolResponseTimeoutError


class _NeverRespondingWebSocket:
    async def send_bytes(self, _payload):
        return None

    async def receive_bytes(self):
        await asyncio.Event().wait()


def test_protocol_response_timeout_is_bounded(monkeypatch):
    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "0.01")
    protocol = Protocol(_NeverRespondingWebSocket())

    async def run_request():
        await protocol.ping()

    with pytest.raises(ProtocolResponseTimeoutError, match="timed out"):
        asyncio.run(run_request())
