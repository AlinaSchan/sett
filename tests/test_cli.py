"""the command line, on real files in a temporary folder."""
import hashlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pngread
import pytest

import sett
from sett import cli
from sett.weave import picture, weave

ROOT = Path(__file__).resolve().parent.parent
EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
HELLO = hashlib.sha256(b"hello\n").hexdigest()
HULLO = hashlib.sha256(b"hullo\n").hexdigest()


def woven(*digests: str, size: int = 4, ends: int = 40, picks: int = 40) -> tuple[int, int, bytes]:
    width, height, rows = picture([weave(bytes.fromhex(d), ends, picks) for d in digests], size)
    return width, height, b"".join(rows)


def test_one_file(tmp_path, capsys):
    note = tmp_path / "note.txt"
    note.write_bytes(b"hello\n")
    out = tmp_path / "out"
    assert cli.main([str(note), "--out", str(out)]) == 0
    picture_path = out / f"{HELLO[:12]}.png"
    size = picture_path.stat().st_size
    assert capsys.readouterr().out.splitlines() == [f"{HELLO}  {note}", f"wrote {picture_path} ({size:,} bytes)"]
    assert pngread.read(picture_path.read_bytes()) == woven(HELLO)
    assert sorted(p.name for p in out.iterdir()) == [picture_path.name]      # no leftovers


def test_the_current_folder_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    Path("empty").write_bytes(b"")
    Path("note").write_bytes(b"hello\n")
    assert cli.main(["empty", "note"]) == 0
    out = capsys.readouterr().out
    assert f"{EMPTY}  empty\nwrote e3b0c44298fc.png (" in out and f"{HELLO}  note\nwrote {HELLO[:12]}.png (" in out
    assert Path("e3b0c44298fc.png").is_file() and Path(f"{HELLO[:12]}.png").is_file()


def test_text_and_hex(tmp_path, capsys):
    assert cli.main(["--text", "", "--out", str(tmp_path)]) == 0
    first = (tmp_path / "e3b0c44298fc.png").read_bytes()
    for spelling in (EMPTY, EMPTY.upper(), f"sha256:{EMPTY}", f"SHA256:{EMPTY.upper()}", f" {EMPTY}\n"):
        assert cli.main(["--hex", spelling, "--out", str(tmp_path)]) == 0
        assert (tmp_path / "e3b0c44298fc.png").read_bytes() == first
    out = capsys.readouterr().out
    assert f"{EMPTY}  (text)" in out and f"{EMPTY}  (hex)" in out
    assert cli.main(["--text", "café", "--out", str(tmp_path)]) == 0
    assert capsys.readouterr().out.startswith(hashlib.sha256("café".encode()).hexdigest() + "  (text)\n")


def test_svg(tmp_path, capsys):
    assert cli.main(["--hex", HELLO, "--svg", "--size", "8", "--out", str(tmp_path)]) == 0
    root = ET.fromstring((tmp_path / f"{HELLO[:12]}.svg").read_text(encoding="utf-8"))
    assert (root.get("width"), root.get("height")) == ("320", "320")
    assert root.find("{http://www.w3.org/2000/svg}title").text == f"sha256 {HELLO}"
    assert f"wrote {tmp_path / (HELLO[:12] + '.svg')} (" in capsys.readouterr().out


def test_size_ends_and_picks(tmp_path):
    assert cli.main(["--hex", HELLO, "--size", "8", "--out", str(tmp_path / "big")]) == 0
    assert pngread.read((tmp_path / "big" / f"{HELLO[:12]}.png").read_bytes()) == woven(HELLO, size=8)
    assert cli.main(["--hex", HELLO, "--ends", "36", "--picks", "38", "--out", str(tmp_path / "row")]) == 0
    width, height, rgba = pngread.read((tmp_path / "row" / f"{HELLO[:12]}.png").read_bytes())
    assert (width, height, rgba) == woven(HELLO, ends=36, picks=38) and (width, height) == (144, 152)


