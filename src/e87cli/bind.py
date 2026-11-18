"""Bind: the step the phone app performs right after scanning the badge's QR.

A factory-fresh (or unbound) badge sits on a QR "pair me" screen and keeps
showing it even after a successful upload. Sending the bind request makes it
leave that screen and show the uploaded content.

Wire format (the 0x9E-framed control channel on characteristic FD02), as
documented by the vasilievh/e87-badge-firmware project (MIT):

    frame   = 9E | checksum | flags | cmd | len (LE16) | payload
    checksum = sum(flags, cmd, len, payload) & 0xFF
    bind    = cmd 0x60, flags 0x02, 13 byte payload:
              header | host_id (6 bytes LE) | host_id (6 bytes LE)
              header = (hour12 << 2) | (english << 1)
    reply   = cmd 0x61: a 1 byte status frame, then a longer frame holding
              state, protocol version and firmware version
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

MAGIC = 0x9E
CMD_BIND = 0x60
CMD_BIND_REPLY = 0x61
CMD_UNBIND = 0x62


def build_frame(flags: int, cmd: int, payload: bytes) -> bytes:
    body = bytes((flags & 0xFF, cmd & 0xFF)) + len(payload).to_bytes(2, "little") + payload
    return bytes((MAGIC, sum(body) & 0xFF)) + body


def parse_frames(buffer: bytes) -> list[tuple[int, int, bytes]]:
    """Extract every valid (flags, cmd, payload) frame from a byte stream."""
    frames = []
    i = 0
    while i + 6 <= len(buffer):
        if buffer[i] != MAGIC:
            i += 1
            continue
        length = int.from_bytes(buffer[i + 4 : i + 6], "little")
        end = i + 6 + length
        if end > len(buffer) or (sum(buffer[i + 2 : end]) & 0xFF) != buffer[i + 1]:
            i += 1
            continue
        frames.append((buffer[i + 2], buffer[i + 3], bytes(buffer[i + 6 : end])))
        i = end
    return frames


def build_bind_payload(host_id: int, *, english: bool = True, hour12: bool = False) -> bytes:
    header = (int(hour12) << 2) | (int(english) << 1)
    ident = (host_id & 0xFFFFFFFFFFFF).to_bytes(6, "little")
    return bytes((header,)) + ident + ident


@dataclass(frozen=True)
class BindResult:
    state: int
    protocol: str
    firmware: str


def parse_bind_reply(payload: bytes) -> BindResult | None:
    if len(payload) < 14:
        return None

    def text(chunk: bytes) -> str:
        return chunk.split(b"\x00", 1)[0].decode("ascii", errors="ignore")

    return BindResult(payload[0], text(payload[1:4]), text(payload[4:14]))


async def bind(client, host_id: int, *, english: bool = True, hour12: bool = False,
               timeout: float = 4.0) -> BindResult | None:
    """Bind an already connected and authenticated `E87Client`.

    Returns the parsed reply, or None when the badge sent no parsable reply
    (the request is still sent, and usually still takes effect).
    """
    from e87_badge.frame import parse_fe_frame
    from e87_badge.protocol import UploadSession

    # The badge ignores control commands until the app's start-up sequence has
    # run; reuse the upload session's setup phases for that.
    session = UploadSession(client._write_ae01, client._write_fd02, client._bus)
    client._bus.clear()
    await session._phase1_reset_auth()
    await session._phase2_fd02_control()
    await session._phase3_device_info()
    await session._phase4_device_config()
    await session._phase5_fd02_bootstrap()
    client._bus.clear()

    payload = build_bind_payload(host_id, english=english, hour12=hour12)
    await client._write_fd02(build_frame(0x02, CMD_BIND, payload))

    stream = bytearray()
    result: BindResult | None = None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline and result is None:
        await asyncio.sleep(0.1)
        while (raw := client._bus.consume(lambda r: parse_fe_frame(r) is None)) is not None:
            stream += raw
        for _flags, cmd, body in parse_frames(bytes(stream)):
            if cmd == CMD_BIND_REPLY:
                result = parse_bind_reply(body) or result
    return result


async def unbind(client) -> None:
    """Return the badge to its QR pairing screen."""
    await client._write_fd02(build_frame(0x00, CMD_UNBIND, b"\x01"))
    await asyncio.sleep(0.5)
