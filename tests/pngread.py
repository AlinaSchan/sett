"""a small png reader for the tests: checks the signature and every crc, returns the chunks and the rgba."""
from __future__ import annotations

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"


def chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    assert data[:8] == SIGNATURE, "not a png signature"
    out, pos = [], 8
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        kind, body = data[pos + 4:pos + 8], data[pos + 8:pos + 8 + n]
        assert len(body) == n and pos + 12 + n <= len(data), f"{kind!r} is cut short"
        (crc,) = struct.unpack(">I", data[pos + 8 + n:pos + 12 + n])
        assert crc == zlib.crc32(kind + body), f"bad crc in {kind!r}"
        out.append((kind, body))
        pos += 12 + n
    return out


def image_data(data: bytes) -> bytes:
    """the idat stream decompressed: one filter byte and the palette indices of each row."""
    return zlib.decompress(b"".join(body for kind, body in chunks(data) if kind == b"IDAT"))


def read(data: bytes) -> tuple[int, int, bytes]:
    """width, height and rgba bytes of an 8 bit palette png whose rows all have filter 0 (what sett writes)."""
    cs = chunks(data)
    assert cs[0][0] == b"IHDR" and cs[-1] == (b"IEND", b"")
    width, height, depth, colour_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", cs[0][1])
    assert (depth, colour_type, compression, filtering, interlace) == (8, 3, 0, 0, 0)
    plte = next(body for kind, body in cs if kind == b"PLTE")
    trns = next((body for kind, body in cs if kind == b"tRNS"), b"")
    colours = [plte[3 * i:3 * i + 3] + bytes([trns[i] if i < len(trns) else 255]) for i in range(len(plte) // 3)]
    raw = image_data(data)
    assert len(raw) == height * (width + 1)
    out = bytearray()
    for y in range(height):
        line = raw[y * (width + 1):(y + 1) * (width + 1)]
        assert line[0] == 0, f"row {y} has filter {line[0]}"
        for i in line[1:]:
            out += colours[i]
    return width, height, bytes(out)
