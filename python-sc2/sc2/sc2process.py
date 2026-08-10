from __future__ import annotations

import asyncio
import os
import os.path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

import aiohttp

# pyre-ignore[21]
import portpicker
from aiohttp.client_ws import ClientWebSocketResponse
from loguru import logger

from sc2 import paths, wsl
from sc2.controller import Controller
from sc2.paths import Paths
from sc2.versions import VERSIONS


def allow_global_wineserver_kill() -> bool:
    """Whether cleanup may terminate every Wine client owned by this user.

    This is deliberately opt-in.  ``wineserver -k`` is process-global, not
    match-local, and used to cascade one match cleanup into SIGTERM for every
    concurrent SC2 experiment.
    """

    return os.environ.get("SC2_ALLOW_GLOBAL_WINESERVER_KILL", "").strip() == "1"


def terminate_owned_process(process: subprocess.Popen, timeout_seconds: float = 10.0) -> bool:
    """Terminate only the SC2 process owned by this match.

    Returns true when termination was requested.  A stuck process is escalated
    to ``kill`` after a bounded wait; no process-name or Wine-global operation
    is used.
    """

    if process.poll() is not None:
        return False
    process.terminate()
    try:
        process.wait(timeout=max(0.1, float(timeout_seconds)))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    return True


def kill_owned_stalled_process(process: subprocess.Popen) -> bool:
    """Kill one owned process without invoking SC2's broken pending-response handler."""

    if process.poll() is not None:
        return False
    process.kill()
    process.wait()
    return True


class KillSwitch:
    _to_kill: list[Any] = []

    @classmethod
    def add(cls, value) -> None:
        logger.debug("kill_switch: Add switch")
        cls._to_kill.append(value)

    @classmethod
    def kill_all(cls) -> None:
        logger.info(f"kill_switch: Process cleanup for {len(cls._to_kill)} processes")
        for p in cls._to_kill:
            p._clean(verbose=False)


