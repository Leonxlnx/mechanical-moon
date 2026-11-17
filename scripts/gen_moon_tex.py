"""Generate the lunar surface maps (equirectangular, row 0 = south pole):
  textures/moon_height.npy   float32 (H,W) metres, all craters  -> real geometry displacement
  textures/moon_detail.png   16-bit grey, small craters only    -> shader bump
  textures/moon_albedo.png   8-bit RGB: R albedo, G maria mask, B fresh ejecta / rays
  textures/moon_meta.json
Run: blender -b -P gen_moon_tex.py   (only numpy is used)
"""
import sys, os, json, zlib, struct, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import common as K, config as C

W, H = 8192, 4096
R = C.R
rng = np.random.default_rng(7)
PI = np.pi
lon = ((np.arange(W) + 0.5) / W * 2 * PI - PI).astype(np.float32)
lat = ((np.arange(H) + 0.5) / H * PI - PI / 2).astype(np.float32)
sin_lat, cos_lat = np.sin(lat), np.cos(lat)


def dirs_grid(w, h):
    lo = (np.arange(w) + 0.5) / w * 2 * PI - PI
    la = (np.arange(h) + 0.5) / h * PI - PI / 2
    lo, la = np.meshgrid(lo, la)
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1).reshape(-1, 3)


def upsample(f):
    h, w = f.shape
    xs = (np.arange(W) + 0.5) / W * w - 0.5
    x0 = np.floor(xs).astype(np.int64)
    tx = (xs - x0).astype(np.float32)
    x1 = (x0 + 1) % w
    x0 = x0 % w
    ys = (np.arange(H) + 0.5) / H * h - 0.5
    y0f = np.floor(ys)
    ty = (ys - y0f).astype(np.float32)
    y0 = np.clip(y0f.astype(np.int64), 0, h - 1)
    y1 = np.clip(y0f.astype(np.int64) + 1, 0, h - 1)
    tmp = f[:, x0] * (1 - tx) + f[:, x1] * tx
    return (tmp[y0, :] * (1 - ty)[:, None] + tmp[y1, :] * ty[:, None]).astype(np.float32)


def field(func, w, h):
    return upsample(func(dirs_grid(w, h)).reshape(h, w).astype(np.float32))


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def write_png(path, arr):
    """arr: uint16 (H,W) grey or uint8 (H,W,3) RGB; row 0 = bottom (flipped on write)."""
    arr = arr[::-1]
    h, w = arr.shape[:2]
    if arr.dtype == np.uint16:
        ct, bd = 0, 16
        rows = arr.astype('>u2').view(np.uint8).reshape(h, w * 2)
    else:
        ct, bd = 2, 8
        rows = np.ascontiguousarray(arr).reshape(h, w * 3)
    raw = np.zeros((h, rows.shape[1] + 1), dtype=np.uint8)
    raw[:, 1:] = rows

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, bd, ct, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw.tobytes(), 5)))
        f.write(chunk(b"IEND", b""))


t0 = time.time()
K.log("low frequency fields")
maria_raw = field(lambda d: K.fbm3(d * 1.25, 4, seed=3) + 0.35 * K.fbm3(d * 3.1, 3, seed=5), 1024, 512)
maria = smoothstep(0.09, 0.22, maria_raw)
K.log("maria coverage %.2f" % float(maria.mean()))
hills = field(lambda d: 1.0 * K.fbm3(d * 2.2, 4, seed=21) + 0.40 * K.fbm3(d * 7.0, 4, seed=22), 2048, 1024)
mottle = field(lambda d: K.fbm3(d * 3.0, 4, seed=41) + 0.6 * K.fbm3(d * 11.0, 3, seed=42), 2048, 1024)

Hgt = (hills * (1 - 0.75 * maria) - 1.1 * maria).astype(np.float32)      # metres
Det = np.zeros((H, W), dtype=np.float32)                                   # small-crater detail, metres
Alb = (0.56 + 0.09 * mottle).astype(np.float32) * (1 - 0.50 * maria)
Fresh = np.zeros((H, W), dtype=np.float32)
del hills, mottle

