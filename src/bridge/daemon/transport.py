"""Asynchronous NDJSON transport for reading from stdin and writing to stdout."""

import asyncio
import os
import sys
from typing import AsyncIterator, Optional, TextIO

from src.bridge.protocol.frames import MasterFrame, decode_master_frame, encode_master_frame


class AsyncNDJSONTransport:
    """Manages asynchronous NDJSON frame reading and writing over standard I/O pipes."""

    def __init__(
        self,
        stdin_stream: Optional[asyncio.StreamReader] = None,
        stdout_stream: Optional[asyncio.StreamWriter] = None,
        stderr_file: Optional[TextIO] = None,
    ) -> None:
        self._reader = stdin_stream
        self._writer = stdout_stream
        self._stderr = stderr_file or sys.stderr
        self._write_lock = asyncio.Lock()
        self._closed = False

    async def initialize(self) -> None:
        """Sets up asynchronous streams for standard input and output if not provided."""
        if self._reader is not None and self._writer is not None:
            return

        loop = asyncio.get_running_loop()

        if self._reader is None:
            reader = asyncio.StreamReader()
            protocol = asyncio.StreamReaderProtocol(reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)
            self._reader = reader

        if self._writer is None:
            w_transport, w_protocol = await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, sys.stdout
            )
            self._writer = asyncio.StreamWriter(w_transport, w_protocol, self._reader, loop)

    async def read_frames(self) -> AsyncIterator[MasterFrame]:
        """Reads and yields validated MasterFrames from the input pipe until EOF."""
        if self._reader is None:
            await self.initialize()

        assert self._reader is not None

        while not self._closed:
            try:
                line_bytes = await self._reader.readline()
                if not line_bytes:
                    # Clean EOF on stdin - Kernel closed pipe
                    self.log_diagnostic("Received EOF on stdin pipe; closing transport.")
                    break

                line_str = line_bytes.decode("utf-8")
                stripped = line_str.strip()
                if not stripped:
                    continue

                frame = decode_master_frame(stripped)
                yield frame

            except asyncio.CancelledError:
                self.log_diagnostic("Transport read loop cancelled.")
                break
            except Exception as exc:
                self.log_diagnostic(f"Failed to decode frame from input pipe: {exc}")

    async def write_frame(self, frame: MasterFrame) -> None:
        """Serializes and writes a MasterFrame to stdout followed by an immediate flush."""
        if self._closed:
            return

        encoded_line = encode_master_frame(frame)
        payload_bytes = encoded_line.encode("utf-8")

        async with self._write_lock:
            if self._writer is not None:
                self._writer.write(payload_bytes)
                await self._writer.drain()
            else:
                # Direct fallback when standard async pipes are not attached
                sys.stdout.write(encoded_line)
                sys.stdout.flush()

    def log_diagnostic(self, message: str) -> None:
        """Logs diagnostic or debug messages strictly to stderr to prevent stdout contamination."""
        try:
            self._stderr.write(f"[Layer4-Daemon] {message}\n")
            self._stderr.flush()
        except Exception:
            pass

    async def close(self) -> None:
        """Closes the transport gracefully."""
        self._closed = True
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
