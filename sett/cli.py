"""command line: sett FILE [FILE ...] | sett --text TEXT | sett --hex DIGEST | sett --compare A B"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

from . import __version__, png, svg
from .weave import ENDS, PICKS, Cloth, T, picture, pixels, weave

MAX_SIDE = 4096                             # pixels a swatch may have on a side
HEX = re.compile(r"[0-9a-f]{64}")
EPILOG = ("exit status: 0 when the pictures are written (for --compare: and the digests match), "
          "1 when --compare finds two different digests, 2 when an input cannot be used.")


class InputError(Exception):
    """an input that cannot be read, or is not a digest."""


def digest(kind: str, value: str) -> bytes:
    """the sha256 an input names: a file's bytes, a text as utf-8, or a digest written in hex."""
    if kind == "text":
        return hashlib.sha256(value.encode("utf-8", "surrogateescape")).digest()
    if kind == "hex":
        h = value.strip().lower().removeprefix("sha256:").strip()
        if not HEX.fullmatch(h):
            raise InputError(f"not a sha256 digest: {value!r} (64 hex characters, with or without sha256: in front)")
        return bytes.fromhex(h)
    if os.path.isdir(value):
        raise InputError(f"{value} is a folder, not a file")
    h = hashlib.sha256()
    try:
        with open(value, "rb") as f:
            while block := f.read(1 << 20):
                h.update(block)
    except FileNotFoundError:
        raise InputError(f"no such file: {value}") from None
    except OSError as e:
        raise InputError(f"cannot read {value}: {e.strerror or e}") from None
    return h.digest()


def verdict(a: bytes, b: bytes, cloth_a: Cloth, cloth_b: Cloth) -> str:
    if a == b:
        return "the digests match"
    if pixels(cloth_a) == pixels(cloth_b):          # a thread that is never on top can differ unseen
        return "the digests differ, but they weave the same cloth: only the hex tells them apart"
    return "the digests differ"


def render(cloths: list[Cloth], size: int, as_svg: bool, title: str) -> bytes:
    if as_svg:
        return svg.render(cloths, size, title).encode("utf-8")
    return png.encode(*picture(cloths, size))


def write(path: str, data: bytes) -> None:
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")   # an odd file name never crashes the console
    ap = argparse.ArgumentParser(prog="sett", description="weave the sha256 of a file into a small piece of cloth.",
                                 epilog=EPILOG)
    ap.add_argument("files", nargs="*", metavar="FILE", help="files to weave, one picture each")
    one = ap.add_mutually_exclusive_group()
    one.add_argument("--text", help="weave the sha256 of this text, as utf-8")
    one.add_argument("--hex", metavar="DIGEST",
                     help="weave a sha256 you already have: 64 hex characters, with or without sha256: in front")
    one.add_argument("--compare", nargs=2, metavar=("A", "B"),
                     help="weave two files side by side in one picture and say whether the digests match")
    ap.add_argument("--out", metavar="DIR", help="folder for the pictures (default: the current folder)")
    ap.add_argument("--svg", action="store_true", help="write svg instead of png")
    ap.add_argument("--size", type=int, default=T, metavar="PX",
                    help=f"pixels a thread, a multiple of {T} (default {T}: 40 ends make 160 pixels)")
    ap.add_argument("--ends", type=int, default=ENDS, metavar="N", help=f"warp ends, left to right (default {ENDS})")
    ap.add_argument("--picks", type=int, default=PICKS, metavar="N", help=f"picks, top to bottom (default {PICKS})")
    ap.add_argument("--version", action="version", version=f"sett {__version__}")
    args = ap.parse_args(argv)

    if bool(args.files) + (args.text is not None) + (args.hex is not None) + (args.compare is not None) != 1:
        ap.error("give one or more files, or one of --text, --hex, --compare")
    if args.size < T or args.size % T:
        ap.error(f"--size must be a multiple of {T}: a thread is {T} pixels and only grows by whole pixels")
    if args.ends < 1 or args.picks < 1:
        ap.error("--ends and --picks must be 1 or more")
    if max(args.ends, args.picks) * args.size > MAX_SIDE:
        ap.error(f"a swatch of {args.ends * args.size} x {args.picks * args.size} pixels; "
                 f"the limit is {MAX_SIDE} a side")

    if args.text is not None:
        todo = [("(text)", "text", args.text)]
    elif args.hex is not None:
        todo = [("(hex)", "hex", args.hex)]
    else:
        todo = [(name, "file", name) for name in args.compare or args.files]
    found: list[tuple[str, bytes]] = []
    problems: list[str] = []
    for name, kind, value in todo:
        try:
            found.append((name, digest(kind, value)))
        except InputError as e:
            problems.append(str(e))
    if problems:
        for p in problems:
            print(f"sett: {p}", file=sys.stderr)
        print("sett: nothing written", file=sys.stderr)
        return 2

    out = args.out or ""
    ext = "svg" if args.svg else "png"
    try:
        if out:
            os.makedirs(out, exist_ok=True)
        if args.compare:
            (name_a, a), (name_b, b) = found
            cloth_a, cloth_b = weave(a, args.ends, args.picks), weave(b, args.ends, args.picks)
            data = render([cloth_a, cloth_b], args.size, args.svg,
                          f"sha256 {a.hex()} (left) and sha256 {b.hex()} (right)")
            path = os.path.join(out, f"{a.hex()[:12]}-vs-{b.hex()[:12]}.{ext}")
            write(path, data)
            print(f"{a.hex()}  {name_a}")
            print(f"{b.hex()}  {name_b}")
            print(verdict(a, b, cloth_a, cloth_b))
            print(f"wrote {path} ({len(data):,} bytes)")
            return 0 if a == b else 1
        for name, d in found:
            data = render([weave(d, args.ends, args.picks)], args.size, args.svg, f"sha256 {d.hex()}")
            path = os.path.join(out, f"{d.hex()[:12]}.{ext}")
            write(path, data)
            print(f"{d.hex()}  {name}")
            print(f"wrote {path} ({len(data):,} bytes)")
    except OSError as e:
        print(f"sett: cannot write to {out or 'the current folder'}: {e.strerror or e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
