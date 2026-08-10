from __future__ import annotations

import asyncio
import os
import sys
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


class ProtocolResponseTimeoutError(ProtocolError):
    """The SC2 websocket accepted a request but never returned a response."""

    pass


class SC2ProcessExitedError(ConnectionAlreadyClosedError):
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
        self._request_lock = asyncio.Lock()
        self._process_exit_logged = False
        # pyre-fixme[11]
        self._status: Status | None = None

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
        logger.debug(f"Sending request: {request!r}")
        self._raise_if_process_exited()
        try:
            await self._ws.send_bytes(request.SerializeToString())
        except TypeError as exc:
            logger.exception("Cannot send: Connection already closed.")
            raise ConnectionAlreadyClosedError("Connection already closed.") from exc
        logger.debug("Request sent")

        response = sc_pb.Response()
        try:
            try:
                timeout_seconds = float(
                    os.environ.get("SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS", "90")
                )
            except (TypeError, ValueError):
                timeout_seconds = 90.0
            if timeout_seconds <= 0:
                response_bytes = await self._ws.receive_bytes()
            else:
                response_bytes = await asyncio.wait_for(
                    self._ws.receive_bytes(), timeout=timeout_seconds
                )
        except asyncio.TimeoutError as exc:
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
            # If request is sent, the response must be received before reraising cancel
            try:
                await self._ws.receive_bytes()
            except asyncio.CancelledError:
                logger.critical("Requests must not be cancelled multiple times")
                sys.exit(2)
            raise

        response.ParseFromString(response_bytes)
        logger.debug("Response received")
        return response

    async def _execute(self, **kwargs):
        assert len(kwargs) == 1, "Only one request allowed by the API"
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
