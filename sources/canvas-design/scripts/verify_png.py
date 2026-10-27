#!/usr/bin/env python3
# Floe first-party (MPL-2.0). See references/PROVENANCE.md.
"""verify_png.py — full PNG integrity + content verifier (stdlib only).

Answers the ONE question the poster pipeline must never fake: is this file a
REAL, complete PNG, and is it the file we think it is? It reads the actual
bytes, walks every chunk and recomputes every CRC32, inflates IDAT with a hard
uncompressed bound (zip-bomb guard), reconstructs the filtered scanlines to
prove the raster size is exactly right, and hashes the file (and optionally
the decoded pixels) — so "a status line said Exported" can never be mistaken
for "this delivered file is the raster".

Checks: PNG signature; chunk stream (length bound, per-chunk CRC); IHDR first,
single, sane (bit depth, color type, interlace); IDAT present, contiguous
enough to inflate, inflated length exactly (1 + w*channels) per row summed
over rows; filter types valid; IEND last (trailing bytes reported and refused
unless --allow-trailing); optional expectations compared fail-closed:
--expect-size WxH, --expect-sha256 (file digest), --expect-pixel-sha256 (with
--pixel-digest), --min-bytes/--max-bytes bounds.

Exit codes: 0 verified; 2 unreadable or corrupt PNG (integrity); 3 valid PNG
but expectations mismatched; 4 unsupported class for content digests (palette
or 16-bit PNGs still pass INTEGRITY checks — CRC and inflate — but pixel
digests are refused; size/sha expectations still work).

This verifier accepts the color-class superset PNGs from any engine produce
(8/16-bit, gray/RGB/RGBA/palette, non-interlaced and interlaced); only the
pixel-content digest requires the simple non-interlaced classes. Use it
BEFORE publishing a downloaded export: a delivered file that fails here was
not delivered intact, and no publishOutput receipt should quote it.
"""
import argparse
import hashlib
import json
import struct
import sys
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
MAX_CHUNK_BYTES = 64 * 1024 * 1024          # per-chunk length bound
MAX_INFLATED_BYTES = 1 << 27                 # 134 MB raster guard (zip bomb)
BITS_OK = {1, 2, 4, 8, 16}
CT_COLORS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
DIGEST_COLOR_TYPES = {0, 2, 6}               # gray/RGB/RGBA pixel digests


class IntegrityError(Exception):
    pass


def fail_integrity(msg):
    raise IntegrityError(msg)


