"""the weave: known answers taken from the implementation this was extracted from, and the rules of SPEC.md."""
import hashlib
import math
import random

import pytest

from sett.weave import DYES, GAP, MH, MV, T, fields, picture, pixels, shade, weave

# sha256 of the raw rgba bytes, row by row, of the cloth the original numpy implementation wove for sha256(text)
GOLDEN = [
    (b"", 40, 40, "3aec9e891860a3695d77ac68a149f7c571c323ba2689995adad2a1942ec0eca6"),
    (b"", 36, 38, "b8b1ad82bbc47e722dcf83de58b855068402e5041357ac4f54f9e07f6280e511"),
    (b"", 8, 8, "b530a8477d5c234ca28d2670b4d34b83858bb277eeb29c455f8746d3a2818100"),
    (b"", 1, 1, "54063bdf74739ca6b5d26c08356f5e1b3e8b6c1f8a71fc86c615ea79946b06be"),
    (b"weave parity 1", 40, 40, "7dfa7648f737602cc113864eb740deec0ac5113e211c5120c2ae9086027eb022"),
    (b"weave parity 1", 36, 38, "515cf6630aa41feb4a18cac3bffb0046f91b51fb9dabc4533e74277b14b10b15"),
    (b"weave parity 2", 40, 40, "69e54f6284a3901403dc6efa93fc1acf0cdc135d659d1de9a03e4682f23fc756"),
    (b"weave parity 2", 8, 8, "3c5a45e7162772b146bcdd4f119c45baae04f3dd2f7f3bd4672790c2853142eb"),
    (b"weave parity 3", 40, 40, "0127f6a0e5c196fd240d7188dca424635003956ec07fb80449f82f13d70c595c"),
    (b"weave parity 3", 1, 1, "e9250e3de8a6a61a7fd361fe3ff4dab067d68915a7d0adcf7db0b98409ec3fd6"),
    (b"hello\n", 40, 40, "8c8024fa7f1ea245781d896cf5dccb34e0f6fb14ee35df8aafb36c07799f1508"),
    (b"hello\n", 1, 1, "e9250e3de8a6a61a7fd361fe3ff4dab067d68915a7d0adcf7db0b98409ec3fd6"),
    (b"hullo\n", 40, 40, "f4576bc901e034ea5752a17342a60d494f449f6bc7e7985518f8fa5da32d266b"),
    (b"hullo\n", 36, 38, "249c374aba55f23c957285cb4328d53b89a0ba84aa50be5ceb7a439e1038b4fb"),
]

# pixels (x, y) -> rgba of the empty string's cloth, 40 x 40, as the original wove them
EMPTY_PIXELS = {
    (0, 0): (98, 68, 44, 255), (1, 0): (98, 68, 44, 255), (3, 0): (98, 68, 44, 255), (0, 3): (72, 50, 32, 255),
    (5, 6): (115, 80, 52, 255), (80, 80): (38, 32, 27, 255), (100, 37): (115, 80, 52, 255),
    (159, 159): (109, 38, 21, 255), (158, 157): (175, 60, 33, 255), (42, 121): (45, 38, 32, 255),
}


def sha(text: bytes) -> bytes:
    return hashlib.sha256(text).digest()


def rgba(d: bytes, ends: int = 40, picks: int = 40, size: int = T) -> bytes:
    return b"".join(pixels(weave(d, ends, picks), size))


@pytest.mark.parametrize(("text", "ends", "picks", "want"), GOLDEN)
def test_known_answers(text, ends, picks, want):
    assert hashlib.sha256(rgba(sha(text), ends, picks)).hexdigest() == want


def test_known_pixels():
    a = rgba(sha(b""))
    for (x, y), want in EMPTY_PIXELS.items():
        i = 4 * (160 * y + x)
        assert tuple(a[i:i + 4]) == want, (x, y)


