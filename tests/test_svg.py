"""the svg: well formed, and its patterns and paths, painted, give exactly the pixels of the png."""
import hashlib
import random
import re
import xml.etree.ElementTree as ET

import pytest

from sett import svg
from sett.weave import picture, weave

NS = "{http://www.w3.org/2000/svg}"
RUN = re.compile(r"M(\d+) (\d+)h(\d+)v(\d+)h-(\d+)z")


def paint(text: str) -> tuple[int, int, bytes]:
    """paint the svg the way a renderer does, one viewBox unit a pixel: width, height and rgba."""
    root = ET.fromstring(text)
    _, _, width, height = map(int, root.get("viewBox").split())
    tiles = {}
    for pattern in root.iter(f"{NS}pattern"):
        assert (pattern.get("width"), pattern.get("height")) == ("4", "4")
        assert pattern.get("patternUnits") == "userSpaceOnUse"
        tile = [[b""] * 4 for _ in range(4)]
        for rect in pattern.iter(f"{NS}rect"):
            x, y = int(rect.get("x", 0)), int(rect.get("y", 0))
            for j in range(y, y + int(rect.get("height"))):
                for i in range(x, x + int(rect.get("width"))):
                    tile[j][i] = bytes.fromhex(rect.get("fill")[1:]) + b"\xff"
        assert all(all(row) for row in tile)
        tiles[pattern.get("id")] = tile
    px = [[bytes(4)] * width for _ in range(height)]
    for path in root.iter(f"{NS}path"):
        tile = tiles[re.fullmatch(r"url\(#(\w+)\)", path.get("fill"))[1]]
        runs = RUN.findall(path.get("d"))
        assert "".join(f"M{x} {y}h{w}v{h}h-{b}z" for x, y, w, h, b in runs) == path.get("d")
        for x, y, w, h, back in runs:
            assert w == back
            for j in range(int(y), int(y) + int(h)):
                for i in range(int(x), int(x) + int(w)):
                    px[j][i] = tile[j % 4][i % 4]
    return width, height, b"".join(b"".join(row) for row in px)


def sha(text: bytes) -> bytes:
    return hashlib.sha256(text).digest()


def png_pixels(cloths) -> tuple[int, int, bytes]:
    width, height, rows = picture(cloths)
    return width, height, b"".join(rows)


def test_well_formed():
    text = svg.render([weave(sha(b""))], 4, "sha256 <e3b0> & more")
    root = ET.fromstring(text)
    assert root.tag == f"{NS}svg"
    assert (root.get("width"), root.get("height"), root.get("viewBox")) == ("160", "160", "0 0 160 160")
    assert root.find(f"{NS}title").text == "sha256 <e3b0> & more"
    assert text.endswith("</svg>\n") and text.isascii()


@pytest.mark.parametrize(("ends", "picks"), [(40, 40), (36, 38), (8, 8), (1, 1), (5, 2)])
def test_paints_the_png_pixels(ends, picks):
    rng = random.Random(ends * 100 + picks)
    for _ in range(4):
        cloth = weave(bytes(rng.randrange(256) for _ in range(32)), ends, picks)
        assert paint(svg.render([cloth])) == png_pixels([cloth])


def test_two_side_by_side():
    cloths = [weave(sha(b"hello\n")), weave(sha(b"hullo\n"))]
    text = svg.render(cloths, 8)
    root = ET.fromstring(text)
    assert (root.get("width"), root.get("height"), root.get("viewBox")) == ("656", "320", "0 0 328 160")
    assert paint(text) == png_pixels(cloths)       # the gap stays empty, like the transparent gap of the png


def test_same_input_same_text():
    cloth = weave(sha(b"weave parity 1"))
    assert svg.render([cloth], 12) == svg.render([cloth], 12)


def test_refuses_a_size_that_is_not_whole_pixels():
    with pytest.raises(ValueError):
        svg.render([weave(sha(b""))], 6)