# ------------------------------------------------------------ crater population (radius in metres on the R=100 sphere)
bins = [(6.0, 10.5, 6), (3.0, 6.0, 38), (1.5, 3.0, 270), (0.75, 1.5, 1900), (0.36, 0.75, 11000)]   # small craters only: the moon must read as enormous
craters = []
maria_lo = maria[::8, ::8]
for lo_r, hi_r, n in bins:
    cnt = 0
    while cnt < n:
        r = float(np.exp(rng.uniform(np.log(lo_r), np.log(hi_r))))
        z = rng.uniform(-1, 1)
        la0 = float(np.arcsin(z))
        lo0 = float(rng.uniform(-PI, PI))
        my = int((la0 + PI / 2) / PI * maria_lo.shape[0]) % maria_lo.shape[0]
        mx = int((lo0 + PI) / (2 * PI) * maria_lo.shape[1]) % maria_lo.shape[1]
        if maria_lo[my, mx] > 0.5 and r < 6.0 and rng.random() < 0.72:
            continue
        if r > 8.0:
            fresh = float(rng.uniform(0.25, 0.6))
        else:
            fresh = float(rng.random() ** 1.4)
        craters.append((r, lo0, la0, fresh))
        cnt += 1
craters.sort(key=lambda c: -c[0] * np.exp(0.35 * rng.standard_normal()))
K.log("craters:", len(craters))


def window(lon0, lat0, ext):
    y0 = max(0, int((lat0 - ext + PI / 2) / PI * H))
    y1 = min(H, int((lat0 + ext + PI / 2) / PI * H) + 2)
    maxabs = min(PI / 2, abs(lat0) + ext)
    c = np.cos(maxabs)
    if c < 0.03 or ext / c >= PI * 0.98:
        xs = slice(0, W)
    else:
        dl = ext / c
        x0 = int(np.floor((lon0 - dl + PI) / (2 * PI) * W))
        x1 = int(np.floor((lon0 + dl + PI) / (2 * PI) * W)) + 2
        if x0 >= 0 and x1 <= W:
            xs = slice(x0, x1)
        else:
            xs = np.arange(x0, x1) % W
    sl = sin_lat[y0:y1][:, None]
    cl = cos_lat[y0:y1][:, None]
    dlon = (lon[xs] - np.float32(lon0))[None, :]
    cosd = sl * np.float32(np.sin(lat0)) + cl * np.float32(np.cos(lat0)) * np.cos(dlon)
    ang = np.arccos(np.clip(cosd, -1, 1))
    return y0, y1, xs, ang, sl, cl, dlon


for ci, (r, lo0, la0, fresh) in enumerate(craters):
    a = r / R
    y0, y1, xs, ang, _, _, _ = window(lo0, la0, 2.6 * a)
    t = (ang / np.float32(a)).astype(np.float32)
    D = min(0.40 * r, 1.25 + 0.105 * r, 3.6) * (0.45 + 0.55 * fresh)
    Hr = 0.24 * D
    ff = float(np.clip((r - 5.0) / 14.0, 0, 0.62))                 # flat floor fraction for big craters
    ti = np.clip((t - ff) / (1 - ff), 0, 1)
    p = 2.2 if r < 6 else 1.7
    prof = np.where(t < 1.0, -D + (D + Hr) * ti ** p,
                    Hr * np.maximum(t, 1.0) ** -3.4 * (1 - smoothstep(1.7, 2.6, t)))
    if r > 9.0:
        prof = prof + 0.30 * D * np.exp(-(t / 0.13) ** 2)
    w_in = 1 - smoothstep(0.85, 1.25, t)
    old = Hgt[y0:y1, xs]
    wsum = float(w_in.sum())
    base = float((old * w_in).sum() / max(wsum, 1e-6))
    Hgt[y0:y1, xs] = old * (1 - w_in) + base * w_in + prof
    if r < 2.4:
        Det[y0:y1, xs] = Det[y0:y1, xs] * (1 - w_in) + prof
    # albedo
    rim = np.exp(-((t - 1.0) / 0.2) ** 2)
    ej = np.where(t > 1.0, np.maximum(t, 1.0) ** -2.6 * (1 - smoothstep(1.8, 2.6, t)), 0.0)
    da = -0.05 * np.clip(1 - t, 0, 1) + fresh * (0.10 * rim + 0.11 * ej)
    Alb[y0:y1, xs] = Alb[y0:y1, xs] + da
    fr = fresh * np.clip(0.8 * rim + 0.7 * ej, 0, 1)
    Fresh[y0:y1, xs] = np.maximum(Fresh[y0:y1, xs], fr)
    if ci % 4000 == 0:
        K.log("  crater", ci, "r=%.2f" % r)

