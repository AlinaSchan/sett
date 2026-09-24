"""a small png writer: rgba rows in, a palette png out. zlib and struct only."""
from __future__ import annotations

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))


def encode(width: int, height: int, rows: list[bytes]) -> bytes:
    """a png with an 8 bit palette of at most 256 colours. the palette is sorted by rgba, alpha goes into a trns
    chunk only when a colour is not opaque, every row has filter 0, and nothing else is written (no time, no text,
    no gamma), so the same pixels always give the same bytes with the same zlib."""
    if width < 1 or height < 1 or len(rows) != height or any(len(r) != 4 * width for r in rows):
        raise ValueError("the rows do not match the width and height")
    as_ints = struct.Struct(f">{width}I")             # a pixel as one number: r << 24 | g << 16 | b << 8 | a
    distinct = list(dict.fromkeys(rows))
    colours: set[int] = set()
    for r in distinct:
        colours.update(as_ints.unpack(r))
    if len(colours) > 256:
        raise ValueError(f"{len(colours)} colours, a palette holds 256")
    palette = sorted(colours)
    index = {c: i for i, c in enumerate(palette)}
    lines = {r: b"\x00" + bytes(map(index.__getitem__, as_ints.unpack(r))) for r in distinct}
    parts = [
        SIGNATURE,
        _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)),
        _chunk(b"PLTE", b"".join(c.to_bytes(4, "big")[:3] for c in palette)),
    ]
    alpha = bytes(c & 255 for c in palette).rstrip(b"\xff")
    if alpha:
        parts.append(_chunk(b"tRNS", alpha))
    parts.append(_chunk(b"IDAT", zlib.compress(b"".join(lines[r] for r in rows), 9)))
    parts.append(_chunk(b"IEND", b""))
    return b"".join(parts)
