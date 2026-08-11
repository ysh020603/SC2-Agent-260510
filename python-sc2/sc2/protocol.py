from __future__ import annotations

import asyncio
import inspect
import os
from contextlib import suppress

from aiohttp.client_ws import ClientWebSocketResponse
from loguru import logger

# pyre-fixme[21]
from s2clientprotocol import sc2api_pb2 as sc_pb

from sc2.data import Status


class ProtocolError(Exception):
    @property
    def is_game_over_error(self) -> bool:
        return self.args[0] in ["['Game has already ended']", "['Not supported if game has already ended']"]


class ConnectionAlreadyClosedError(ProtocolError):
    pass


class SC2MatchFatalError(BaseException):
    """An unrecoverable transport failure for the current SC2 match.

    This intentionally does not inherit from ``Exception``. Bot and manager
    code contains broad recovery handlers for ordinary gameplay failures and
    ``ProtocolError`` responses. A dead native client cannot be recovered by
    that code: swallowing the failure makes the Python match loop issue more
    requests against a killed client forever.

    Match boundaries must catch this type explicitly after their scoped SC2
    cleanup has run and terminate the single-match process with a non-zero
    status.
    """

    pass


class ProtocolResponseTimeoutError(SC2MatchFatalError):
    """The SC2 websocket accepted a request but never returned a response."""

    pass


class ProtocolResponsePendingError(ConnectionAlreadyClosedError):
    """A previous SC2 request is still awaiting its one permitted response."""

    pass


class SC2ProcessExitedError(SC2MatchFatalError):
    """The websocket failed because the owned SC2 client process exited."""

    pass


