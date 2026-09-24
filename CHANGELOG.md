# changelog

all notable changes to sett. the format follows [keep a changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [semver](https://semver.org/) as far as a command line tool has an api.

## 0.1.0 - 2026-09-24

first cut: the sha256 of a file, a text or a hex digest, woven into a small piece of cloth.

- one png a digest, named after its first 12 hex digits; `--svg` for svg
- `--compare` puts two files side by side in one picture and exits with 1 when the digests differ
- `--size`, `--ends` and `--picks` for bigger pictures and other numbers of threads
- `SPEC.md`: every rule and table, one digest worked step by step, known answers
