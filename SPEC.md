# the sett of a digest

this is the whole algorithm. `sett/weave.py` implements it, `sett/png.py` and `sett/svg.py` write it down, and the
tests hold all three to known answers. everything below is integer arithmetic. nothing depends on floating point,
colour management or image smoothing, so another language can weave the same pixels.

a sett is the repeat of a tartan or of a block weave. here it is drawn from the 32 bytes of a sha256 digest.

## input

`d` is the digest as bytes, `d[0]` to `d[31]`. the command line gets it by hashing a file, or a text encoded as
utf-8, or it takes the 64 hex digits as they are.

## geometry

a thread is `t = 4` pixels wide. warp ends are columns (index `x`, left to right) and picks are rows (index `y`,
top to bottom). a cloth has `ends` x `picks` crossings, 40 x 40 unless asked otherwise, so the picture is 160 x 160
pixels. any other numbers of ends and picks, from 1 up, follow the same rules.

the file is named after `sha12`, the first 12 hex digits of the digest: `{sha12}.png` or `{sha12}.svg`, and
`{sha12 of a}-vs-{sha12 of b}.png` for two cloths side by side.

## step 1: fields

bytes 0 to 3 give four warp field widths, bytes 4 to 7 four weft field heights:

    ww[i] = 1 + d[i] mod 5          (i = 0..3)
    wh[i] = 1 + d[4 + i] mod 5

`fields(w, n)` spreads `n` threads over the four fields in proportion to `w`. with `s = w[0] + w[1] + w[2] + w[3]`
and `a[i] = w[0] + ... + w[i]`, thread `k` (0 <= k < n) belongs to the smallest `i` with

    2 * n * a[i]  >  (2k + 1) * s

that is: the centre of thread `k`, at `(k + 1/2) / n`, lies before the end of field `i`. the last field always
passes this test, so every thread gets a field, and the fields are runs of neighbouring threads. then

    wf[x] = fields(ww, ends)[x]
    sf[y] = fields(wh, picks)[y]

## step 2: dyes

six dyes, numbered 0 to 5:

| number | dye | rgb |
|---|---|---|
| 0 | madder | `#a2381f` = 162, 56, 31 |
| 1 | weld | `#d9ac3f` = 217, 172, 63 |
| 2 | indigo | `#26345c` = 38, 52, 92 |
| 3 | walnut | `#6b4a30` = 107, 74, 48 |
| 4 | undyed | `#e6dcc6` = 230, 220, 198 |
| 5 | oak gall | `#2a231e` = 42, 35, 30 |

    warp dye of end x   = dye[ d[8 + wf[x]] mod 6 ]
    weft dye of pick y  = dye[ d[12 + sf[y]] mod 6 ]

## step 3: which thread is on top

the fields cut the cloth into 4 x 4 blocks. bytes 16 to 31 give one byte a block:

    b    = d[16 + 4 * sf[y] + wf[x]]
    face = b mod 5
    z    = +1 if b >= 128 else -1                 (the direction of the diagonal)
    k4   = (x + z * y) mod 4
    k5   = (2 * x + z * y) mod 5                  (mod is the remainder from 0 up, also for a negative number)

    face 0 or 1:  the weft is on top unless k5 = 0     (weft-faced five-end satin)
    face 2 or 3:  the weft is on top only when k5 = 0  (warp-faced five-end satin)
    face 4:       the weft is on top when k4 < 2       (2/2 twill)

in c, java or javascript `%` keeps the sign of the dividend, so a port writes `((v % m) + m) % m`.

## step 4: the pixels of one crossing

the crossing of end `x` and pick `y` covers the pixels `(4x + i, 4y + j)` for `i, j = 0..3`. its colour `c` is the
weft dye when the weft is on top, else the warp dye. a thread is round, so each pixel gets a brightness `m`, in
1/256:

    weft on top:  m = mv[j],  mv = [234, 276, 276, 173]   (rows across the pick; the last one is the shed line)
    warp on top:  m = mh[i],  mh = [234, 276, 276, 183]   (columns across the end; the last one is the gap)

    channel = min(255, (c_channel * m + 128) >> 8)          for r, g and b;  alpha = 255

the two tables are the spec. they came from `round(256 * (0.8 + 0.3 * sin(pi * (k + 1/2) / 4)))`, which is 234,
276, 276, 234, with the last entry times 0.74 and 0.78, rounded half up in integers: `(234 * 74 + 50) // 100 = 173`
and `(234 * 78 + 50) // 100 = 183`. a cloth has at most 24 colours: 6 dyes at 4 brightness values.

## bigger pictures

`--size p` draws a thread `p` pixels wide, where `p` is a multiple of 4. each pixel of step 4 becomes a square of
`p/4` x `p/4` pixels and nothing else changes, so a bigger picture is the same cloth. the default is `p = 4`. the
command line refuses a cloth of more than 4096 pixels on a side.

## two cloths side by side

`--compare` puts two cloths with the same ends and picks into one picture: the first on the left, the second on
the right, and between them a gap of two threads (`2p` pixels) of transparent pixels, `(0, 0, 0, 0)`.

## the png

8 bits a channel, srgb, no gamma chunk, no colour profile. the file is a palette png with these chunks, in this
order, and no others (no time, no text):