class Protocol:
    def __init__(self, ws: ClientWebSocketResponse, process=None) -> None:
        """
        A class for communicating with an SCII application.
        :param ws: the websocket (type: aiohttp.ClientWebSocketResponse) used to communicate with a specific SCII app
        """
        assert ws
        self._ws: ClientWebSocketResponse = ws
        self._sc2_process = process
        # SC2 accepts exactly one request at a time on a protocol connection.
        # Most callers are sequential, but managers and timeout cancellation can
        # otherwise overlap a follow-up query with a response still in flight.
        # Create the lock lazily inside the active loop.  Protocol objects are
        # also constructed by compatibility callers before asyncio.run(); on
        # Python 3.9 an eagerly-created Lock can bind to the wrong loop.
        self._request_lock: asyncio.Lock | None = None
        self._process_exit_logged = False
        self._pending_response_task: asyncio.Task | None = None
        self._pending_request_type: str | None = None
        register_protocol = getattr(process, "register_protocol", None)
        if register_protocol is not None:
            register_protocol(self)
        # pyre-fixme[11]
        self._status: Status | None = None

    @property
    def has_pending_response(self) -> bool:
        task = self._pending_response_task
        return task is not None and not task.done()

    @property
    def pending_request_type(self) -> str | None:
        return self._pending_request_type if self.has_pending_response else None

    def _notify_process(self, method: str, *args) -> None:
        process = self._sc2_process
        callback = getattr(process, method, None) if process is not None else None
        if callback is not None:
            callback(*args)

    def _response_task_done(self, task: asyncio.Task) -> None:
        request_type = self._pending_request_type
        with suppress(asyncio.CancelledError, Exception):
            task.exception()
        if self._pending_response_task is task:
            self._pending_response_task = None
            self._pending_request_type = None
            self._notify_process("protocol_request_finished", request_type)

    @staticmethod
    def _timeout_seconds(request_type: str) -> float:
        try:
            generic = float(
                os.environ.get("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "90")
            )
        except (TypeError, ValueError):
            generic = 90.0
        specific_name = f"SC2_PROTOCOL_{request_type.upper()}_TIMEOUT_SECONDS"
        specific = os.environ.get(specific_name)
        if specific is not None:
            try:
                return float(specific)
            except (TypeError, ValueError):
                logger.warning("Ignoring invalid {}={!r}", specific_name, specific)
        # Give loaded clients more room for an observation, but keep the bound
        # short enough that a terminal SC2 4.10 response stall can be killed
        # and retried instead of holding a batch worker indefinitely.
        if request_type == "observation" and generic > 0:
            return max(generic, 120.0)
        return generic

    async def drain_pending_response(self, timeout_seconds: float) -> bool:
        """Wait without cancelling the sole SC2 response receiver."""

        task = self._pending_response_task
        if task is None or task.done():
            return True
        done, _ = await asyncio.wait(
            {task}, timeout=max(0.0, float(timeout_seconds))
        )
        return bool(done)

    async def cancel_pending_response(self) -> bool:
        """Cancel this protocol's receiver after its owned SC2 is gone.

        Cancelling a live receive can trigger the legacy Linux client's broken
        pending-response shutdown path.  Callers must therefore kill or
        observe termination of the exact owned client first.
        """

        task = self._pending_response_task
        if task is None:
            return False
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
        if self._pending_response_task is task:
            self._pending_response_task = None
            self._pending_request_type = None
        return True

    async def _abort_timed_out_request(self, request_type: str) -> None:
        """Abort at the failure site instead of relying on later context exit."""

        process = self._sc2_process
        callback = getattr(process, "abort_protocol_request", None) if process is not None else None
        if callback is not None:
            result = callback(request_type)
            if inspect.isawaitable(result):
                await result
        await self.cancel_pending_response()

    def _process_diagnostics(self):
        process = self._sc2_process
        if process is None or not hasattr(process, "diagnostic_snapshot"):
            return None
        try:
            return process.diagnostic_snapshot()
        except Exception as exc:  # Diagnostics must never mask the protocol error.
            return {"diagnostic_error": repr(exc)}

    def _raise_if_process_exited(self) -> None:
        diagnostics = self._process_diagnostics()
        if diagnostics is not None and diagnostics.get("returncode") is not None:
            if not self._process_exit_logged:
                logger.error("SC2 client process exited: {}", diagnostics)
                self._process_exit_logged = True
            raise SC2ProcessExitedError(
                f"SC2 client process exited: {diagnostics}"
            )

    async def __request(self, request):
        request_type = request.WhichOneof("request") or "unknown"
        if self.has_pending_response:
            raise ProtocolResponsePendingError(
                "Cannot send a new SC2 request while response is pending for "
                f"request_type={self.pending_request_type}"
            )
        logger.debug(f"Sending request: {request!r}")
        self._raise_if_process_exited()
        try:
            await self._ws.send_bytes(request.SerializeToString())
        except TypeError as exc:
            logger.exception("Cannot send: Connection already closed.")
            raise ConnectionAlreadyClosedError("Connection already closed.") from exc
        logger.debug("Request sent")

        response = sc_pb.Response()
        receive_task = asyncio.create_task(self._ws.receive_bytes())
        self._pending_response_task = receive_task
        self._pending_request_type = request_type
        self._notify_process("protocol_request_started", request_type)
        receive_task.add_done_callback(self._response_task_done)
        try:
            timeout_seconds = self._timeout_seconds(request_type)
            if timeout_seconds <= 0:
                response_bytes = await asyncio.shield(receive_task)
            else:
                done, _ = await asyncio.wait({receive_task}, timeout=timeout_seconds)
                if not done:
                    raise asyncio.TimeoutError
                response_bytes = receive_task.result()
        except asyncio.TimeoutError as exc:
            self._notify_process("protocol_request_timed_out", request_type)
            diagnostics = self._process_diagnostics()
            if diagnostics is not None and diagnostics.get("returncode") is not None:
                logger.error("SC2 client exited while awaiting response: {}", diagnostics)
                raise SC2ProcessExitedError(
                    f"SC2 client exited while awaiting response: {diagnostics}"
                ) from exc
            logger.error(
                "SC2 protocol response timed out after {:.1f} seconds; "
                "request_type={}; process={}",
                timeout_seconds,
                request_type,
                diagnostics,
            )
            # Do not leave the websocket receiver and native client spinning
            # until outer context cleanup.  This Protocol may be the match
            # Client rather than SC2Process._controller, so cleanup cannot
            # otherwise see its pending task.  Kill only this match's native
            # client, then cancel and await its sole receiver.
            await self._abort_timed_out_request(request_type)
            raise ProtocolResponseTimeoutError(
                f"SC2 protocol response timed out after {timeout_seconds:.1f} seconds; "
                f"request_type={request_type}; process={diagnostics}"
            ) from exc
        except TypeError as exc:
            if self._status == Status.ended:
                logger.info("Cannot receive: Game has already ended.")
                raise ConnectionAlreadyClosedError("Game has already ended") from exc
            diagnostics = self._process_diagnostics()
            if diagnostics is not None and diagnostics.get("returncode") is not None:
                logger.error("SC2 client connection closed after process exit: {}", diagnostics)
                raise SC2ProcessExitedError(
                    f"SC2 client connection closed after process exit: {diagnostics}"
                ) from exc
            logger.error("Cannot receive: Connection already closed.")
            raise ConnectionAlreadyClosedError("Connection already closed.") from exc
        except asyncio.CancelledError:
            # asyncio.wait/shield leaves the receiver alive. Never start a
            # second receive for the same websocket response.
            self._notify_process("protocol_request_timed_out", request_type)
            raise

        response.ParseFromString(response_bytes)
        logger.debug("Response received")
        return response

    async def _execute(self, **kwargs):
        assert len(kwargs) == 1, "Only one request allowed by the API"
        if self._request_lock is None:
            self._request_lock = asyncio.Lock()
        async with self._request_lock:
            response = await self.__request(sc_pb.Request(**kwargs))

            new_status = Status(response.status)
            if new_status != self._status:
                logger.info(f"Client status changed to {new_status} (was {self._status})")
            self._status = new_status

            if response.error:
                logger.debug(f"Response contained an error: {response.error}")
                raise ProtocolError(f"{response.error}")

            return response

    async def ping(self):
        result = await self._execute(ping=sc_pb.RequestPing())
        return result

    async def quit(self) -> None:
        with suppress(ConnectionAlreadyClosedError, ConnectionResetError):
            await self._execute(quit=sc_pb.RequestQuit())