def test_fields():
    assert fields([1, 1, 1, 1], 8) == [0, 0, 1, 1, 2, 2, 3, 3]
    assert fields([1, 2, 3, 4], 10) == [0, 1, 1, 2, 2, 2, 3, 3, 3, 3]
    assert fields([5, 1, 1, 1], 3) == [0, 0, 2]
    rng = random.Random(7)
    for _ in range(500):
        widths, n = [rng.randint(1, 5) for _ in range(4)], rng.randint(1, 60)
        f = fields(widths, n)
        assert len(f) == n and f == sorted(f)
        for i, w in enumerate(widths):          # each field gets its share, rounded to a whole thread
            assert abs(f.count(i) - n * w / sum(widths)) <= 1


def test_tables_follow_the_formula():
    base = [round(256 * (0.8 + 0.3 * math.sin(math.pi * (k + 0.5) / 4))) for k in range(4)]
    assert base == [234, 276, 276, 234]
    assert list(MV) == [*base[:3], (base[3] * 74 + 50) // 100]
    assert list(MH) == [*base[:3], (base[3] * 78 + 50) // 100]


def test_dyes():
    assert ["#{:02x}{:02x}{:02x}".format(*c) for c in DYES] == [
        "#a2381f", "#d9ac3f", "#26345c", "#6b4a30", "#e6dcc6", "#2a231e"]
    assert shade((230, 220, 198), 276) == (248, 237, 213)
    assert shade((255, 255, 255), 276) == (255, 255, 255)


def test_every_pixel_is_a_shaded_dye():
    allowed = {bytes((*shade(c, m), 255)) for c in DYES for m in (*MV, *MH)}
    rng = random.Random(11)
    for _ in range(20):
        a = rgba(bytes(rng.randrange(256) for _ in range(32)))
        assert {a[i:i + 4] for i in range(0, len(a), 4)} <= allowed


def test_the_three_weaves():
    # equal fields, and every block byte the same: the byte alone decides the weave of the whole cloth
    def share_of_weft(b: int) -> float:
        c = weave(bytes(16) + bytes([b]) * 16)
        return sum(map(sum, c.up)) / (40 * 40)

    assert share_of_weft(0) == share_of_weft(1) == share_of_weft(130) == 0.8       # weft-faced satin
    assert share_of_weft(2) == share_of_weft(3) == share_of_weft(128) == 0.2       # warp-faced satin
    assert share_of_weft(4) == share_of_weft(129) == 0.5                           # 2/2 twill
    # the top bit turns the diagonal: z = -1 below 128, +1 from 128 (4 and 129 are both twill)
    c, d = weave(bytes(16) + bytes([4]) * 16), weave(bytes(16) + bytes([129]) * 16)
    assert c.up[1][:4] == [False, True, True, False] and d.up[1][:4] == [True, False, False, True]


def test_bigger_size_is_the_same_cloth():
    d = sha(b"weave parity 2")
    small = pixels(weave(d, 9, 7))
    for size in (8, 12):
        k = size // T
        big = pixels(weave(d, 9, 7), size)
        assert len(big) == 7 * size and len(big[0]) == 4 * 9 * size
        for y, row in enumerate(big):
            want = b"".join(small[y // k][4 * x:4 * x + 4] * k for x in range(9 * T))
            assert row == want


def test_picture_side_by_side():
    a, b = weave(sha(b"a")), weave(sha(b"b"))
    width, height, rows = picture([a, b], 8)
    assert (width, height) == (2 * 40 * 8 + GAP * 8, 40 * 8)
    left, right = pixels(a, 8), pixels(b, 8)
    for y, row in enumerate(rows):
        assert row == left[y] + bytes(4 * GAP * 8) + right[y]


def test_what_does_not_change_a_sett():
    # the cloth reads its bytes modulo 5 or 6 (and the top bit of a block byte), so some changes weave the same cloth
    d = sha(b"hello\n")
    same = bytes([d[0] + 5]) + d[1:]                   # the first warp field is 1 + d[0] mod 5 wide
    assert same != d and weave(same) == weave(d)
    other = d[:8] + bytes([d[8] ^ 1]) + d[9:]          # its dye is d[8] mod 6
    assert weave(other) != weave(d)


def test_refuses():
    with pytest.raises(ValueError):
        weave(bytes(20))
    with pytest.raises(ValueError):
        weave(bytes(32), 0, 40)
    with pytest.raises(ValueError):
        pixels(weave(bytes(32)), 6)