# ------------------------------------------------------------ ray systems for some fresh mid-sized craters
cands = [c for c in craters if 2.2 < c[0] < 8.0 and c[3] > 0.55]
rng.shuffle(cands)
for (r, lo0, la0, fresh) in cands[:34]:
    a = r / R
    y0, y1, xs, ang, sl, cl, dlon = window(lo0, la0, 11.0 * a)
    t = (ang / np.float32(a)).astype(np.float32)
    # azimuth around the crater centre
    px = cl * np.sin(dlon)
    py = sl * np.float32(np.cos(la0)) - cl * np.float32(np.sin(la0)) * np.cos(dlon)
    th = np.arctan2(py, px)
    ray = np.zeros_like(t)
    for _ in range(int(rng.integers(9, 18))):
        ph = rng.uniform(-PI, PI)
        wd = rng.uniform(0.025, 0.09)
        st = rng.uniform(0.35, 1.0)
        ln = rng.uniform(4.0, 11.0)
        dth = np.angle(np.exp(1j * (th - ph))).astype(np.float32)
        lobe = np.exp(-(dth / wd) ** 2) * st * np.clip(1 - t / ln, 0, 1) ** 1.3
        ray = np.maximum(ray, lobe)
    ray = ray * smoothstep(0.9, 1.6, t)
    Alb[y0:y1, xs] = Alb[y0:y1, xs] + 0.16 * fresh * ray
    Fresh[y0:y1, xs] = np.maximum(Fresh[y0:y1, xs], 0.8 * fresh * ray)
K.log("stamping done %.1fs" % (time.time() - t0))

os.makedirs(K.P("textures"), exist_ok=True)
np.save(K.P("textures", "moon_height.npy"), Hgt)
dmin, dmax = float(Det.min()), float(Det.max())
det16 = np.round((Det - dmin) / (dmax - dmin) * 65535).astype(np.uint16)
write_png(K.P("textures", "moon_detail.png"), det16)
rgb = np.stack([np.clip(Alb, 0, 1), maria, np.clip(Fresh, 0, 1)], -1)
write_png(K.P("textures", "moon_albedo.png"), np.round(rgb * 255).astype(np.uint8))
meta = dict(W=W, H=H, hmin=float(Hgt.min()), hmax=float(Hgt.max()), det_min=dmin, det_max=dmax,
            alb_min=float(Alb.min()), alb_max=float(Alb.max()), ncraters=len(craters))
json.dump(meta, open(K.P("textures", "moon_meta.json"), "w"), indent=1)
K.log("META", meta)
# small preview
prev = np.round(np.clip(Alb[::8, ::8], 0, 1) * 255).astype(np.uint8)
write_png(K.P("textures", "moon_albedo_prev.png"), np.stack([prev] * 3, -1))
hp = Hgt[::8, ::8]
write_png(K.P("textures", "moon_height_prev.png"), np.stack([np.round((hp - hp.min()) / (hp.max() - hp.min()) * 255).astype(np.uint8)] * 3, -1))
K.log("TEX DONE %.1fs" % (time.time() - t0))
