"""the block weave of a sha256 digest: which thread is on top at every crossing, and its pixels (SPEC.md)."""
from __future__ import annotations

from typing import NamedTuple

T = 4                           # pixels a thread: the two tables below have one entry per pixel
MV = (234, 276, 276, 173)       # weft on top: brightness of each pixel row of a pick, in 1/256
MH = (234, 276, 276, 183)       # warp on top: brightness of each pixel column of an end
ENDS = 40                       # warp ends, left to right
PICKS = 40                      # picks, top to bottom
GAP = 2                         # empty threads between two swatches side by side

# the six dyes, in the order the digest indexes them
DYES = (
    (162, 56, 31),              # madder    #a2381f
    (217, 172, 63),             # weld      #d9ac3f
    (38, 52, 92),               # indigo    #26345c
    (107, 74, 48),              # walnut    #6b4a30
    (230, 220, 198),            # undyed    #e6dcc6
    (42, 35, 30),               # oak gall  #2a231e
)


class Cloth(NamedTuple):
    warp: list[int]             # dye of each end, left to right
    weft: list[int]             # dye of each pick, top to bottom
    up: list[list[bool]]        # up[y][x]: the weft is on top where pick y crosses end x


def fields(widths: list[int], n: int) -> list[int]:
    """spread n threads over the fields in proportion to their widths; returns the field of each thread."""
    total = sum(widths)
    out = []
    for t in range(n):
        acc = 0
        for i, w in enumerate(widths):
            acc += w
            if 2 * n * acc > (2 * t + 1) * total:      # the centre of thread t lies before the end of field i
                out.append(i)
                break
    return out


def weave(digest: bytes, ends: int = ENDS, picks: int = PICKS) -> Cloth:
    """the cloth of a 32 byte digest. bytes 0-3 give the warp fields, 4-7 the weft fields, 8-15 their dyes,
    16-31 the weave of each of the 4 x 4 blocks."""
    d = digest
    if len(d) != 32:
        raise ValueError(f"a sett needs the 32 bytes of a sha256 digest, not {len(d)}")
    if ends < 1 or picks < 1:
        raise ValueError("a cloth needs at least one end and one pick")
    wf = fields([1 + d[i] % 5 for i in range(4)], ends)
    sf = fields([1 + d[4 + i] % 5 for i in range(4)], picks)
    up = []
    for y in range(picks):
        row = []
        for x in range(ends):
            b = d[16 + 4 * sf[y] + wf[x]]
            z = 1 if b >= 128 else -1                  # the direction of the diagonal
            k4, k5 = (x + z * y) % 4, (2 * x + z * y) % 5
            face = b % 5
            if face < 2:
                row.append(k5 != 0)                    # weft-faced five-end satin
            elif face < 4:
                row.append(k5 == 0)                    # warp-faced five-end satin
            else:
                row.append(k4 < 2)                     # 2/2 twill
        up.append(row)
    return Cloth([d[8 + f] % 6 for f in wf], [d[12 + f] % 6 for f in sf], up)


def shade(rgb: tuple[int, int, int], m: int) -> tuple[int, ...]:
    """a dye at brightness m / 256, rounded, at most 255."""
    return tuple(min(255, (c * m + 128) >> 8) for c in rgb)


def _px(dye: int, m: int) -> bytes:
    return bytes((*shade(DYES[dye], m), 255))


def pixels(cloth: Cloth, size: int = T) -> list[bytes]:
    """the cloth as rows of rgba bytes, `size` pixels a thread. size is a multiple of 4: each pixel of the tables
    becomes a square of (size / 4) x (size / 4), so a bigger picture is the same cloth."""
    if size < T or size % T:
        raise ValueError(f"size must be a multiple of {T}, not {size}")
    k = size // T
    warp_cells = [b"".join(_px(d, m) * k for m in MH) for d in cloth.warp]
    rows = []
    for y, dye in enumerate(cloth.weft):
        weft_cells = [_px(dye, m) * size for m in MV]
        for j in range(T):
            row = b"".join(weft_cells[j] if on else warp_cells[x] for x, on in enumerate(cloth.up[y]))
            rows += [row] * k
    return rows


def picture(cloths: list[Cloth], size: int = T) -> tuple[int, int, list[bytes]]:
    """one cloth, or several of the same height side by side with GAP transparent threads between them.
    returns width, height and the rgba rows."""
    gap = bytes(4 * GAP * size)                        # transparent pixels are (0, 0, 0, 0)
    rows = [gap.join(parts) for parts in zip(*(pixels(c, size) for c in cloths), strict=True)]
    return len(rows[0]) // 4, len(rows), rows
