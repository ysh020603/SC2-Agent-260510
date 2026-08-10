import asyncio
import subprocess
import sys
import weakref

import pytest
import sc2.sc2process as sc2process_module
from sc2.protocol import Protocol, ProtocolResponseTimeoutError
from sc2.sc2process import (
    SC2Process,
    allow_global_wineserver_kill,
    kill_owned_stalled_process,
    terminate_owned_process,
)


def test_global_wineserver_kill_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SC2_ALLOW_GLOBAL_WINESERVER_KILL", raising=False)
    assert allow_global_wineserver_kill() is False


def test_global_wineserver_kill_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("SC2_ALLOW_GLOBAL_WINESERVER_KILL", "1")
    assert allow_global_wineserver_kill() is True


class FakeProcess:
    def __init__(self, *, running=True, timeout=False):
        self.pid = 123
        self.running = running
        self.timeout = timeout
        self.terminated = 0
        self.killed = 0
        self.waits = []

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.terminated += 1

    def wait(self, timeout=None):
        self.waits.append(timeout)
        if self.timeout and timeout is not None:
            self.timeout = False
            raise subprocess.TimeoutExpired("SC2", timeout)
        self.running = False
        return 0

    def kill(self):
        self.killed += 1


def test_owned_process_cleanup_terminates_only_that_process():
    process = FakeProcess()
    assert terminate_owned_process(process, timeout_seconds=0.2) is True
    assert process.terminated == 1
    assert process.killed == 0


def test_owned_process_cleanup_escalates_after_bounded_wait():
    process = FakeProcess(timeout=True)
    assert terminate_owned_process(process, timeout_seconds=0.2) is True
    assert process.terminated == 1
    assert process.killed == 1
    assert process.waits == [0.2, None]


def test_owned_process_cleanup_ignores_already_exited_process():
    process = FakeProcess(running=False)
    assert terminate_owned_process(process) is False
    assert process.terminated == 0


def test_stalled_process_cleanup_skips_sigterm_handler():
    process = FakeProcess()
    assert kill_owned_stalled_process(process) is True
    assert process.terminated == 0
    assert process.killed == 1
    assert process.waits == [None]


def test_pending_response_is_killed_before_transport_close(monkeypatch):
    events = []

    class Controller:
        has_pending_response = True
        pending_request_type = "observation"

        async def drain_pending_response(self, _timeout):
            events.append("drain")
            return False

    class Transport:
        async def close(self):
            events.append("transport_close")

    process = FakeProcess()

    def kill_owned(owned):
        assert owned is process
        events.append("kill")
        owned.running = False
        return True

    monkeypatch.setattr(sc2process_module, "kill_owned_stalled_process", kill_owned)
    sc2_process = object.__new__(SC2Process)
    sc2_process._port = 12345
    sc2_process._controller = Controller()
    sc2_process._process = process
    sc2_process._ws = Transport()
    sc2_process._session = None
    sc2_process._protocols = weakref.WeakSet()

    asyncio.run(sc2_process._close_connection())
    assert events == ["drain", "kill", "transport_close"]


def test_client_pending_state_is_killed_before_controller_transport_close(monkeypatch):
    events = []

    class StartupController:
        has_pending_response = False

    class Transport:
        async def close(self):
            events.append("transport_close")

    process = FakeProcess()

    def kill_owned(owned):
        assert owned is process
        events.append("kill")
        owned.running = False
        return True

    monkeypatch.setattr(sc2process_module, "kill_owned_stalled_process", kill_owned)
    sc2_process = object.__new__(SC2Process)
    sc2_process._port = 12345
    sc2_process._controller = StartupController()
    sc2_process._process = process
    sc2_process._ws = Transport()
    sc2_process._session = None
    sc2_process._protocols = weakref.WeakSet()
    sc2_process._protocol_request_in_flight = True
    sc2_process._protocol_request_timed_out = True
    sc2_process._protocol_request_type = "observation"

    asyncio.run(sc2_process._close_connection())
    assert events == ["kill", "transport_close"]


def test_match_protocol_timeout_propagates_to_process_cleanup(monkeypatch):
    events = []

    class StartupController:
        has_pending_response = False

    class SharedTransport:
        def __init__(self):
            self.release = asyncio.Event()

        async def send_bytes(self, _payload):
            return None

        async def receive_bytes(self):
            await self.release.wait()
            return b""

        async def close(self):
            events.append("transport_close")
            self.release.set()

    process = FakeProcess()

    def kill_owned(owned):
        assert owned is process
        events.append("kill")
        owned.running = False
        return True

    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setattr(sc2process_module, "kill_owned_stalled_process", kill_owned)
    sc2_process = object.__new__(SC2Process)
    sc2_process._port = 12345
    sc2_process._controller = StartupController()
    sc2_process._process = process
    sc2_process._ws = None
    sc2_process._session = None
    sc2_process._protocols = weakref.WeakSet()
    sc2_process._protocol_request_in_flight = False
    sc2_process._protocol_request_timed_out = False
    sc2_process._protocol_request_type = None
    async def run_timeout_and_cleanup():
        transport = SharedTransport()
        sc2_process._ws = transport
        match_client = Protocol(transport, process=sc2_process)
        with pytest.raises(ProtocolResponseTimeoutError):
            await match_client.ping()
        assert sc2_process._protocol_request_timed_out is True
        assert sc2_process._protocol_request_type == "ping"
        await sc2_process._close_connection()

    asyncio.run(run_timeout_and_cleanup())
    assert events == ["kill", "transport_close"]


def test_timeout_aborts_owned_process_and_reaps_match_receiver(monkeypatch):
    events = []

    class SharedTransport:
        async def send_bytes(self, _payload):
            return None

        async def receive_bytes(self):
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                events.append("receive_cancel")
                raise

    process = FakeProcess()

    def kill_owned(owned):
        assert owned is process
        events.append("kill")
        owned.running = False
        return True

    monkeypatch.setenv("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "0.01")
    monkeypatch.setattr(sc2process_module, "kill_owned_stalled_process", kill_owned)
    sc2_process = object.__new__(SC2Process)
    sc2_process._process = process
    sc2_process._protocols = weakref.WeakSet()
    sc2_process._protocol_request_in_flight = False
    sc2_process._protocol_request_timed_out = False
    sc2_process._protocol_request_type = None
    client = Protocol(SharedTransport(), process=sc2_process)

    async def run_timeout():
        with pytest.raises(ProtocolResponseTimeoutError):
            await client.ping()

    asyncio.run(run_timeout())
    assert events == ["kill", "receive_cancel"]
    assert client.has_pending_response is False
    assert sc2_process._protocol_request_timed_out is True


def test_owned_process_cleanup_does_not_touch_peer_process():
    owned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    peer = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert terminate_owned_process(owned, timeout_seconds=2.0) is True
        assert owned.poll() is not None
        assert peer.poll() is None
    finally:
        if owned.poll() is None:
            owned.kill()
            owned.wait()
        if peer.poll() is None:
            peer.terminate()
            peer.wait(timeout=2.0)
