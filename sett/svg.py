"""the cloth as svg: the warp laid down in stripes, the weft drawn over it wherever it is on top (SPEC.md)."""
from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import groupby
from typing import TypeVar
from xml.sax.saxutils import escape

from .weave import DYES, GAP, MH, MV, Cloth, T, shade

V = TypeVar("V")


def _runs(values: Sequence[V]) -> Iterator[tuple[V, int, int]]:
    """(value, start, length) of every run of equal neighbours."""
    x = 0
    for v, group in groupby(values):
        n = sum(1 for _ in group)
        yield v, x, n
        x += n


def _colour(dye: int, m: int) -> str:
    return "#{:02x}{:02x}{:02x}".format(*shade(DYES[dye], m))


def _pattern(name: str, dye: int, table: tuple[int, ...], across: bool) -> str:
    """one thread's shading as a 4 x 4 tile: columns for an end (across), rows for a pick."""
    band = 'x="{}" width="1" height="4"' if across else 'y="{}" width="4" height="1"'
    rects = "".join(f'<rect {band.format(k)} fill="{_colour(dye, m)}"/>' for k, m in enumerate(table))
    return f'<pattern id="{name}{dye}" width="{T}" height="{T}" patternUnits="userSpaceOnUse">{rects}</pattern>'


def render(cloths: list[Cloth], size: int = T, title: str = "") -> str:
    """one cloth, or several of the same size side by side with GAP empty threads between them. the viewBox counts
    4 units a thread; `size` sets how many pixels a thread is drawn with."""
    if size < T or size % T:
        raise ValueError(f"size must be a multiple of {T}, not {size}")
    ends, picks = len(cloths[0].warp), len(cloths[0].weft)
    step = (ends + GAP) * T
    width, height = len(cloths) * step - GAP * T, picks * T
    warp: dict[int, list[str]] = {d: [] for d in sorted({d for c in cloths for d in c.warp})}
    weft: dict[int, list[str]] = {d: [] for d in sorted({d for c in cloths for d in c.weft})}
    for n, c in enumerate(cloths):
        x0 = n * step
        for dye, x, k in _runs(c.warp):
            warp[dye].append(f"M{x0 + x * T} 0h{k * T}v{height}h-{k * T}z")
        for y, row in enumerate(c.up):
            for on, x, k in _runs(row):
                if on:
                    weft[c.weft[y]].append(f"M{x0 + x * T} {y * T}h{k * T}v{T}h-{k * T}z")
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * size // T}" height="{height * size // T}" '
        f'viewBox="0 0 {width} {height}" shape-rendering="crispEdges">',
    ]
    if title:
        lines.append(f"<title>{escape(title)}</title>")
    lines.append("<defs>")
    lines += [_pattern("warp", d, MH, True) for d in warp]
    lines += [_pattern("weft", d, MV, False) for d in weft]
    lines.append("</defs>")
    lines += [f'<path fill="url(#warp{d})" d="{"".join(p)}"/>' for d, p in warp.items()]
    lines += [f'<path fill="url(#weft{d})" d="{"".join(p)}"/>' for d, p in weft.items() if p]
    lines.append("</svg>")
    return "\n".join(lines) + "\n"
