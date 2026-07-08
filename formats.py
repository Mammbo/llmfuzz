"""Format-aware tooling for LLM-guided fuzzing of non-text inputs.

The thesis (per Penghui): models don't understand raw bytes -- they reason
about binaries through text-extraction tools. So we give the model those tools
explicitly and deterministically instead of hoping its internal heuristics
work:

    detect_format(data)      -> 'png' | 'pdf' | 'mp4' | 'elf' | ... | 'unknown'
    hexdump(data, off, n)    -> annotated hex+ascii the model can read
    parse(data)              -> structural view with byte offsets
    apply_patch(data, edits) -> new bytes from (offset, hex) edits
    fix(data)                -> repair format checksums/lengths after edits

`fix` is the piece that silently kills naive LLM binary generation: change one
byte of a PNG and every downstream CRC check rejects the file long before the
target branch. Here CRCs/lengths/xref-offsets get repaired automatically.
"""
from __future__ import annotations
import binascii, struct


# ---------------------------------------------------------------- detection
_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"%PDF",             "pdf"),
    (b"\x7fELF",          "elf"),
    (b"\xff\xd8\xff",     "jpeg"),
    (b"GIF8",             "gif"),
    (b"II*\x00",          "tiff"),
    (b"MM\x00*",          "tiff"),
    (b"PK\x03\x04",       "zip"),
    (b"\x1f\x8b",         "gzip"),
]


def detect_format(data: bytes) -> str:
    for magic, name in _MAGIC:
        if data.startswith(magic):
            return name
    # mp4/mov: 'ftyp' box at offset 4
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "mp4"
    return "unknown"


# ---------------------------------------------------------------- hexdump
def hexdump(data: bytes, offset: int = 0, length: int | None = None) -> str:
    end = len(data) if length is None else min(len(data), offset + length)
    out = []
    for base in range(offset, end, 16):
        chunk = data[base:base + 16]
        hexs = " ".join(f"{b:02x}" for b in chunk)
        asci = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"{base:08x}  {hexs:<47}  |{asci}|")
    return "\n".join(out)


# ---------------------------------------------------------------- patching
def apply_patch(data: bytes, edits: list[dict]) -> bytes:
    """Apply in-place byte edits. Each edit: {"offset": int, "hex": "deadbeef"}.

    Edits are same-length overwrites (the common case for flipping a field that
    guards a branch). Length-changing structural edits should be expressed as
    chunk/atom replacements at the format layer, not here.
    """
    buf = bytearray(data)
    for e in edits:
        off = int(e["offset"])
        raw = bytes.fromhex(e["hex"].replace(" ", ""))
        if off < 0 or off + len(raw) > len(buf):
            raise ValueError(f"edit at {off} (+{len(raw)}) out of range {len(buf)}")
        buf[off:off + len(raw)] = raw
    return bytes(buf)


def fix(data: bytes) -> bytes:
    """Repair format-specific integrity fields after edits. No-op if unknown."""
    fmt = detect_format(data)
    return {"png": png_fix, "gzip": gzip_fix}.get(fmt, lambda d: d)(data)


def parse(data: bytes) -> str:
    """Return a text structural view with byte offsets, dispatched on format."""
    fmt = detect_format(data)
    fn = {
        "png": png_parse, "pdf": pdf_parse, "mp4": mp4_parse, "elf": elf_parse,
    }.get(fmt)
    header = f"format: {fmt}   size: {len(data)} bytes\n"
    return header + (fn(data) if fn else hexdump(data, 0, 256))


# ================================================================ PNG
_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _png_chunks(data: bytes):
    """Yield (offset, length, ctype, cdata, crc) walking the chunk stream."""
    pos = len(_PNG_SIG)
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        cdata = data[pos + 8:pos + 8 + length]
        crc = data[pos + 8 + length:pos + 12 + length]
        yield pos, length, ctype, cdata, crc
        pos += 12 + length
        if ctype == b"IEND":
            break


def png_parse(data: bytes) -> str:
    out = []
    for off, length, ctype, cdata, crc in _png_chunks(data):
        want = struct.pack(">I", binascii.crc32(ctype + cdata) & 0xFFFFFFFF)
        ok = "ok" if want == crc else "BAD"
        note = ""
        if ctype == b"IHDR" and length >= 13:
            w, h, bd, ct = struct.unpack(">IIBB", cdata[:10])
            note = f"  width={w} height={h} bitdepth={bd} colortype={ct}"
        out.append(
            f"@{off:<6} {ctype.decode('latin1')} len={length} "
            f"data@{off+8} crc@{off+8+length} crc={ok}{note}"
        )
    return "\n".join(out)


def png_fix(data: bytes) -> bytes:
    """Recompute every chunk CRC in place (lengths assumed unchanged)."""
    buf = bytearray(data)
    for off, length, ctype, cdata, _crc in _png_chunks(bytes(buf)):
        crc = binascii.crc32(ctype + cdata) & 0xFFFFFFFF
        struct.pack_into(">I", buf, off + 8 + length, crc)
    return bytes(buf)


