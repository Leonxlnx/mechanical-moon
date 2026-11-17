"""Engraving / window textures for the rings (numpy only).
  textures/ring_engrave.png  RGB: R = engraved (ticks, lines, runes), G = runes only, B = fine scratches
  textures/ring_windows.png  RGB: R = panel seams, G = lit window brightness, B = unused
Both tile along u (20 degrees of arc per tile); v runs across the face. Row 0 = bottom.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import common as K

rng = np.random.default_rng(3)
SS = 2


def down(a):
    h, w = a.shape
    return a.reshape(h // SS, SS, w // SS, SS).mean(axis=(1, 3))


def seg_mask(shape, x0, y0, x1, y1, th):
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy + 1e-9
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / L2, 0, 1)
    d = np.hypot(xx - (x0 + t * dx), yy - (y0 + t * dy))
    return np.clip(th - d + 0.5, 0, 1)


# ------------------------------------------------------------------ engraving tile: 20 degrees x face width
W, H = 4096 * SS, 512 * SS
eng = np.zeros((H, W), np.float32)
rune = np.zeros((H, W), np.float32)
px_deg = W / 20.0


def band(v0, v1):
    return int(v0 * H), int(v1 * H)


for v0, v1 in ((0.035, 0.055), (0.945, 0.965), (0.385, 0.398), (0.925, 0.935)):
    a, b = band(v0, v1)
    eng[a:b, :] = 1
# tick scale
for k in range(40):                      # every 0.5 degree
    x = int((k + 0.5) * 0.5 * px_deg) if False else int(k * 0.5 * px_deg + 0.25 * px_deg)
    deg2 = k                              # half degrees
    if deg2 % 20 == 0:
        ln, th = 0.46, 5
    elif deg2 % 10 == 0:
        ln, th = 0.36, 4
    elif deg2 % 2 == 0:
        ln, th = 0.24, 3
    else:
        ln, th = 0.14, 2
    a, b = band(0.92 - ln, 0.92)
    eng[a:b, max(0, x - th * SS):x + th * SS] = 1
# decade marks: small diamonds
for k in (0, 10):
    cx = int(k * px_deg + 0.25 * px_deg)
    cy = int(0.435 * H)
    yy, xx = np.mgrid[-40 * SS:40 * SS, -40 * SS:40 * SS]
    dm = (np.abs(xx) + np.abs(yy)) < 15 * SS
    ys, xs = np.nonzero(dm)
    eng[np.clip(cy + ys - 40 * SS, 0, H - 1), (cx + xs - 40 * SS) % W] = 1
# rune row: one glyph per degree
ra, rb = band(0.105, 0.335)
gh = rb - ra
gw = int(px_deg * 0.62)
for i in range(20):
    x0 = int(i * px_deg + (px_deg - gw) / 2 + 0.25 * px_deg)
    cols = [0.0, 0.5, 1.0]
    rows = [0.0, 0.33, 0.66, 1.0]
    nodes = [(c, r) for c in cols for r in rows]
    sub = np.zeros((gh, gw), np.float32)
    nseg = rng.integers(3, 6)
    cur = nodes[rng.integers(len(nodes))]
    for _ in range(nseg):
        cand = [n for n in nodes if n != cur and abs(n[0] - cur[0]) <= 0.5 and abs(n[1] - cur[1]) <= 0.67]
        nxt = cand[rng.integers(len(cand))]
        sub = np.maximum(sub, seg_mask((gh, gw), cur[0] * (gw - 1), cur[1] * (gh - 1), nxt[0] * (gw - 1), nxt[1] * (gh - 1), 5.0 * SS))
        cur = nxt if rng.random() < 0.75 else nodes[rng.integers(len(nodes))]
    if rng.random() < 0.3:                # dot accent
        yy, xx = np.mgrid[0:gh, 0:gw]
        sub = np.maximum(sub, (np.hypot(xx - gw * 0.5, yy - gh * 0.5) < 7 * SS).astype(np.float32))
    xs = (x0 + np.arange(gw)) % W
    eng[ra:rb, xs] = np.maximum(eng[ra:rb, xs], sub)
    rune[ra:rb, xs] = np.maximum(rune[ra:rb, xs], sub)
scr = (rng.random((H // (8 * SS), W // SS)) ** 6).astype(np.float32)          # fine horizontal scratches
scr = np.repeat(scr, 8, axis=0)
img = np.stack([down(eng), down(rune), scr[:H // SS, :]], -1)
K.write_png(K.P("textures", "ring_engrave.png"), np.round(np.clip(img, 0, 1) * 255).astype(np.uint8))

# ------------------------------------------------------------------ window tile
W, H = 4096 * SS, 256 * SS
seam = np.zeros((H, W), np.float32)
win = np.zeros((H, W), np.float32)
px_deg = W / 20.0
for v0, v1 in ((0.05, 0.075), (0.925, 0.95), (0.49, 0.51)):
    seam[int(v0 * H):int(v1 * H), :] = 1
for k in range(16):                       # panel seams every 1.25 degrees
    x = int(k * 1.25 * px_deg + 0.1 * px_deg)
    seam[int(0.075 * H):int(0.925 * H), x - 2 * SS:x + 2 * SS] = 1
for row, (v0, v1) in enumerate(((0.17, 0.40), (0.60, 0.83))):
    n = 80                                 # windows per 20 degrees
    for k in range(n):
        if rng.random() < 0.32:
            continue
        x0 = int((k + 0.22) * W / n)
        x1 = int((k + 0.78) * W / n)
        b = rng.uniform(0.35, 1.0)
        hh = rng.choice([1.0, 1.0, 0.55])
        a_ = int(v0 * H)
        b_ = int((v0 + (v1 - v0) * hh) * H)
        win[a_:b_, x0:x1] = b
img = np.stack([down(seam), down(win), np.zeros((H // SS, W // SS), np.float32)], -1)
K.write_png(K.P("textures", "ring_windows.png"), np.round(np.clip(img, 0, 1) * 255).astype(np.uint8))
# ------------------------------------------------------------------ v2 window tile: glazed panes with mullions, softer edges
rng2 = np.random.default_rng(8)
seam2 = seam.copy()
win2 = np.zeros((H, W), np.float32)
for row, (v0, v1) in enumerate(((0.16, 0.41), (0.59, 0.84))):
    n = 80
    for k in range(n):
        if rng2.random() < 0.30:
            continue
        x0 = int((k + 0.18) * W / n)
        x1 = int((k + 0.82) * W / n)
        b = rng2.uniform(0.30, 1.0)
        hh = rng2.choice([1.0, 1.0, 0.6])
        a_ = int(v0 * H)
        b_ = int((v0 + (v1 - v0) * hh) * H)
        yy, xx = np.mgrid[a_:b_, x0:x1]
        u = (xx - x0) / max(x1 - x0 - 1, 1)
        v = (yy - a_) / max(b_ - a_ - 1, 1)
        pane = b * (0.72 + 0.28 * np.sin(np.pi * v)) * (0.85 + 0.15 * np.sin(np.pi * u))
        for m_ in (1 / 3, 2 / 3):
            pane = np.where(np.abs(u - m_) < 0.045, 0.06 * b, pane)
        pane = np.where(np.abs(v - 0.5) < 0.05, 0.06 * b, pane)
        pane = np.where((u < 0.05) | (u > 0.95) | (v < 0.06) | (v > 0.94), 0.0, pane)
        win2[a_:b_, x0:x1] = pane
        seam2[max(a_ - 3 * SS, 0):a_, x0:x1] = 1
        seam2[b_:b_ + 3 * SS, x0:x1] = 1
img = np.stack([down(seam2), down(win2), np.zeros((H // SS, W // SS), np.float32)], -1)
K.write_png(K.P("textures", "ring_windows_v2.png"), np.round(np.clip(img, 0, 1) * 255).astype(np.uint8))
K.log("RING TEX DONE")
