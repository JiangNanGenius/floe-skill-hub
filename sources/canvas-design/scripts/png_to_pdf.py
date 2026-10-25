#!/usr/bin/env python3
# Floe first-party (MPL-2.0). See references/PROVENANCE.md.
"""png_to_pdf.py — wrap a REAL rendered PNG into a one-page PDF (stdlib only).

This is a containerizer, not a renderer: it never invents pixel content. Run it
on a PNG that was actually rendered elsewhere (native `browser.screenshot`
artifact, or any verified raster export of the poster). Input contract:
non-interlaced PNG, 8-bit, colour types gray/RGB/RGBA only; other classes fail
with an actionable message instead of producing a broken PDF.

Page size maps pixels to physical units via --dpi (default 300, the poster
declaration unit), so a 1080x1350px poster at 300dpi becomes 8.64x10.8in.

Output is verified by reopening the written PDF, inflating the embedded image
stream and comparing it against the pixel data that was written.

Exit codes: 0 success, 2 invalid input/output guard, 4 unsupported PNG class.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import zlib

MAX_PNG_BYTES = 64 * 1024 * 1024
MAX_DIM = 16384
PNG_SIG = b"\x89PNG\r\n\x1a\n"

def die(code, msg):
    sys.stderr.write("png_to_pdf: %s\n" % msg)
    sys.exit(code)

def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c

def decode_png(data):
    """Returns (width, height, rgb_rows) or raises ValueError(reason, retryable_class)."""
    if not data.startswith(PNG_SIG):
        die(2, "not a PNG file (bad signature)")
    pos = 8
    idat = []
    ihdr = None
    chunks_seen = []
    while pos + 8 <= len(data):
        ln = struct.unpack_from(">I", data, pos)[0]
        typ = data[pos + 4:pos + 8]
        body_start = pos + 8
        if ln > MAX_PNG_BYTES or body_start + ln + 4 > len(data):
            die(2, "truncated or oversized PNG chunk at offset %d" % pos)
        body = data[body_start:body_start + ln]
        crc = struct.unpack_from(">I", data, body_start + ln)[0]
        if zlib.crc32(typ + body) & 0xFFFFFFFF != crc:
            die(2, "chunk CRC failure in %s" % typ.decode("ascii", "replace"))
        chunks_seen.append(typ)
        if typ == b"IHDR":
            if ihdr is not None:
                die(2, "duplicate IHDR")
            (w, h, depth, ctype, comp, filt, interlace) = struct.unpack(">IIBBBBB", body)
            ihdr = (w, h, depth, ctype, interlace)
        elif typ == b"IDAT":
            idat.append(body)
            if sum(map(len, idat)) > MAX_PNG_BYTES:
                die(2, "IDAT exceeds %d bytes" % MAX_PNG_BYTES)
        elif typ == b"IEND":
            break
        pos = body_start + ln + 4
    else:
        die(2, "PNG ended without IEND")
    if ihdr is None or not idat:
        die(2, "PNG missing IHDR or IDAT")
    w, h, depth, ctype, interlace = ihdr
    if interlace != 0:
        die(4, "interlaced (Adam7) PNG unsupported; export non-interlaced first")
    if ctype not in (0, 2, 6):
        die(4, "color type %d unsupported (gray/RGB/RGBA only; convert palette PNGs)" % ctype)
    if depth != 8:
        die(4, "only 8-bit PNGs supported (got bit depth %d)" % depth)
    if not (1 <= w <= MAX_DIM and 1 <= h <= MAX_DIM):
        die(2, "dimensions %dx%d out of range" % (w, h))
    if b"PLTE" in chunks_seen and ctype != 3:
        die(2, "unexpected PLTE with color type %d" % ctype)
    channels = {0: 1, 2: 3, 6: 4}[ctype]
    max_uncompressed = h * (1 + w * channels)
    if max_uncompressed * 2 > (1 << 27):
        die(2, "decoded raster too large (limit 134 MB inflated)")
    d = zlib.decompressobj()
    raw = d.decompress(b"".join(idat), max_uncompressed + 1)
    if not d.eof or len(raw) > max_uncompressed:
        die(2, "PNG IDAT inflates beyond the declared raster size (possible zip bomb)")
    expected = max_uncompressed
    if len(raw) != expected:
        die(2, "inflate size mismatch: got %d, expect %d" % (len(raw), expected))
    stride = w * channels
    out = bytearray(h * w * 3)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                c = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + paeth(a, prev[i], c)) & 0xFF
        else:
            die(2, "invalid PNG filter type %d on row %d" % (ftype, y))
        base = y * w * 3
        if channels == 1:
            for x in range(w):
                g = line[x]
                out[base + x * 3:base + x * 3 + 3] = bytes((g, g, g))
        elif channels == 3:
            out[base:base + stride] = line
        else:
            for x in range(w):
                r, g, b, a = line[x * 4:x * 4 + 4]
                out[base + x * 3:base + x * 3 + 3] = bytes((
                    (r * a + 255 * (255 - a) + 127) // 255,
                    (g * a + 255 * (255 - a) + 127) // 255,
                    (b * a + 255 * (255 - a) + 127) // 255))
        prev = line
    return w, h, bytes(out), ctype

def build_pdf(w, h, rgb, dpi):
    pt_w = round(w * 72.0 / dpi, 2)
    pt_h = round(h * 72.0 / dpi, 2)
    stream = zlib.compress(rgb, 9)
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %g %g] "
                 "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>" % (pt_w, pt_h)).encode())
    objs.append(("<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                 "/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>" % (w, h, len(stream))).encode()
                + b"\nstream\n" + stream + b"\nendstream")
    content = ("q %g 0 0 %g 0 0 cm /Im0 Do Q" % (pt_w, pt_h)).encode()
    objs.append(b"<< /Length %d >>" % len(content) + b"\nstream\n" + content + b"\nendstream")
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, xref_pos))
    return bytes(out), pt_w, pt_h

def verify_pdf(path, expect_stream_sha):
    data = open(path, "rb").read()
    if not data.startswith(b"%PDF-1.7"):
        die(2, "self-verify failed: header")
    marker = b"/Subtype /Image"
    i = data.find(marker)
    if i == -1:
        die(2, "self-verify failed: image object missing")
    j = data.find(b"stream\n", i)
    k = data.find(b"\nendstream", j)
    payload = zlib.decompressobj().decompress(data[j + 7:k], (1 << 27))
    if hashlib.sha256(payload).hexdigest() != expect_stream_sha:
        die(2, "self-verify failed: embedded raster differs from decoded pixels")
    return len(payload)

def atomic_write(path, data, overwrite):
    if os.path.exists(path) and not overwrite:
        die(3, "refusing to overwrite existing %s (pass --overwrite)" % path)
    tmp = path + ".tmp-%05d" % (os.getpid() & 0xFFFF)
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser(prog="png_to_pdf")
    ap.add_argument("--input", required=True, help="workspace-relative rendered PNG")
    ap.add_argument("--output", required=True, help="workspace-relative PDF to write")
    ap.add_argument("--dpi", type=float, default=300.0, help="pixel->inch mapping used by the poster declaration")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if not (1.0 <= args.dpi <= 4000.0):
        die(2, "--dpi must be 1..4000")
    try:
        data = open(args.input, "rb").read()
    except OSError as e:
        die(2, "cannot read input: %s" % e)
    w, h, rgb, ctype = decode_png(data)
    pdf, pt_w, pt_h = build_pdf(w, h, rgb, args.dpi)
    outdir = os.path.dirname(args.output)
    if outdir and not os.path.isdir(outdir):
        try:
            os.makedirs(outdir)
        except OSError as e:
            die(2, "cannot create output directory: %s" % e)
    atomic_write(args.output, pdf, args.overwrite)
    checked = verify_pdf(args.output, hashlib.sha256(rgb).hexdigest())
    if checked != len(rgb):
        die(2, "self-verify byte length mismatch")
    sys.stdout.write(json.dumps({
        "pdf": args.output, "pdfBytes": len(pdf), "sourcePng": args.input,
        "pixels": [w, h], "pagePt": [pt_w, pt_h], "dpi": args.dpi,
        "colorType": ctype, "verified": True,
    }) + "\n")

if __name__ == "__main__":
    main()