def walk(data):
    """Returns (ihdr(w,h,depth,ctype,interlace), idat_bytes, chunks, trailing)."""
    if len(data) < len(PNG_SIG) or data[:8] != PNG_SIG:
        fail_integrity("bad PNG signature (not a PNG)")
    pos = 8
    ihdr = None
    idat = []
    idat_bytes = 0
    chunks = {}
    seen_order = []
    after_iend = 0
    while pos < len(data):
        if pos + 12 > len(data):
            fail_integrity("truncated chunk header at offset %d" % pos)
        ln = struct.unpack_from(">I", data, pos)[0]
        typ = data[pos + 4:pos + 8]
        if not all(32 <= b < 127 for b in typ):
            fail_integrity("non-ASCII chunk type at offset %d (corrupt stream)" % pos)
        if ln > MAX_CHUNK_BYTES:
            fail_integrity("chunk %s length %d exceeds cap %d" % (typ.decode("latin1"), ln, MAX_CHUNK_BYTES))
        if pos + 12 + ln > len(data):
            fail_integrity("truncated chunk %s (declared %d bytes) at offset %d" % (typ.decode("latin1"), ln, pos))
        body = data[pos + 8:pos + 8 + ln]
        crc = struct.unpack_from(">I", data, pos + 8 + ln)[0]
        if zlib.crc32(typ + body) & 0xFFFFFFFF != crc:
            fail_integrity("CRC mismatch in chunk %s at offset %d" % (typ.decode("latin1"), pos))
        chunks[typ.decode("latin1")] = chunks.get(typ.decode("latin1"), 0) + 1
        if after_iend:
            fail_integrity("chunk %s after IEND" % typ.decode("latin1"))
        seen_order.append(typ)
        if typ == b"IHDR":
            if ihdr is not None:
                fail_integrity("duplicate IHDR")
            if seen_order[0] != b"IHDR" or len(body) != 13:
                fail_integrity("IHDR must be the first chunk and 13 bytes")
            w, h, depth, ctype, comp, filt, interlace = struct.unpack(">IIBBBBB", body)
            if comp != 0 or filt != 0:
                fail_integrity("unsupported compression/filter method %d/%d" % (comp, filt))
            if ctype not in CT_COLORS:
                fail_integrity("invalid color type %d" % ctype)
            if depth not in BITS_OK or (ctype == 3 and depth > 8):
                fail_integrity("invalid bit depth %d for color type %d" % (depth, ctype))
            if interlace not in (0, 1):
                fail_integrity("invalid interlace %d" % interlace)
            if not (1 <= w <= 65535 and 1 <= h <= 65535):
                fail_integrity("dimensions out of PNG range: %dx%d" % (w, h))
            ihdr = (w, h, depth, ctype, interlace)
        elif typ == b"IDAT":
            if ihdr is None:
                fail_integrity("IDAT before IHDR")
            idat_bytes += ln
            if idat_bytes > MAX_CHUNK_BYTES:
                fail_integrity("IDAT exceeds cap %d bytes" % MAX_CHUNK_BYTES)
            idat.append(body)
        elif typ == b"IEND":
            if ln != 0:
                fail_integrity("IEND must be empty")
            after_iend = len(data) - (pos + 12 + ln)
            pos = pos + 12 + ln
            break
        pos = pos + 12 + ln
    if ihdr is None:
        fail_integrity("no IHDR")
    if not idat:
        fail_integrity("no IDAT")
    if not after_iend and pos >= len(data) and seen_order[-1] != b"IEND":
        fail_integrity("PNG ends without IEND")
    return ihdr, b"".join(idat), chunks, after_iend


def inflated_exact(idat_blob, w, h, depth, ctype, interlace):
    channels = CT_COLORS[ctype]
    bits_per_row_samples = w * channels * depth
    row_bytes = (bits_per_row_samples + 7) // 8
    if interlace == 0:
        expected = h * (1 + row_bytes)
    else:
        # Adam7: sum over the 7 passes of the rows that exist in each pass.
        expected = 0
        x0s = [0, 4, 0, 2, 0, 1, 0]
        y0s = [0, 0, 4, 0, 2, 0, 1]
        xds = [8, 8, 4, 4, 2, 2, 1]
        yds = [8, 8, 8, 4, 4, 2, 2]
        for p in range(7):
            pw = (w - x0s[p] + xds[p] - 1) // xds[p]
            ph = (h - y0s[p] + yds[p] - 1) // yds[p]
            if pw <= 0 or ph <= 0:
                continue
            prb = (pw * channels * depth + 7) // 8
            expected += ph * (1 + prb)
    if expected > MAX_INFLATED_BYTES:
        fail_integrity("declared raster too large to verify (%d bytes inflated cap)" % expected)
    d = zlib.decompressobj()
    raw = d.decompress(idat_blob, expected + 1)
    if len(raw) > expected:
        fail_integrity("IDAT inflates beyond the declared raster (possible zip bomb)")
    if not d.eof or len(raw) != expected:
        fail_integrity("IDAT inflate incomplete: got %d of expected %d bytes" % (len(raw), expected))
    return raw, row_bytes


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def unfilter_sha(raw, row_bytes, h, channels_bytes):
    """Non-interlaced unfiltered content digest. bytes_pp = per-pixel not needed:
    PNG filters work on byte offsets with bpp = ceil(channels*depth/8)."""
    m = hashlib.sha256()
    prev = bytearray(row_bytes)
    pos = 0
    for y in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + row_bytes])
        pos += row_bytes
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(channels_bytes, row_bytes):
                line[i] = (line[i] + line[i - channels_bytes]) & 0xFF
        elif ftype == 2:
            for i in range(row_bytes):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(row_bytes):
                a = line[i - channels_bytes] if i >= channels_bytes else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(row_bytes):
                a = line[i - channels_bytes] if i >= channels_bytes else 0
                c = prev[i - channels_bytes] if i >= channels_bytes else 0
                line[i] = (line[i] + paeth(a, prev[i], c)) & 0xFF
        else:
            fail_integrity("invalid filter type %d on row %d" % (ftype, y))
        m.update(bytes(line))
        prev = line
    if pos != len(raw):
        fail_integrity("unfilter consumed %d of %d bytes" % (pos, len(raw)))
    return m.hexdigest()