def png_write(width: int, height: int, colortype: int = 0, bitdepth: int = 8,
              idat_raw: bytes | None = None) -> bytes:
    """Minimal valid PNG writer (used for tests / seed synthesis)."""
    import zlib
    def chunk(ctype: bytes, cdata: bytes) -> bytes:
        crc = binascii.crc32(ctype + cdata) & 0xFFFFFFFF
        return struct.pack(">I", len(cdata)) + ctype + cdata + struct.pack(">I", crc)
    ihdr = struct.pack(">IIBBBBB", width, height, bitdepth, colortype, 0, 0, 0)
    if idat_raw is None:
        idat_raw = b"\x00" * (height * (1 + width))  # grayscale, filter 0
    idat = zlib.compress(idat_raw)
    return _PNG_SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ================================================================ GZIP
def gzip_fix(data: bytes) -> bytes:
    """Repair the trailing CRC32 + ISIZE of a single-member gzip stream.

    We must NOT use gzip.decompress() here -- it validates the CRC and raises
    exactly when the trailer is broken (the only time this is called). Instead
    parse the gzip header to locate the raw DEFLATE body, inflate it with
    wbits=-15 (raw, no checksum), then recompute crc32 + isize over the result.
    """
    import zlib
    if len(data) < 18 or data[:2] != b"\x1f\x8b":
        return data
    flg = data[3]
    pos = 10                                  # fixed header
    if flg & 0x04:                            # FEXTRA
        (xlen,) = struct.unpack("<H", data[pos:pos + 2]); pos += 2 + xlen
    if flg & 0x08:                            # FNAME
        pos = data.index(b"\x00", pos) + 1
    if flg & 0x10:                            # FCOMMENT
        pos = data.index(b"\x00", pos) + 1
    if flg & 0x02:                            # FHCRC
        pos += 2
    body = data[pos:len(data) - 8]
    try:
        raw = zlib.decompressobj(-15).decompress(body)
    except Exception:
        return data
    buf = bytearray(data)
    struct.pack_into("<I", buf, len(buf) - 8, zlib.crc32(raw) & 0xFFFFFFFF)
    struct.pack_into("<I", buf, len(buf) - 4, len(raw) & 0xFFFFFFFF)
    return bytes(buf)


# ================================================================ PDF
def pdf_parse(data: bytes) -> str:
    out, i = [], 0
    while True:
        j = data.find(b" obj", i)
        if j == -1:
            break
        ls = data.rfind(b"\n", 0, j) + 1
        head = data[ls:j + 4].decode("latin1", "replace").strip()
        end = data.find(b"endobj", j)
        out.append(f"@{ls:<7} {head}  (endobj@{end})")
        i = j + 4
    sx = data.rfind(b"startxref")
    if sx != -1:
        tail = data[sx:sx + 40].split(b"\n")
        out.append(f"@{sx:<7} startxref -> {tail[1].decode('latin1','replace').strip() if len(tail)>1 else '?'}")
    return "\n".join(out) or hexdump(data, 0, 256)


# ================================================================ MP4
def mp4_parse(data: bytes, pos: int = 0, end: int | None = None, depth: int = 0) -> str:
    end = len(data) if end is None else end
    out = []
    while pos + 8 <= end:
        (size,) = struct.unpack(">I", data[pos:pos + 4])
        atom = data[pos + 4:pos + 8].decode("latin1", "replace")
        real = size if size > 1 else (end - pos)
        out.append(f"{'  '*depth}@{pos:<7} {atom} size={size}")
        if atom in ("moov", "trak", "mdia", "minf", "stbl", "moof", "traf"):
            out.append(mp4_parse(data, pos + 8, pos + real, depth + 1))
        pos += real if real >= 8 else 8
    return "\n".join(x for x in out if x)


# ================================================================ ELF
def elf_parse(data: bytes) -> str:
    if len(data) < 20:
        return "truncated ELF"
    ei_class = data[4]        # 1=32-bit 2=64-bit
    ei_data = data[5]         # 1=LE 2=BE
    end = "<" if ei_data == 1 else ">"
    is64 = ei_class == 2
    e_type, e_machine = struct.unpack(end + "HH", data[16:20])
    if is64:
        e_entry, e_phoff, e_shoff = struct.unpack(end + "QQQ", data[24:48])
    else:
        e_entry, e_phoff, e_shoff = struct.unpack(end + "III", data[24:36])
    cls = "64" if is64 else "32"
    return (f"ELF{cls} {'LE' if ei_data==1 else 'BE'} type={e_type} "
            f"machine={e_machine} entry=0x{e_entry:x} "
            f"phoff={e_phoff} shoff={e_shoff}")
