import hashlib, json, os

BASE = r"E:\GTA6\GTA6.Xbox.v1.0.2.1-CYBERLEEK"
LIST = r"C:\Users\z7299\Documents\deepseek-harness\default-workspace\gta6\bad-pieces.json"
TORR = os.path.expandvars(r"%LOCALAPPDATA%\qBittorrent\BT_backup\465d6a0eac381e68ca77115f44f19f0c968b9590.torrent")


def bdecode(b):
    i = 0

    def dec():
        nonlocal i
        c = b[i:i + 1]
        if c == b"i":
            j = b.index(b"e", i); v = int(b[i + 1:j]); i = j + 1; return v
        if c == b"l":
            i += 1; out = []
            while b[i:i + 1] != b"e":
                out.append(dec())
            i += 1; return out
        if c == b"d":
            i += 1; out = {}
            while b[i:i + 1] != b"e":
                k = dec(); out[k] = dec()
            i += 1; return out
        j = b.index(b":", i); n = int(b[i:j]); s = b[j + 1:j + 1 + n]; i = j + 1 + n; return s

    return dec()


info = bdecode(open(TORR, "rb").read())[b"info"]
pl = info[b"piece length"]
hashes = info[b"pieces"]
name = info[b"name"].decode()
base = BASE if os.path.basename(BASE.rstrip("\\")) == name else os.path.join(os.path.dirname(BASE), name)
files = []
for f in info[b"files"]:
    files.append((os.path.join(base, *[p.decode() for p in f[b"path"]]), f[b"length"]))
offsets = []
o = 0
for p, n in files:
    offsets.append((o, o + n, p))
    o += n
total = o
bad = json.load(open(LIST))

def read_range(start, n):
    out = b""
    for lo, hi, path in offsets:
        if hi <= start or lo >= start + n:
            continue
        s = max(start, lo); e = min(start + n, hi)
        with open(path, "rb") as h:
            h.seek(s - lo)
            b = h.read(e - s)
        if len(b) != e - s:
            b += b"\x00" * (e - s - len(b))
        out += b
    return out

ok = 0
remaining = []
for e in bad:
    p = e["piece"] if isinstance(e, dict) else e
    need = min(pl, total - p * pl)
    data = read_range(p * pl, need)
    got = hashlib.sha1(data).digest()
    if got == hashes[p * 20:(p + 1) * 20]:
        ok += 1
    else:
        remaining.append(p)
print(json.dumps({"verified_ok": ok, "remaining_bad": len(remaining), "remaining": remaining}))