def main():
    ap = argparse.ArgumentParser(prog="verify_png")
    ap.add_argument("png", help="PNG file to verify")
    ap.add_argument("--expect-size", metavar="WxH", help="fail 3 unless IHDR size equals WxH")
    ap.add_argument("--expect-sha256", metavar="HEX", help="fail 3 unless the file sha256 matches")
    ap.add_argument("--pixel-digest", action="store_true",
                    help="also decode scanlines and hash the unfiltered pixel content")
    ap.add_argument("--expect-pixel-sha256", metavar="HEX",
                    help="with --pixel-digest: fail 3 unless the content digest matches")
    ap.add_argument("--min-bytes", type=int, default=1)
    ap.add_argument("--max-bytes", type=int, default=256 * 1024 * 1024)
    ap.add_argument("--allow-trailing", action="store_true",
                    help="permit (and report) bytes after IEND instead of refusing them")
    args = ap.parse_args()

    try:
        data = open(args.png, "rb").read()
    except OSError as e:
        sys.stderr.write("verify_png: cannot read: %s\n" % e)
        sys.exit(2)
    result = {"file": args.png, "bytes": len(data),
              "sha256": hashlib.sha256(data).hexdigest()}
    mismatch = []
    if not (args.min_bytes <= len(data) <= args.max_bytes):
        mismatch.append("file size %d outside bounds [%d,%d]" % (len(data), args.min_bytes, args.max_bytes))

    try:
        (w, h, depth, ctype, interlace), idat, chunks, trailing = walk(data)
    except IntegrityError as e:
        sys.stderr.write("verify_png: INTEGRITY FAIL: %s\n" % e)
        sys.exit(2)
    result.update({"size": [w, h], "bitDepth": depth, "colorType": ctype,
                   "interlaced": interlace == 1, "chunks": chunks})
    if trailing and not args.allow_trailing:
        sys.stderr.write("verify_png: INTEGRITY FAIL: %d bytes trail IEND "
                         "(pass --allow-trailing to accept)\n" % trailing)
        sys.exit(2)
    if trailing:
        result["trailingBytes"] = trailing

    try:
        raw, row_bytes = inflated_exact(idat, w, h, depth, ctype, interlace)
        result["idatInflatedBytes"] = len(raw)
    except IntegrityError as e:
        sys.stderr.write("verify_png: INTEGRITY FAIL: %s\n" % e)
        sys.exit(2)

    if args.pixel_digest:
        if interlace or depth != 8 or ctype not in DIGEST_COLOR_TYPES:
            sys.stderr.write("verify_png: UNSUPPORTED for pixel digest "
                             "(interlaced or bit depth %d or color type %d; integrity passed)\n"
                             % (depth, ctype))
            sys.exit(4)
        channels_bytes = max(1, (CT_COLORS[ctype] * depth + 7) // 8)
        result["pixelSha256"] = unfilter_sha(raw, row_bytes, h, channels_bytes)

    if args.expect_size:
        try:
            ew, eh = (int(x) for x in args.expect_size.lower().split("x"))
        except ValueError:
            sys.stderr.write("verify_png: bad --expect-size (use WxH)\n")
            sys.exit(2)
        if [ew, eh] != [w, h]:
            mismatch.append("size %dx%d != expected %dx%d" % (w, h, ew, eh))
    if args.expect_sha256 and result["sha256"] != args.expect_sha256.lower():
        mismatch.append("file sha256 != expected")
    if args.expect_pixel_sha256:
        if "pixelSha256" not in result:
            mismatch.append("--expect-pixel-sha256 requires --pixel-digest")
        elif result["pixelSha256"] != args.expect_pixel_sha256.lower():
            mismatch.append("pixel sha256 != expected")

    if mismatch:
        result["ok"] = False
        result["mismatches"] = mismatch
        sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
        sys.stderr.write("verify_png: MISMATCH: " + "; ".join(mismatch) + "\n")
        sys.exit(3)
    result["ok"] = True
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