def test_compare(tmp_path, capsys):
    a, b, c = tmp_path / "a.txt", tmp_path / "b.txt", tmp_path / "c.txt"
    a.write_bytes(b"hello\n")
    b.write_bytes(b"hello\n")
    c.write_bytes(b"hullo\n")
    assert cli.main(["--compare", str(a), str(b), "--out", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines()[2] == "the digests match"
    assert cli.main(["--compare", str(a), str(c), "--out", str(tmp_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    both = tmp_path / f"{HELLO[:12]}-vs-{HULLO[:12]}.png"
    assert lines == [f"{HELLO}  {a}", f"{HULLO}  {c}", "the digests differ",
                     f"wrote {both} ({both.stat().st_size:,} bytes)"]
    assert pngread.read(both.read_bytes()) == woven(HELLO, HULLO)
    assert cli.main(["--compare", str(a), str(c), "--svg", "--out", str(tmp_path)]) == 1
    assert (tmp_path / f"{HELLO[:12]}-vs-{HULLO[:12]}.svg").is_file()


def test_compare_says_when_the_cloths_cannot_tell(tmp_path, capsys):
    # one end and one pick leave almost nothing of the digest: these two different texts weave the same cloth
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"weave parity 3")
    b.write_bytes(b"hello\n")
    assert cli.main(["--compare", str(a), str(b), "--ends", "1", "--picks", "1", "--out", str(tmp_path)]) == 1
    assert "the digests differ, but they weave the same cloth" in capsys.readouterr().out


def test_bad_inputs_write_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    good = tmp_path / "good.txt"
    good.write_bytes(b"hello\n")
    assert cli.main([str(good), str(tmp_path / "missing.txt"), "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert f"sett: no such file: {tmp_path / 'missing.txt'}" in err and "nothing written" in err
    assert not out.exists()
    assert cli.main([str(tmp_path), "--out", str(out)]) == 2
    assert "is a folder" in capsys.readouterr().err
    assert cli.main(["--compare", str(good), str(tmp_path / "gone"), "--out", str(out)]) == 2
    for bad in ("abc", "g" * 64, EMPTY[:-1], EMPTY + "0", "sha1:" + EMPTY, ""):
        assert cli.main(["--hex", bad, "--out", str(out)]) == 2
        assert "not a sha256 digest" in capsys.readouterr().err
    assert not out.exists()


def test_an_out_folder_that_is_a_file(tmp_path, capsys):
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"")
    assert cli.main(["--text", "x", "--out", str(blocker)]) == 2
    assert "sett: cannot write to" in capsys.readouterr().err


@pytest.mark.parametrize("argv", [
    [], ["a.txt", "--text", "x"], ["--text", "x", "--hex", EMPTY], ["--compare", "a.txt"],
    ["--text", "x", "--size", "6"], ["--text", "x", "--size", "0"], ["--text", "x", "--ends", "0"],
    ["--text", "x", "--size", "4096"], ["--text", "x", "--picks", "1025"],
])
def test_usage_errors(argv, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(argv)
    assert e.value.code == 2
    assert "usage: sett" in capsys.readouterr().err


def test_python_dash_m_and_the_version():
    r = subprocess.run([sys.executable, "-m", "sett", "--version"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == f"sett {sett.__version__}"
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version = "(.+)"$', project, re.M)[1] == sett.__version__
    assert 'sett = "sett.cli:main"' in project


# the pictures in examples/, and the digests and --size they were made with (see the readme)
EXAMPLES = {
    "license.png": (["e666a4b6ff5433a2b56e9d694dcd189527d02fba12cec49240ac24195f998053"], 8),
    "empty.png": ([EMPTY], 8),
    "hello-vs-hullo.png": ([HELLO, HULLO], 8),
}


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_examples(name):
    data = (ROOT / "examples" / name).read_bytes()
    digests, size = EXAMPLES[name]
    assert len(data) < 50 * 1024
    assert pngread.read(data) == woven(*digests, size=size)