- `IHDR`: width, height, bit depth 8, colour type 3, compression 0, filter 0, no interlace.
- `PLTE`: every colour of the picture once, sorted by the number `r << 24 | g << 16 | b << 8 | a`.
- `tRNS`: only when a colour is not opaque: the alpha of each palette entry, up to the last one below 255. with the
  gap of a side by side picture that is one byte, `00`, because `(0, 0, 0, 0)` sorts first.
- `IDAT`: one chunk. each row is a filter byte 0 and one palette index a pixel; all rows go through zlib at level 9.
- `IEND`.

so the same pixels give the same bytes with the same zlib. another zlib build may pack the same rows into other
bytes; the rows themselves, and so the picture, do not change.

## the svg

the svg draws the same picture with shapes. its `viewBox` counts 4 units a thread (160 x 160 for 40 x 40), its
`width` and `height` are the size in pixels (`ends * p` by `picks * p`), and it sets
`shape-rendering="crispEdges"`. inside, in this order:

- a `<title>` with the digest.
- one 4 x 4 `<pattern>` with `patternUnits="userSpaceOnUse"` for each dye that the warp uses, `warp{n}`, made of
  four columns 1 unit wide in the brightness of `mh`; then one for each dye of the weft, `weft{n}`, made of four
  rows 1 unit high in the brightness of `mv`. `n` is the dye number. the tiles start at 0, 0, so they line up
  with the threads.
- the warp: for each warp dye, by number, one `<path>` filled with its pattern, with one full-height rectangle for
  each run of neighbouring ends of that dye.
- the weft on top of it: for each weft dye, by number, one `<path>` with a rectangle for each run of neighbouring
  crossings in a pick where that pick's weft is on top. a weft dye that is never on top gets no path.

each rectangle is written `M{x} {y}h{w}v{h}h-{w}z`. painted, the svg gives the pixels of the png exactly.

## one digest, step by step

the sha256 of the empty string is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

- `ww = [3, 2, 2, 2]`, so the 40 ends fall into fields of 13, 9, 9 and 9. `wh = [3, 3, 4, 1]`, so the 40 picks
  fall into fields of 11, 11, 14 and 4.
- bytes 8 to 11 are 154, 251, 244, 200: the warp fields are undyed, oak gall, undyed, indigo. bytes 12 to 15 are
  153, 111, 185, 36: the weft fields are walnut, walnut, oak gall, madder.
- the block of pick 0 and end 0 is byte 16, `0x27` = 39: face 4, a twill, with `z = -1`.
- at end 0 and pick 0, `k4 = 0`, so the weft is on top. pixel (0, 0) is walnut at 234: `(98, 68, 44, 255)`.
  pixel (0, 3) is walnut at 173: `(72, 50, 32, 255)`.
- at end 2 and pick 0, `k4 = 2`, so the warp is on top. pixel (8, 0) is undyed at 234: `(210, 201, 181, 255)`,
  and pixel (11, 0) undyed at 183: `(164, 157, 142, 255)`.
- along pick 0 the weft is on top (`w`) or under (`-`) like this:
  `ww--ww--ww--ww--ww--wwwww-wwww-----w----`.

## known answers

the golden hash of a cloth is the sha256 of its raw rgba bytes, row by row from the top, at `p = 4` (for 40 x 40
that is 160 * 160 * 4 = 102,400 bytes).

| text hashed | ends x picks | golden hash |
|---|---|---|
| the empty string | 40 x 40 | `3aec9e891860a3695d77ac68a149f7c571c323ba2689995adad2a1942ec0eca6` |
| the empty string | 36 x 38 | `b8b1ad82bbc47e722dcf83de58b855068402e5041357ac4f54f9e07f6280e511` |
| the empty string | 8 x 8 | `b530a8477d5c234ca28d2670b4d34b83858bb277eeb29c455f8746d3a2818100` |
| `hello` and a newline | 40 x 40 | `8c8024fa7f1ea245781d896cf5dccb34e0f6fb14ee35df8aafb36c07799f1508` |
| `hullo` and a newline | 40 x 40 | `f4576bc901e034ea5752a17342a60d494f449f6bc7e7985518f8fa5da32d266b` |
| `hello` and a newline | 1 x 1 | `e9250e3de8a6a61a7fd361fe3ff4dab067d68915a7d0adcf7db0b98409ec3fd6` |
| `weave parity 3` | 1 x 1 | `e9250e3de8a6a61a7fd361fe3ff4dab067d68915a7d0adcf7db0b98409ec3fd6` |

the last two rows are two different digests with the same cloth, which one crossing makes easy.

## what changes a sett

the sett reads its bytes modulo 5 or 6, and the top bit of each block byte. a digest with `d[0] = 7` and one with
`d[0] = 12` give the first warp field the same width, and so on: at most about 80 of the 256 bits show in the
cloth. a changed
file almost always weaves a different cloth, but an equal cloth does not prove an equal digest. with enough
computing power someone could make a second file that weaves the same cloth; they could not make one with the
same digest. the picture is a quick check for the eye. when it matters, compare the hex.

the algorithm is fixed. changing a table here changes every cloth and every known answer above.