class SC2Process:
    """
    A class for handling SCII applications.

    :param host: hostname for the url the SCII application will listen to
    :param port: the websocket port the SCII application will listen to
    :param fullscreen: whether to launch the SCII application in fullscreen or not, defaults to False
    :param resolution: (window width, window height) in pixels, defaults to (1024, 768)
    :param placement: (x, y) the distances of the SCII app's top left corner from the top left corner of the screen
                       e.g. (20, 30) is 20 to the right of the screen's left border, and 30 below the top border
    :param render:
    :param sc2_version:
    :param base_build:
    :param data_hash:
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        fullscreen: bool = False,
        resolution: list[int] | tuple[int, int] | None = None,
        placement: list[int] | tuple[int, int] | None = None,
        render: bool = False,
        sc2_version: str | None = None,
        base_build: str | None = None,
        data_hash: str | None = None,
    ) -> None:
        assert isinstance(host, str) or host is None
        assert isinstance(port, int) or port is None

        self._render = render
        self._arguments: dict[str, str] = {"-displayMode": str(int(fullscreen))}
        if not fullscreen:
            if resolution and len(resolution) == 2:
                self._arguments["-windowwidth"] = str(resolution[0])
                self._arguments["-windowheight"] = str(resolution[1])
            if placement and len(placement) == 2:
                self._arguments["-windowx"] = str(placement[0])
                self._arguments["-windowy"] = str(placement[1])

        self._host = host or os.environ.get("SC2CLIENTHOST", "127.0.0.1")
        self._serverhost = os.environ.get("SC2SERVERHOST", self._host)

        if port is None:
            self._port = portpicker.pick_unused_port()
        else:
            self._port = port
        self._used_portpicker = bool(port is None)
        self._tmp_dir = tempfile.mkdtemp(prefix="SC2_")
        self._process: subprocess.Popen | None = None
        self._stderr_path = Path(self._tmp_dir) / "SC2.stderr.log"
        self._stderr_handle = None
        self._session = None
        self._ws = None
        self._controller = None
        self._protocol_request_in_flight = False
        self._protocol_request_timed_out = False
        self._protocol_request_type: str | None = None
        self._sc2_version = sc2_version
        self._base_build = base_build
        self._data_hash = data_hash

    async def __aenter__(self) -> Controller:
        KillSwitch.add(self)

        def signal_handler(*_args):
            # unused arguments: signal handling library expects all signal
            # callback handlers to accept two positional arguments
            KillSwitch.kill_all()

        signal.signal(signal.SIGINT, signal_handler)

        try:
            self._process = self._launch()
            self._ws = await self._connect()
        except:
            await self._close_connection()
            self._clean()
            raise

        self._controller = Controller(self._ws, self)
        return self._controller

    async def __aexit__(self, *args) -> None:
        await self._close_connection()
        KillSwitch.kill_all()
        signal.signal(signal.SIGINT, signal.SIG_DFL)

    def protocol_request_started(self, request_type: str) -> None:
        self._protocol_request_in_flight = True
        self._protocol_request_timed_out = False
        self._protocol_request_type = request_type

    def protocol_request_finished(self, request_type: str | None = None) -> None:
        if request_type is None or request_type == self._protocol_request_type:
            self._protocol_request_in_flight = False

    def protocol_request_timed_out(self, request_type: str) -> None:
        self._protocol_request_in_flight = True
        self._protocol_request_timed_out = True
        self._protocol_request_type = request_type

    @property
    def ws_url(self) -> str:
        return f"ws://{self._host}:{self._port}/sc2api"

    @property
    def versions(self):
        """Opens the versions.json file which origins from
        https://github.com/Blizzard/s2client-proto/blob/master/buildinfo/versions.json"""
        return VERSIONS

    def find_data_hash(self, target_sc2_version: str) -> str | None:
        """Returns the data hash from the matching version string."""
        version: dict
        for version in self.versions:
            if version["label"] == target_sc2_version:
                return version["data-hash"]
        return None

    def find_base_dir(self, target_sc2_version: str) -> str | None:
        """Returns the base directory from the matching version string."""
        version: dict
        for version in self.versions:
            if version["label"] == target_sc2_version:
                return "Base" + str(version["base-version"])
        return None

    def _launch(self):
        if self._sc2_version and not self._base_build:
            self._base_build = self.find_base_dir(self._sc2_version)

        if self._base_build:
            executable = str(paths.latest_executeble(Paths.BASE / "Versions", self._base_build))
        else:
            executable = str(Paths.EXECUTABLE)

        if self._port is None:
            self._port = portpicker.pick_unused_port()
            self._used_portpicker = True
        args = paths.get_runner_args(Paths.CWD) + [
            executable,
            "-listen",
            self._serverhost,
            "-port",
            str(self._port),
            "-dataDir",
            str(Paths.BASE),
            "-tempDir",
            self._tmp_dir,
        ]
        for arg, value in self._arguments.items():
            args.append(arg)
            args.append(value)
        if self._sc2_version:

            def special_match(strg: str):
                """Tests if the specified version is in the versions.py dict."""
                return any(version["label"] == strg for version in self.versions)

            valid_version_string = special_match(self._sc2_version)
            if valid_version_string:
                self._data_hash = self.find_data_hash(self._sc2_version)
                assert self._data_hash is not None, (
                    f"StarCraft 2 Client version ({self._sc2_version}) was not found inside sc2/versions.py file. Please check your spelling or check the versions.py file."
                )

            else:
                logger.warning(
                    f'The submitted version string in sc2.rungame() function call (sc2_version="{self._sc2_version}") was not found in versions.py. Running latest version instead.'
                )

        if self._data_hash:
            args.extend(["-dataVersion", self._data_hash])

        if self._render:
            args.extend(["-eglpath", "libEGL.so"])

        # The pinned Linux client can emit hundreds of megabytes per minute in
        # verbose mode after a protocol fault. Keep fatal stderr diagnostics,
        # but make the firehose an explicit troubleshooting opt-in.
        if os.environ.get("SC2_VERBOSE_LOG", "").strip() == "1":
            args.append("-verbose")

        sc2_cwd = str(Paths.CWD) if Paths.CWD else None

        if paths.PF in {"WSL1", "WSL2"}:
            return wsl.run(args, sc2_cwd)

        # Keep the client diagnostics until cleanup.  The previous DEVNULL
        # redirection made mid-game client exits impossible to distinguish
        # from a slow websocket response.
        self._stderr_handle = self._stderr_path.open("wb")
        return subprocess.Popen(
            args,
            cwd=sc2_cwd,
            stderr=self._stderr_handle,
            # , env=run_config.env
        )

    def diagnostic_snapshot(self, tail_bytes: int = 4096) -> dict[str, Any]:
        """Return bounded process diagnostics safe to copy into match logs."""

        return_code = self._process.poll() if self._process is not None else None
        stderr_tail = ""
        try:
            if self._stderr_handle is not None:
                self._stderr_handle.flush()
            if self._stderr_path.is_file():
                with self._stderr_path.open("rb") as handle:
                    handle.seek(0, os.SEEK_END)
                    size = handle.tell()
                    handle.seek(max(0, size - max(1, int(tail_bytes))))
                    stderr_tail = handle.read().decode("utf-8", errors="replace")
        except OSError as exc:
            stderr_tail = f"<stderr unavailable: {exc}>"
        return {
            "pid": self._process.pid if self._process is not None else None,
            "port": self._port,
            "returncode": return_code,
            "protocol_request_in_flight": self._protocol_request_in_flight,
            "protocol_request_timed_out": self._protocol_request_timed_out,
            "protocol_request_type": self._protocol_request_type,
            "stderr_tail": stderr_tail[-tail_bytes:],
        }

    async def _connect(self) -> ClientWebSocketResponse:
        # How long to wait for SC2 to publish its websocket endpoint.  Keep
        # the historical 180-second default, but make it configurable for
        # batch runners and fail immediately when the client has already
        # exited.  Previously a launch crash was indistinguishable from a
        # slow startup and consumed the full three-minute wait.
        try:
            startup_timeout = max(
                1.0, float(os.environ.get("SC2_STARTUP_TIMEOUT", "180"))
            )
        except (TypeError, ValueError):
            startup_timeout = 180.0
        deadline = asyncio.get_running_loop().time() + startup_timeout
        attempt = 0
        while asyncio.get_running_loop().time() < deadline:
            if self._process is None:
                # The ._clean() was called, clearing the process
                logger.debug("Process cleanup complete, exit")
                sys.exit()
            return_code = self._process.poll()
            if return_code is not None:
                raise RuntimeError(
                    f"SC2 process exited before websocket startup "
                    f"(return code {return_code}, port {self._port})"
                )

            await asyncio.sleep(1)
            try:
                self._session = aiohttp.ClientSession()
                ws = await self._session.ws_connect(self.ws_url, timeout=120)
                # FIXME fix deprecation warning in for future aiohttp version
                # ws = await self._session.ws_connect(
                #     self.ws_url, timeout=aiohttp.client_ws.ClientWSTimeout(ws_close=120)
                # )
                logger.debug("Websocket connection ready")
                return ws
            except aiohttp.client_exceptions.ClientConnectorError:
                await self._session.close()
                attempt += 1
                if attempt > 15:
                    logger.debug("Connection refused (startup not complete (yet))")

        logger.debug("Websocket connection to SC2 process timed out")
        raise TimeoutError(
            f"SC2 websocket startup timed out after {startup_timeout:g}s "
            f"(port {self._port})"
        )

    async def _close_connection(self) -> None:
        logger.info(f"Closing connection at {self._port}...")

        if self._controller is not None and self._controller.has_pending_response:
            try:
                drain_timeout = max(
                    0.0,
                    float(os.environ.get("SC2_PROTOCOL_DRAIN_TIMEOUT_SECONDS", "10")),
                )
            except (TypeError, ValueError):
                drain_timeout = 10.0
            drained = await self._controller.drain_pending_response(drain_timeout)
            if not drained:
                logger.error(
                    "SC2 response still pending during cleanup: request_type={} "
                    "drain_timeout_seconds={}",
                    self._controller.pending_request_type,
                    drain_timeout,
                )
                # Closing the websocket first makes the legacy Linux client
                # enter the same broken pending-response shutdown path as
                # SIGTERM. Kill this exact owned client before closing the
                # transport; sibling clients and the shared Wine server are
                # deliberately untouched.
                if (
                    self._process is not None
                    and self._process.poll() is None
                    and paths.PF not in {"WSL1", "WSL2"}
                ):
                    kill_owned_stalled_process(self._process)
        elif (
            self._process is not None
            and self._process.poll() is None
            and (self._protocol_request_in_flight or self._protocol_request_timed_out)
            and paths.PF not in {"WSL1", "WSL2"}
        ):
            # The game Client and the startup Controller share a websocket but
            # are distinct Protocol objects. A match request can therefore be
            # pending even when Controller.has_pending_response is false. The
            # process-level callbacks are the authoritative cross-Protocol
            # signal; kill the exact owned client before aiohttp ws.close(),
            # which otherwise busy-spins while the Client receive is pending.
            logger.warning(
                "Force-killing owned SC2 before transport close: pid={} "
                "request_type={} timed_out={}",
                self._process.pid,
                self._protocol_request_type,
                self._protocol_request_timed_out,
            )
            kill_owned_stalled_process(self._process)

        if self._ws is not None:
            try:
                await asyncio.wait_for(self._ws.close(), timeout=5.0)
            except (asyncio.TimeoutError, RuntimeError):
                logger.warning("Timed out closing SC2 websocket at {}", self._port)

        if self._session is not None:
            await self._session.close()

    def _clean(self, verbose: bool = True) -> None:
        if verbose:
            logger.info("Cleaning up...")

        if self._process is not None:
            assert isinstance(self._process, subprocess.Popen)
            diagnostics = self.diagnostic_snapshot()
            if paths.PF in {"WSL1", "WSL2"}:
                if wsl.kill(self._process):
                    logger.error("KILLED")
            elif self._process.poll() is None and (
                self._protocol_request_in_flight or self._protocol_request_timed_out
            ):
                # SIGTERM enters the legacy SC2 shutdown handler. If a response
                # is pending that handler crashes with signal 11. A direct,
                # match-local SIGKILL avoids the broken native cleanup path and
                # never affects sibling SC2 clients.
                logger.warning(
                    "Force-killing owned stalled SC2 process pid={} "
                    "request_type={} timed_out={}",
                    self._process.pid,
                    self._protocol_request_type,
                    self._protocol_request_timed_out,
                )
                kill_owned_stalled_process(self._process)
            elif self._process.poll() is None:
                for _ in range(3):
                    self._process.terminate()
                    time.sleep(0.5)
                    if not self._process or self._process.poll() is not None:
                        break
                if self._process.poll() is None:
                    self._process.kill()
                    self._process.wait()
            else:
                if diagnostics["returncode"] not in {None, 0}:
                    logger.error("SC2 process exited unexpectedly: {}", diagnostics)
                if terminate_owned_process(self._process):
                    logger.info("Terminated owned SC2 process pid={}", self._process.pid)
            # Never kill the user's global Wine server during ordinary match
            # cleanup.  Concurrent SC2 clients share it, so doing so sends
            # SIGTERM to unrelated matches.  Retain an explicit emergency
            # escape hatch for isolated debugging only.
            if paths.PF in {"Linux", "WineLinux"} and allow_global_wineserver_kill():
                logger.warning("Opt-in global wineserver shutdown requested")
                with suppress(FileNotFoundError), subprocess.Popen(["wineserver", "-k"]) as p:
                    p.wait()

        if self._stderr_handle is not None:
            with suppress(OSError):
                self._stderr_handle.close()
            self._stderr_handle = None

        if Path(self._tmp_dir).exists():
            shutil.rmtree(self._tmp_dir)

        self._process = None
        self._ws = None
        self._controller = None
        self._protocol_request_in_flight = False
        self._protocol_request_timed_out = False
        self._protocol_request_type = None
        if self._used_portpicker and self._port is not None:
            portpicker.return_port(self._port)
            self._port = None
        if verbose:
            logger.info("Cleanup complete")
