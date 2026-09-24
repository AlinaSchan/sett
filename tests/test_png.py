"""the png writer: a valid file, the pixels it was given, and the same bytes for the same pixels."""
import hashlib
import struct

import pngread
import pytest

from sett import png
from sett.weave import picture, weave

EMPTY = hashlib.sha256(b"").digest()
# sha256 of the decompressed image data (filter bytes and palette indices). it pins the palette order and the rows
# without pinning zlib's compressed bytes, which may differ between zlib builds.
EMPTY_IMAGE_DATA = "e03cefdce06e7c72eda5c98cad8ab67ea0fa202b7b0b4c4315fa242e74167f9b"
PAIR_IMAGE_DATA = "a5d74c3f8e819660c85b2a1858dfd42964d2ef42cd811f557b3e4086f36cd16f"


def test_a_valid_png_of_the_same_pixels():
    width, height, rows = picture([weave(EMPTY)])
    data = png.encode(width, height, rows)
    kinds = [kind for kind, _ in pngread.chunks(data)]      # signature and every crc are checked here
    assert kinds == [b"IHDR", b"PLTE", b"IDAT", b"IEND"]     # opaque: no trns, and nothing else
    assert struct.unpack(">IIBBBBB", pngread.chunks(data)[0][1]) == (160, 160, 8, 3, 0, 0, 0)
    assert pngread.read(data) == (160, 160, b"".join(rows))
    assert hashlib.sha256(pngread.image_data(data)).hexdigest() == EMPTY_IMAGE_DATA


def test_palette_is_sorted_and_alpha_only_when_needed():
    a, b = weave(EMPTY), weave(hashlib.sha256(b"x").digest())
    data = png.encode(*picture([a, b]))
    cs = dict(pngread.chunks(data))
    plte = cs[b"PLTE"]
    entries = [plte[i:i + 3] for i in range(0, len(plte), 3)]
    assert entries[0] == bytes(3) and entries[1:] == sorted(entries[1:])
    assert cs[b"tRNS"] == b"\x00"                            # only the gap is transparent, and it sorts first
    width, height, rgba = pngread.read(data)
    assert (width, height) == (2 * 160 + 8, 160)
    assert rgba[4 * 160:4 * 168] == bytes(32)                # the gap is (0, 0, 0, 0)
    assert hashlib.sha256(pngread.image_data(data)).hexdigest() == PAIR_IMAGE_DATA


def test_same_pixels_same_bytes():
    one = png.encode(*picture([weave(EMPTY)], 8))
    two = png.encode(*picture([weave(EMPTY)], 8))
    assert one == two
    assert pngread.read(one)[:2] == (320, 320)


def test_small_images_and_odd_colours():
    rows = [bytes([1, 2, 3, 255, 1, 2, 3, 128]), bytes([0, 0, 0, 0, 9, 9, 9, 255])]
    data = png.encode(2, 2, rows)
    assert pngread.read(data) == (2, 2, b"".join(rows))
    # palette by rgba: (0,0,0,0), (1,2,3,128), (1,2,3,255), (9,9,9,255); trns stops after the last alpha below 255
    assert dict(pngread.chunks(data))[b"tRNS"] == b"\x00\x80"


def test_refuses():
    with pytest.raises(ValueError):
        png.encode(2, 1, [bytes(4)])
    with pytest.raises(ValueError):
        png.encode(1, 2, [bytes(4)])
    with pytest.raises(ValueError):
        png.encode(0, 0, [])
    many = b"".join(bytes([i % 256, i // 256, 0, 255]) for i in range(257))
    with pytest.raises(ValueError, match="257 colours"):
        png.encode(257, 1, [many])
