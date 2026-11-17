"""Interior architecture of the hollow moon (moon-local space). Run headless:
blender -b --factory-startup -P build_arch.py      -> blend/arch.blend (collection ARCH)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np, math, time
from mathutils import Euler
import common as K, config as C, mats
import arch_lib as L
from arch_lib import (B, boxes, polar_boxes, lathe, sweep_bar, fill_strip, annulus, arch_half, circ, mir, add_sym,
                      compact, sph, cap_map, diamond, rotz, xf, pinnacle, gear, mesh_phase, pol, RI, TAU)

rng = np.random.default_rng(7)
T0 = time.time()
rad = math.radians
ROSE_AX = -np.asarray(C.OPEN_DIR, float)
ROSE_R = 26.0
LAT_G = 57.5                                   # galleries span +-LAT_G
RD = rad(90 - LAT_G) * RI                      # dome/bowl cap radius in arc metres (52.47)


def win_rnd(shape, dark=0.28):
    u = rng.random(shape)
    v = 0.22 + 0.65 * rng.random(shape) ** 1.5
    v = np.where(rng.random(shape) < 0.06, 0.75 + 0.25 * rng.random(shape), v)
    return np.where(u < dark, 0.04, v).astype(np.float32)


# ====================================================================== materials (module specific)
def _dome_enamel(name):
    m = bpy.data.materials.new(name)
    nt = mats.clear(m)
    N, Lk = mats.N, mats.L
    out = N(nt, "ShaderNodeOutputMaterial", (600, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (300, 0))
    tc = N(nt, "ShaderNodeTexCoord", (-900, 0))
    vor = N(nt, "ShaderNodeTexVoronoi", (-650, 0), inputs={"Scale": 0.55})
    Lk(nt, tc.outputs["Object"], vor.inputs["Vector"])
    dot = N(nt, "ShaderNodeMapRange", (-380, 0), inputs={"From Min": 0.035, "From Max": 0.09, "To Min": 1.0, "To Max": 0.0})
    Lk(nt, vor.outputs["Distance"], dot.inputs["Value"])
    noi = N(nt, "ShaderNodeTexNoise", (-650, 250), inputs={"Scale": 0.08, "Detail": 5.0})
    Lk(nt, tc.outputs["Object"], noi.inputs["Vector"])
    col = N(nt, "ShaderNodeMixRGB", (-120, 200))
    col.inputs["Color1"].default_value = (0.008, 0.022, 0.085, 1)
    col.inputs["Color2"].default_value = (0.03, 0.075, 0.26, 1)
    Lk(nt, noi.outputs["Fac"], col.inputs["Fac"])
    Lk(nt, col.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.35
    bsdf.inputs["Roughness"].default_value = 0.22
    em = N(nt, "ShaderNodeMixRGB", (-120, -150))
    em.inputs["Color1"].default_value = (0.012, 0.035, 0.16, 1)
    em.inputs["Color2"].default_value = (1.0, 0.8, 0.5, 1)
    Lk(nt, dot.outputs["Result"], em.inputs["Fac"])
    Lk(nt, em.outputs["Color"], bsdf.inputs["Emission Color"])
    es = N(nt, "ShaderNodeMapRange", (60, -300), inputs={"To Min": 0.5, "To Max": 14.0})
    Lk(nt, dot.outputs["Result"], es.inputs["Value"])
    Lk(nt, es.outputs["Result"], bsdf.inputs["Emission Strength"])
    Lk(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m


L._ARCH_MATS["ARCH_DomeEnamel"] = _dome_enamel
L._ARCH_MATS["ARCH_GlassBlue"] = lambda n: mats._emit(bpy.data.materials.new(n), (0.05, 0.20, 1.0), 7.0, attr="rnd", base=(0.005, 0.01, 0.03))
L._ARCH_MATS["ARCH_GlassAmber"] = lambda n: mats._emit(bpy.data.materials.new(n), (1.0, 0.38, 0.07), 7.0, attr="rnd", base=(0.03, 0.01, 0.002))
L._ARCH_MATS["ARCH_GlassRuby"] = lambda n: mats._emit(bpy.data.materials.new(n), (1.0, 0.10, 0.04), 8.0, attr="rnd", base=(0.03, 0.004, 0.002))


def tracery(b, a, ys, y0, wt0, wt1, n, circle, slot):
    a2 = a / 2
    ys_s = ys - 0.3
    sub = arch_half(a2, a2, n) + [0, ys_s]
    for x0 in (-a2, a2):
        v, f = sweep_bar(sub + [x0, 0], 0.16, wt0, wt1)
        b.add(v, f, 'Gold')
        v2, f2 = mir(*sweep_bar(sub, 0.16, wt0, wt1))
        v2[:, 0] += x0
        b.add(v2, f2, 'Gold')
    b.add(*boxes([-0.09, y0, wt0], [0.09, ys_s, wt1], 'xXZ'), 'Gold')
    if circle:
        rc = 0.36 * a
        yc = ys + 0.566 * a - 0.2 + rc
        b.add(*sweep_bar(circ(rc, 12, (0, yc)), 0.16, wt0, wt1, closed=True), 'Gold')
        Lp, Rp = disc_strip((0, yc), rc)
        b.add(*fill_strip(Lp, Rp, wt0 + 0.06), 'Window', slot)

# ====================================================================== gallery tiers
_e = [4.5, 9.5, 14.5, 19.5, 28.5, 33.5, 38.5, 43.5, 52.5, 57.5]
TIERS = [(-4.5, 4.5)] + [(_e[i], _e[i + 1]) for i in range(len(_e) - 1)] + [(-_e[i + 1], -_e[i]) for i in range(len(_e) - 1)]
TIERS.sort()
NRIB = 24


def lancet(b, xc, y0, hwid, hs, slot, wp=0.42, n=4):
    def prof(hw_, y0_, hs_):
        ah = arch_half(hw_, hw_ * 1.5, n)
        R = np.concatenate([[[hw_, y0_]], ah + [0, y0_ + hs_]])
        return R * [-1, 1] + [xc, 0], R + [xc, 0]
    Lp, Rp = prof(hwid, y0, hs)
    b.add(*fill_strip(Lp, Rp, wp), 'Window', slot)
    Lp, Rp = prof(hwid + 0.11, y0 - 0.11, hs + 0.11)
    b.add(*fill_strip(Lp, Rp, wp - 0.04), 'Gold')
    top = y0 + hs + hwid * 2.0
    b.add(*boxes([xc - 0.035, y0, wp], [xc + 0.035, top - 0.1, wp + 0.06], 'xXZ'), 'Gold')
    b.add(*boxes([xc - hwid, y0 + hs * 0.5 - 0.035, wp], [xc + hwid, y0 + hs * 0.5 + 0.035, wp + 0.06], 'yYZ'), 'Gold')


def disc_strip(c, r, n=3):
    t = np.linspace(-math.pi / 2, math.pi / 2, n + 2)[1:-1] if n <= 3 else np.linspace(-math.pi / 2, math.pi / 2, n + 1)
    if n <= 3:
        t = np.radians([-67.5, -22.5, 22.5, 67.5])
    Rp = np.c_[c[0] + r * np.cos(t), c[1] + r * np.sin(t)]
    Lp = np.c_[c[0] - r * np.cos(t), c[1] + r * np.sin(t)]
    return Lp, Rp


def oculus(b, xc, yc, r, slot, wp=0.42):
    for rr, w_, mat, sl in [(r, wp, 'Window', slot), (r + 0.11, wp - 0.04, 'Gold', 0)]:
        Lp, Rp = disc_strip((xc, yc), rr)
        b.add(*fill_strip(Lp, Rp, w_), mat, sl)


def bay_module(W, H, grand, style):
    b = B()
    hw = W / 2
    ts = 0.6 if grand else 0.45
    Da = 4.2 if grand else 3.4
    wf = Da - 0.3
    wb = wf - 0.7
    D = Da + (2.0 if grand else 0.0)      # balcony edge
    pw = 0.5 if grand else 0.38
    a = hw - pw
    cf = 1.7 if grand else (1.0, 0.45, 1.5)[style % 3]
    n = 8 if grand else 6
    ah = arch_half(a, a * cf, n)
    ys = H - (1.0 if grand else 0.75) - ah[-1, 1]
    # floor slab + cornice
    b.add(*boxes([-hw, 0, 0], [hw, ts, D], 'yY'), 'Bronze')
    c1, c2 = (0.35, 0.7) if grand else (0.25, 0.5)
    b.add(*boxes([-hw, 0, D], [hw, ts * 0.6, D + c1], 'yZ'), 'Gold')
    b.add(*boxes([-hw, ts * 0.6, D], [hw, ts + 0.08, D + c2], 'yYZ'), 'Gold')
    nd = 6
    xd = (np.arange(nd) + 0.5) / nd * W - hw
    od = np.ones(nd)
    b.add(*boxes(np.c_[xd - 0.13, od * (ts * 0.6 - 0.17), od * (D + c1)], np.c_[xd + 0.13, od * (ts * 0.6), od * (D + c2 - 0.07)], 'xXyZ'), 'Gold')
    yb = ts + 0.08
    rh = 1.05
    b.add(*boxes([-hw, yb + rh - 0.14, D + c2 - 0.38], [hw, yb + rh, D + c2 - 0.08], 'yYzZ'), 'Gold')
    nbal = 6
    xc = (np.arange(nbal) + 0.5) / nbal * W - hw
    o = np.ones(nbal)
    b.add(*boxes(np.c_[xc - 0.07, o * yb, o * (D + c2 - 0.30)], np.c_[xc + 0.07, o * (yb + rh - 0.14), o * (D + c2 - 0.16)], 'xXZ'), 'Brass')
    b.add(*boxes([-hw - 0.17, yb, D + c2 - 0.42], [-hw + 0.17, yb + rh + 0.25, D + c2 - 0.04], 'xXYZz'), 'Gold')
    ls = 0.15 if grand else 0.11
    b.add(*diamond((-hw, yb + rh + 0.25 + 0.3, D + c2 - 0.23), ls, 0.3, axis=1), 'Lamp')
    # arcade
    am = 'Brass'
    add_sym(b, *boxes([a, ts, wb], [hw, ys, wf], 'Zx'), am)
    add_sym(b, *boxes([a, ys, wb], [hw, H, wf], 'Z'), am)
    cur = ah[::-1] + [0, ys]
    m = len(cur)
    v = np.concatenate([np.c_[cur, np.full(m, wf)], np.c_[cur[:, 0], np.full(m, H), np.full(m, wf)], np.c_[cur, np.full(m, wb)]])
    i = np.arange(m - 1)
    f = np.concatenate([np.stack([i, i + 1, m + i + 1, m + i], -1), np.stack([i, 2 * m + i, 2 * m + i + 1, i + 1], -1)])
    add_sym(b, v, f, am)
    ah2 = arch_half(a + 0.17, a * cf, n) + [0, ys]
    add_sym(b, *sweep_bar(ah2, 0.3, wf, wf + 0.14), 'Gold')
    add_sym(b, *boxes([a - 0.12, ys - 0.4, wb - 0.05], [hw, ys, wf + 0.22], 'xyYZ'), 'Gold')
    add_sym(b, *boxes([a - 0.1, ts, wb], [hw, ts + 0.45, wf + 0.18], 'xYZ'), 'Gold')
    px = np.array([hw - 0.22, hw - 0.14, hw])
    pz = np.array([wf, wf + 0.2, wf + 0.28])
    v = np.concatenate([np.c_[px, np.full(3, ts + 0.45), pz], np.c_[px, np.full(3, H), pz]])
    add_sym(b, v, np.array([[0, 1, 4, 3], [1, 2, 5, 4]]), 'Gold')
    lw = wf + (0.6 if grand else 0.3)
    b.add(*diamond((-hw, ys + 0.35, lw + ls), ls, 0.32, axis=1), 'Lamp')
    b.add(*boxes([-hw - 0.04, ys + 0.3, lw - 0.3], [-hw + 0.04, ys + 0.4, lw + ls], 'xXyY'), 'Gold')
    glazed = grand or (style % 3 != 1)
    if glazed:
        wg = wb - 0.25
        y0 = ts + 0.45
        prof = np.concatenate([[[a, y0]], [[a, ys]], ah[1:] + [0, ys]])
        cen = np.c_[np.zeros(len(prof)), prof[:, 1]]
        b.add(*fill_strip(prof * [-1, 1], cen, wg), 'Window', 1)
        b.add(*fill_strip(cen, prof, wg), 'Window', 2)
        b.add(*boxes([-a, ts, wg - 0.1], [a, y0, wb], 'YZ'), 'Bronze')
        tracery(b, a, ys, y0, wg + 0.02, wb + 0.1, 5 if grand else 3, grand, 3)
        hts = (0.33, 0.66) if grand else (0.5,)
        for h_ in hts:
            yy_ = y0 + (ys - 0.3 - y0) * h_
            b.add(*boxes([-a, yy_ - 0.05, wg], [a, yy_ + 0.05, wg + 0.2], 'yYZ'), 'Gold')
        nbar = max(2, int((ys - 0.3 - y0) / 0.95))
        yb_ = y0 + np.arange(1, nbar) * (ys - 0.3 - y0) / nbar
        o_ = np.ones(len(yb_))
        b.add(*boxes(np.c_[-a * o_, yb_ - 0.025, o_ * (wg + 0.01)], np.c_[a * o_, yb_ + 0.025, o_ * (wg + 0.04)], 'Z'), 'DarkMetal')
        for xv in (-a / 2, a / 2):
            b.add(*boxes([xv - 0.025, y0, wg + 0.01], [xv + 0.025, ys - 0.3, wg + 0.04], 'Z'), 'DarkMetal')
        nslots = 3
    else:
        b.add(*boxes([-hw, ts, 0], [hw, H, 0.35], 'Z'), 'Bronze')
        sH = (H - ts) / 7.62
        lancet(b, -W * 0.24, ts + 1.2 * sH, 0.6, 3.0 * sH, 1)
        lancet(b, W * 0.24, ts + 1.2 * sH, 0.6, 3.0 * sH, 2)
        oculus(b, 0, ts + 6.3 * sH, 0.6, 3)
        nslots = 3
    if grand:
        # corbel under the projecting balcony + buttress + pinnacle on the pier
        b.add(*boxes([-hw - 0.22, -1.3, Da - 0.2], [-hw + 0.22, 0, D - 0.5], 'xXyZ'), 'Gold')
        b.add(*boxes([-hw - 0.32, ts + 0.45, wf], [-hw + 0.32, ys + 0.9, wf + 0.6], 'xXYZ'), 'Brass')
        b.add(*boxes([-hw - 0.2, ys + 0.9, wf + 0.1], [-hw + 0.2, ys + 2.0, wf + 0.5], 'xXYZ'), 'Gold')
        b.add(*boxes([-hw - 0.1, ys + 2.0, wf + 0.2], [-hw + 0.1, ys + 3.0, wf + 0.4], 'xXYZ'), 'Gold')
    return b, dict(ts=ts, D=D, wf=wf, wb=wb, ys=ys, nslots=nslots)


def edge_module(W, H, dm):
    """Section wall + broken stubs for a bay whose +x neighbour is missing."""
    b = B()
    hw = W / 2
    ts, D, ys = dm['ts'], dm['D'], dm['ys']
    b.add(*boxes([hw - 0.3, 0, -1.5], [hw, H, D + 0.45], 'xXZ'), 'Bronze')
    w0_, w1_, y0_, y1_ = 0.5, D - 0.7, ts + 0.4, H - 0.6
    nx = max(1, int((w1_ - w0_) / 1.4))
    ny = max(1, int((y1_ - y0_) / 2.6))
    cw, ch = (w1_ - w0_) / nx, (y1_ - y0_) / ny
    I_, J_ = [q.ravel() for q in np.meshgrid(np.arange(nx), np.arange(ny), indexing='ij')]
    oo = np.ones(len(I_))
    b.add(*boxes(np.c_[oo * hw, y0_ + J_ * ch + 0.25, w0_ + I_ * cw + 0.15], np.c_[oo * (hw + 0.04), y0_ + (J_ + 1) * ch - 0.25, w0_ + (I_ + 1) * cw - 0.15], 'X'),
          'Window', np.repeat(win_rnd(len(I_), 0.4), 8))
    for j in range(ny + 1):
        b.add(*boxes([hw, y0_ + j * ch - 0.12, -1.4], [hw + 0.3, y0_ + j * ch + 0.12, D + 0.3], 'XyYzZ'), 'Gold')
    nc = max(2, int(H / 1.7))
    yy = (np.arange(nc) + 0.25) * H / nc
    o = np.ones(nc)
    b.add(*boxes(np.c_[o * hw, yy, o * -1.25], np.c_[o * (hw + 0.04), yy + H / nc * 0.5, o * -0.25], 'X'), 'Window',
          np.repeat(win_rnd(nc, 0.3), 8))
    l = rng.uniform(0.6, 3.0)
    b.add(*boxes([hw, 0, -1.5], [hw + l, ts, D], 'XyYzZ'), 'Bronze')
    b.add(*boxes([hw, 0, D], [hw + l * 0.8, ts + 0.08, D + 0.5], 'XyYzZ'), 'Gold')
    for j in range(4):
        y = rng.uniform(ts + 0.5, H - 0.6)
        w0 = rng.uniform(-1.3, D - 0.5)
        l = rng.uniform(0.5, 3.4)
        b.add(*boxes([hw, y, w0], [hw + l, y + 0.4, w0 + 0.4], 'XyYzZ'), ['Gold', 'DarkMetal', 'Brass'][int(rng.integers(3))])
    l = rng.uniform(0.3, 2.2)
    b.add(*boxes([hw, ts, -1.5], [hw + l, H * rng.uniform(0.3, 0.9), 0], 'XYzZ'), 'Bronze')
    return b


def cap_module(W, H, dm, up):
    b = B()
    hw = W / 2
    D = dm['D']
    if up:
        b.add(*boxes([-hw, H, -1.5], [hw, H + 0.5, D + 0.3], 'xXYzZ'), 'Bronze')
        b.add(*boxes([-hw, H + 0.5, -1.5], [hw, H + 0.5 + rng.uniform(0.4, 3.2), 0.0], 'xXYzZ'), 'Bronze')
        for sx in (-1, 1):
            if rng.random() < 0.7:
                b.add(*boxes([sx * hw - 0.4, H + 0.5, dm['wb']], [sx * hw + 0.4, H + 0.5 + rng.uniform(0.5, 3.8), dm['wf']], 'xXYzZ'), 'Brass')
        if rng.random() < 0.5:
            x = rng.uniform(-hw * 0.6, hw * 0.6)
            b.add(*boxes([x - 0.2, H + 0.5, 0.8], [x + 0.2, H + 0.5 + rng.uniform(0.5, 2.5), 1.2], 'xXYzZ'), 'Gold')
    else:
        b.add(*boxes([-hw, -0.5, -1.5], [hw, 0, D + 0.3], 'xXyzZ'), 'Bronze')
        b.add(*boxes([-hw, -0.5 - rng.uniform(0.4, 3.2), -1.5], [hw, -0.5, 0.0], 'xXyzZ'), 'Bronze')
        for sx in (-1, 1):
            if rng.random() < 0.7:
                b.add(*boxes([sx * hw - 0.3, -0.5 - rng.uniform(0.5, 3.5), 1.0], [sx * hw + 0.3, -0.5, 1.6], 'xXyzZ'), 'Gold')
    return b


def hull_strip(HB, la0, la1, nb, keep):
    nl = max(1, int(np.ceil((la1 - la0) / 2.5)))
    lons = np.arange(nb + 1) * TAU / nb
    lats = np.radians(np.linspace(la0, la1, nl + 1))
    LO, LA = np.meshgrid(lons, lats, indexing='ij')
    i = np.where(keep)[0]
    m = nl + 1
    I, J = np.meshgrid(i, np.arange(nl), indexing='ij')
    F = np.stack([I * m + J, (I + 1) * m + J, (I + 1) * m + J + 1, I * m + J + 1], -1).reshape(-1, 4)
    if not len(F):
        return
    HB.add(*compact(sph(LO, LA, C.HULL_R).reshape(-1, 3), F), 'HullSkin')
    HB.add(*compact(sph(LO, LA, RI).reshape(-1, 3), F[:, ::-1]), 'Bronze')


def hull_cap(HB, la0, la1, nb=96, nl=13):
    lons = np.arange(nb + 1) * TAU / nb
    lats = np.radians(np.linspace(la0, la1, nl + 1))
    LO, LA = np.meshgrid(lons, lats, indexing='ij')
    lc, ac = np.meshgrid((lons[:-1] + lons[1:]) / 2, (lats[:-1] + lats[1:]) / 2, indexing='ij')
    keep = (C.open_field(sph(lc.ravel(), ac.ravel(), 1.0)) >= C.HULL_OPEN_F).reshape(nb, nl)
    m = nl + 1
    I, J = np.where(keep)
    F = np.stack([I * m + J, (I + 1) * m + J, (I + 1) * m + J + 1, I * m + J + 1], -1).reshape(-1, 4)
    HB.add(*compact(sph(LO, LA, C.HULL_R).reshape(-1, 3), F), 'HullSkin')
    HB.add(*compact(sph(LO, LA, RI).reshape(-1, 3), F[:, ::-1]), 'Bronze')
    c0, c1 = [], []
    for i, j in zip(I, J):
        l0, l1, a0, a1 = lons[i], lons[i + 1], lats[j], lats[j + 1]
        dl = 0.45 / (RI * max(0.05, math.cos((a0 + a1) / 2)))
        da = 0.45 / RI
        if not keep[(i + 1) % nb, j]:
            c0.append((l1 - dl, a0, -1.5)); c1.append((l1, a1, rng.uniform(1.0, 3.0)))
        if not keep[(i - 1) % nb, j]:
            c0.append((l0, a0, -1.5)); c1.append((l0 + dl, a1, rng.uniform(1.0, 3.0)))
        if j + 1 < nl and not keep[i, j + 1]:
            c0.append((l0, a1 - da, -1.5)); c1.append((l1, a1, rng.uniform(1.0, 3.0)))
        if j > 0 and not keep[i, j - 1]:
            c0.append((l0, a0, -1.5)); c1.append((l1, a0 + da, rng.uniform(1.0, 3.0)))
    if c0:
        eb = B()
        eb.add(*boxes(np.array(c0), np.array(c1)), 'Bronze')
        HB.merge(eb, fn=lambda V: sph(V[:, 0], V[:, 1], RI - V[:, 2]))
    K.log("hull cap", la0, la1, "cells cut", int((~keep).sum()), "edge walls", len(c0))


def build_galleries(G, HB):
    info = []
    for t, (la0, la1) in enumerate(TIERS):
        latm = rad((la0 + la1) / 2)
        nb = max(24, 24 * int(round(144 * math.cos(latm) / 24)))
        dlon = TAU / nb
        lonc = (np.arange(nb) + 0.5) * dlon
        f = C.open_field(sph(lonc, latm + 0 * lonc, 1.0))
        keep_h = f >= C.HULL_OPEN_F
        # rose test on corners + centre
        dmin = np.full(nb, 1e9)
        for lo_ in (-0.5, 0, 0.5):
            for la_ in (la0, (la0 + la1) / 2, la1):
                d = sph(lonc + lo_ * dlon, rad(la_) + 0 * lonc, 1.0)
                dmin = np.minimum(dmin, np.arccos(np.clip(d @ ROSE_AX, -1, 1)) * RI)
        info.append(dict(la0=la0, la1=la1, nb=nb, dlon=dlon, lonc=lonc, keep_h=keep_h, keep=keep_h & (dmin > ROSE_R + 0.3)))
    nbays = 0
    for t, ti in enumerate(info):
        la0, la1, nb, dlon, lonc = ti['la0'], ti['la1'], ti['nb'], ti['dlon'], ti['lonc']
        grand = (la1 - la0) > 6
        latm = rad((la0 + la1) / 2)
        W = RI * math.cos(latm) * dlon
        H = RI * rad(la1 - la0)
        mod, dm = bay_module(W, H, grand, t)
        V, F, M, S = mod.arrays()
        V = V.astype(np.float64)

        def tmap(P, lon0, W=W, H=H, la0=la0, la1=la1, dlon=dlon):
            P = np.asarray(P, float)
            return sph(lon0 + P[..., 0] / W * dlon, rad(la0) + P[..., 1] / H * rad(la1 - la0), RI - P[..., 2])
        idx = np.where(ti['keep'])[0]
        nbays += len(idx)
        P = tmap(V[None], lonc[idx][:, None])
        rv = win_rnd((len(idx), dm['nslots'] + 1))
        rv[:, 0] = 0
        Si = S.astype(int)
        tg = np.zeros(len(V))
        for sl in range(1, dm['nslots'] + 1):          # vertical brightness gradient inside every pane
            msk = Si == sl
            if msk.any():
                yy_ = V[msk, 1]
                tg[msk] = (yy_ - yy_.min()) / max(1e-6, yy_.max() - yy_.min())
        up_ = rng.random((len(idx), 1)) < 0.5
        grad = 0.5 + 0.8 * np.where(up_, tg[None], 1 - tg[None])
        G.merge_instances(mod, P, flip=True, Rinst=np.minimum(1.0, rv[:, Si] * grad))
        hull_strip(HB, la0, la1, nb, ti['keep_h'])
        # cut edges
        kh = ti['keep_h']
        for i in np.where(kh)[0]:
            for side in (1, -1):
                if not kh[(i + side) % nb]:
                    em = edge_module(W, H, dm)
                    HB.merge(em, fn=lambda Q, s=side, l0=lonc[i]: tmap(Q * [s, 1, 1], l0))
            for up in (True, False):
                tn = t + (1 if up else -1)
                if 0 <= tn < len(info):
                    o = info[tn]
                    j = int(lonc[i] / o['dlon']) % o['nb']
                    if not o['keep_h'][j]:
                        cm = cap_module(W, H, dm, up)
                        HB.merge(cm, fn=lambda Q, l0=lonc[i]: tmap(Q, l0))
        ti['dm'] = dm
    K.log("bays", nbays, "gallery tris", G.tris())
    # polar caps of the hull (cut per cell where the opening reaches them)
    for la0, la1 in ((LAT_G, 90.0), (-90.0, -LAT_G)):
        hull_cap(HB, la0, la1)
    return info


def rib_fn(lon0):
    return lambda V: sph(lon0 + V[:, 0] / (RI * np.cos(V[:, 1] / RI)), V[:, 1] / RI, RI - V[:, 2])


def build_ribs(G, info):
    lat_d = np.arange(-LAT_G, LAT_G + 1e-6, 2.5)
    lat_s = np.radians(lat_d)
    y = lat_s * RI
    bounds = sorted(set([ti['la0'] for ti in info] + [ti['la1'] for ti in info]))
    grand_base = set(ti['la0'] for ti in info if ti['la1'] - ti['la0'] > 6)
    col = B()
    col.add(*boxes([-1.95, -0.5, 0], [1.95, 0.5, 6.4], 'xXyYZ'), 'Gold')
    col.add(*boxes([-0.8, -0.8, 6.4], [0.8, 0.8, 7.0], 'xXyYZ'), 'Brass')
    col.merge(pinnacle(3.0, 0.5), fn=xf(t=(0, 0, 7.0)))
    gb = B()
    gb.add(*boxes([-1.0, 0.5, 5.6], [1.0, 1.5, 8.5], 'xXYZ'), 'Brass')
    gb.merge(pinnacle(6.5, 0.72), fn=lambda V: np.c_[V[:, 0], V[:, 2] + 1.5, 7.45 + V[:, 1]])
    side = B()
    lancet(side, 0, 0, 0.75, 3.0, 1, wp=0.08)
    band = B()
    band.add(*boxes([-1.22, -0.13, 3.0], [1.22, 0.13, 5.72], 'xXyYZ'), 'Gold')
    band.add(*boxes([-0.68, -0.2, 5.6], [0.68, 0.2, 7.35], 'xXyYZ'), 'Brass')
    sV, sF, sM, sR = side.arrays()
    s_t = (sV[:, 1] - sV[:, 1].min()) / (sV[:, 1].max() - sV[:, 1].min())
    tiers = [(ti['la0'], ti['la1']) for ti in info]
    bal = B()   # projecting semicircular balcony (lathe about local y at w=5.2)
    v, f = lathe([(0.3, -2.4), (1.3, -1.7), (3.2, -0.8), (4.7, -0.3), (4.7, 0.0), (0.02, 0.0)], 14, a0=0, a1=math.pi)
    bal.add(v, f, 'Brass')
    v, f = lathe([(4.45, 0), (4.7, 0), (4.7, 1.1), (4.45, 1.1)], 14, closed=True, a0=0, a1=math.pi)
    bal.add(v, f, 'Gold')
    for a_ in np.linspace(0.15, math.pi - 0.15, 5):
        bal.add(*boxes([4.57 * math.cos(a_) - 0.2, 4.57 * math.sin(a_) - 0.2, 1.1], [4.57 * math.cos(a_) + 0.2, 4.57 * math.sin(a_) + 0.2, 1.6], 'xXyYZ'), 'Lamp')
    for k in range(NRIB):
        lon0 = k * TAU / NRIB
        d = sph(lon0 + 0 * lat_s, lat_s, 1.0)
        ok = (C.open_field(d) >= C.HULL_OPEN_F) & (np.arccos(np.clip(d @ ROSE_AX, -1, 1)) * RI > 28.5)
        b = B()
        i = 0
        n = len(y)
        while i < n:
            if not ok[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and ok[j + 1]:
                j += 1
            if j > i:
                pts = np.c_[np.zeros(j - i + 1), y[i:j + 1]]
                for wd, z0, z1, mat in [(3.2, 0, 3.0, 'Bronze'), (2.2, 3.0, 5.6, 'Brass'), (1.1, 5.6, 7.2, 'Gold')] + ([(0.5, 7.2, 8.4, 'Gold')] if k % 2 == 0 else []):
                    b.add(*sweep_bar(pts, wd, z0, z1, faces='TLRE'), mat)
            i = j + 1
        fn = rib_fn(lon0)
        G.merge(b, fn)
        for la in bounds:
            dd = sph(np.array([lon0]), np.array([rad(la)]), 1.0)
            if C.open_field(dd)[0] < C.HULL_OPEN_F + 0.02 or math.acos(np.clip(dd[0] @ ROSE_AX, -1, 1)) * RI < 30:
                continue
            yy = rad(la) * RI
            G.merge(col, fn=lambda V, yy=yy: fn(V + [0, yy, 0]))
            for (ta, tb) in tiers:
                if ta != la:
                    continue
                Ht = rad(tb - ta) * RI
                for yb_ in ((Ht * 0.25, Ht * 0.5, Ht * 0.75) if tb - ta > 6 else (Ht * 0.66,)):
                    G.merge(band, fn=lambda V, yy=yy + yb_: fn(V + [0, yy, 0]))
                for yo in ((1.2, 8.4) if tb - ta > 6 else (0.9,)):
                    for sx in (-1, 1):
                        rr_ = float(win_rnd(1, 0.2)[0])
                        G.merge(side, fn=lambda V, yy=yy + yo, sx=sx: fn(np.c_[sx * (1.1 + V[:, 2]), V[:, 1] + yy, 4.3 + V[:, 0]]),
                                rnd=np.where(sR > 0, min(1.0, rr_) * (0.55 + 0.6 * s_t), 0))
            if la in grand_base:
                G.merge(gb, fn=lambda V, yy=yy: fn(V + [0, yy, 0]))
                if (k + int(la > 0)) % 2 == 0 and abs(la) < 40:
                    G.merge(bal, fn=lambda V, yy=yy: fn(np.c_[V[:, 0], V[:, 2] + yy + 0.6, 7.6 + V[:, 1]]))


def build_bridges(G):
    nbr = 0
    for li, la in enumerate((9.5, -14.5, 33.5, -38.5, 19.5, -28.5)):
        for k in range(NRIB):
            if (k * 5 + li * 3) % 6 != 0:
                continue
            lon0 = k * TAU / NRIB
            dd = sph(lon0 + np.array([0, 0.5, 1.0]) * TAU / NRIB, np.full(3, rad(la)), 1.0)
            if (C.open_field(dd) < C.HULL_OPEN_F + 0.03).any() or (np.arccos(np.clip(dd @ ROSE_AX, -1, 1)) * RI < 31).any():
                continue
            X = TAU / NRIB * RI * math.cos(rad(la))
            sgrid = np.linspace(0, 1, 13)
            px = 0.5 + (X - 1.0) * sgrid
            pq = 7.0 + 1.6 * np.sin(sgrid * math.pi)
            b = B()
            b.add(*sweep_bar(np.c_[px, pq], 1.9, -0.3, 0.0, faces='TLRB'), 'Brass')
            for off in (-0.9, 0.9):
                b.add(*sweep_bar(np.c_[px, pq + off], 0.14, 0.0, 1.0, faces='TLR'), 'Gold')
                b.add(*sweep_bar(np.c_[px, pq + off], 0.3, -0.5, -0.3, faces='TLRB'), 'Gold')
            for i in range(1, 12, 2):
                for off in (-0.9, 0.9):
                    b.add(*diamond((px[i], pq[i] + off, 1.3), 0.13, 0.3), 'Lamp')
            # arch ribs under the deck
            b.add(*sweep_bar(np.c_[px, pq], 0.5, -0.3 - 1.8 * np.abs(2 * sgrid - 1) ** 2, -0.3, faces='LR'), 'Gold')
            yy = rad(la) * RI + 0.6
            fn = rib_fn(lon0)
            G.merge(b, fn=lambda V, yy=yy: fn(np.c_[V[:, 0], V[:, 2] + yy, V[:, 1]]))
            nbr += 1
    K.log("bridges", nbr)


# ====================================================================== rose window
def rose_frame():
    e1 = np.cross([0, 0, 1.0], ROSE_AX)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(ROSE_AX, e1)
    return np.stack([e1, e2, ROSE_AX], 1)


def to_pol(Pxy, thc, rho_s):
    rho = rho_s + Pxy[:, 1]
    th = thc - Pxy[:, 0] / rho_s
    return np.c_[rho * np.cos(th), rho * np.sin(th)]


def lathe_at(b, prof, nseg, cx, cy, mat):
    v, f = lathe(prof, nseg)
    b.add(v + [cx, cy, 0], f, mat)


def build_rose():
    Rb = B()
    # backing + enamel
    Rb.add(*annulus(0.5, 38.0, 120, 0.2, nr=6), 'Bronze')
    Rb.add(*annulus(2.6, 22.6, 96, 0.9, nr=4), 'Enamel')
    WP = 1.0
    # petals ring A / B
    for npet, rin, rs, cf, z1, bright in ((12, 2.9, 5.2, 1.0, 2.0, (0.45, 0.62)), (24, 8.7, 12.3, 1.0, 1.9, (0.3, 0.45))):
        a = math.pi / npet * rs * 0.9
        ah = arch_half(a, a * cf, 6)
        prof = np.concatenate([[[a, rin - rs]], ah])
        full = np.concatenate([prof[::-1] * [-1, 1], prof[1:]]) if False else np.concatenate([(prof * [-1, 1]), prof[::-1][1:]])
        for i in range(npet):
            thc = (i + 0.5) * TAU / npet
            Lp = to_pol(prof * [-1, 1], thc, rs)
            Rp = to_pol(prof, thc, rs)
            blue = (npet == 24 and i % 2 == 0)
            Rb.add(*fill_strip(Lp, Rp, WP), 'ARCH_GlassBlue' if blue else ('ARCH_GlassAmber' if npet == 24 else 'Window'), rng.uniform(0.3, 0.52) if (blue or npet == 24) else rng.uniform(*bright))
            Rb.add(*sweep_bar(to_pol(full, thc, rs), 0.22, WP, z1 - 0.15), 'Gold')
        th = np.arange(npet) * TAU / npet
        for t_ in th:   # radial mullions
            rr = np.linspace(rin - 0.4, rs + 3.9, 6)
            Rb.add(*sweep_bar(np.c_[rr * math.cos(t_), rr * math.sin(t_)], 0.3, 0.9, z1), 'Gold')
    # trefoil roundels at the top of ring B mullions
    for i in range(24):
        t_ = i * TAU / 24
        c = (15.5 * math.cos(t_), 15.5 * math.sin(t_))
        Rb.add(*fill_strip(*disc_strip(c, 0.55), 1.95), 'ARCH_GlassRuby', 0.55)
        Rb.add(*sweep_bar(circ(0.62, 10, c), 0.16, 0.9, 2.05, closed=True), 'Gold')
    # ring C: 24 big circles with quatrefoils
    for i in range(24):
        t_ = (i + 0.5) * TAU / 24
        c = np.array([19.4 * math.cos(t_), 19.4 * math.sin(t_)])
        Rb.add(*fill_strip(*disc_strip(c, 2.3, 8), WP), 'ARCH_GlassBlue', rng.uniform(0.28, 0.45))
        Rb.add(*sweep_bar(circ(2.38, 20, c), 0.3, 0.9, 2.1, closed=True), 'Gold')
        for q in range(4):
            a_ = t_ + math.pi / 4 + q * math.pi / 2
            cq = c + 1.2 * np.array([math.cos(a_), math.sin(a_)])
            Rb.add(*sweep_bar(circ(0.95, 10, cq), 0.14, WP, 1.7, closed=True), 'Gold')
            Rb.add(*fill_strip(*disc_strip(cq, 0.9), WP + 0.05), 'ARCH_GlassAmber' if q % 2 else 'Window', rng.uniform(0.3, 0.48))
        Rb.add(*boxes([c[0] - 0.22, c[1] - 0.22, WP], [c[0] + 0.22, c[1] + 0.22, 2.0], 'xXyYZ'), 'Gold')
    # tracery rings
    for rc, wd, z1 in ((2.75, 0.5, 2.3), (8.3, 0.6, 2.4), (16.4, 0.7, 2.6), (22.3, 0.9, 3.0)):
        Rb.add(*sweep_bar(circ(rc, 120), wd, 0.9, z1, closed=True), 'Gold')
    # graduated ring
    Rb.add(*sweep_bar(circ(24.0, 144), 2.5, 0.2, 1.6, closed=True), 'Brass')
    th = np.arange(360) * TAU / 360
    ln = np.where(np.arange(360) % 15 == 0, 1.5, np.where(np.arange(360) % 5 == 0, 1.0, 0.55))
    Rb.add(*polar_boxes(25.1 - ln, 25.1, th, 0.0022, 1.6, 1.75, 'xXyYZ'), 'Gold')
    th = (np.arange(24) + 0.5) * TAU / 24
    Rb.add(*polar_boxes(23.0, 23.26, th, 0.0055, 1.6, 1.9, 'xXyYZ'), 'Lamp')
    # heavy frame
    for rc, wd, z1, mat in ((26.0, 1.7, 4.2, 'Gold'), (27.5, 1.5, 5.6, 'Brass'), (28.7, 1.1, 4.0, 'Gold'), (29.6, 0.9, 2.4, 'Bronze')):
        Rb.add(*sweep_bar(circ(rc, 144), wd, 0.2, z1, closed=True), mat)
    th = np.arange(48) * TAU / 48
    Rb.add(*polar_boxes(27.33, 27.67, th, 0.006, 5.6, 5.95, 'xXyYZ'), 'Lamp')
    th = (np.arange(48) + 0.5) * TAU / 48
    Rb.add(*polar_boxes(26.9, 28.1, th, 0.02, 5.6, 5.85, 'xXyYZ'), 'Gold')
    # sunburst on the surround
    for i in range(96):
        t_ = i * TAU / 96
        rr = np.linspace(30.1, 36.5 if i % 2 == 0 else 33.5, 4)
        Rb.add(*sweep_bar(np.c_[rr * math.cos(t_), rr * math.sin(t_)], np.linspace(0.45, 0.08, 4), 0.2, 0.34), 'Gold')
    # centre boss
    v, f = lathe([(2.9, 0.9), (2.9, 2.6), (2.2, 3.0), (1.6, 3.0), (1.2, 3.6), (0.95, 3.7)], 32)
    Rb.add(v, f, 'Gold')
    v, f = lathe([(0.95, 3.7), (0.7, 4.3), (0.02, 4.55)], 16)
    Rb.add(v, f, 'Lamp')
    # dials
    Do = B()
    Do.add(*sweep_bar(circ(23.95, 144), 1.7, 1.9, 2.3, closed=True, faces='TLRB'), 'Silver')
    th = np.arange(12) * TAU / 12
    Do.add(*polar_boxes(23.3, 24.6, th, 0.012, 2.3, 2.6, 'xXyYZ'), 'Gold')
    th = (np.arange(60) + 0.5) * TAU / 60
    Do.add(*polar_boxes(23.6, 24.3, th, 0.004, 2.3, 2.42, 'xXyYZ'), 'Gold')
    lathe_at(Do, [(1.5, 2.3), (1.5, 2.75), (0.95, 3.05)], 24, 23.95 * math.cos(0.13), 23.95 * math.sin(0.13), 'Gold')
    lathe_at(Do, [(0.95, 3.05), (0.6, 3.3), (0.02, 3.4)], 16, 23.95 * math.cos(0.13), 23.95 * math.sin(0.13), 'Lamp')
    lathe_at(Do, [(1.2, 2.3), (1.2, 2.7), (0.7, 3.0), (0.02, 3.1)], 20, 23.95 * math.cos(3.4), 23.95 * math.sin(3.4), 'Silver')
    Di = B()
    Di.add(*sweep_bar(circ(8.3, 96), 0.5, 2.45, 2.8, closed=True, faces='TLRB'), 'Gold')
    Di.add(*sweep_bar(circ(3.25, 48), 0.6, 2.62, 3.2, closed=True, faces='TLRB'), 'Brass')
    for ang, r1, w0, mat, orb, om in ((0.6, 21.0, 0.8, 'Gold', 19.3, 'Lamp'), (0.6 + 2.5, 14.6, 0.6, 'Silver', 13.2, 'Silver'), (0.6 + math.pi, 6.5, 0.9, 'Gold', 0, None), (2.5 + 0.6 + math.pi, 5.5, 0.8, 'Silver', 0, None)):
        rr = np.linspace(3.4, r1, 8)
        Di.add(*sweep_bar(np.c_[rr * math.cos(ang), rr * math.sin(ang)], np.linspace(w0, 0.16, 8), 2.9, 3.2, faces='TLRBE'), mat)
        if om:
            cx, cy = orb * math.cos(ang), orb * math.sin(ang)
            lathe_at(Di, [(1.15, 2.9), (1.15, 3.35), (0.8, 3.55)], 24, cx, cy, 'Gold' if om == 'Lamp' else 'Silver')
            lathe_at(Di, [(0.8, 3.55), (0.5, 3.8), (0.02, 3.9)], 16, cx, cy, om)
    return Rb, Do, Di


# ====================================================================== dome
def build_dome():
    D = B()
    D.add(*annulus(5.0, RD + 0.4, 96, 0.3, nr=16), 'ARCH_DomeEnamel')
    for rc, wd, z1, mat in ((RD - 0.6, 1.7, 5.3, 'Gold'), (RD - 2.0, 1.4, 3.7, 'Brass'), (RD - 3.2, 1.1, 2.3, 'Gold')):
        D.add(*sweep_bar(circ(rc, 144), wd, 0.3, z1, closed=True), mat)
    th = (np.arange(96) + 0.5) * TAU / 96
    D.add(*polar_boxes(RD - 0.95, RD - 0.35, th, 0.3 / RD, 5.3, 5.8, 'xXyYZ'), 'Lamp')
    for k in range(NRIB):
        t_ = k * TAU / NRIB
        rr = np.linspace(RD - 1.0, 12.3, 12)
        pts = np.c_[rr * math.cos(t_), rr * math.sin(t_)]
        D.add(*sweep_bar(pts, np.linspace(2.0, 0.9, 12), 0.3, np.linspace(4.4, 2.3, 12)), 'Brass')
        D.add(*sweep_bar(pts, np.linspace(0.8, 0.4, 12), np.linspace(4.4, 2.3, 12), np.linspace(5.0, 2.8, 12)), 'Gold')
    for rc, wd, z1, mat in ((12.4, 1.7, 3.1, 'Gold'), (26.0, 0.9, 1.6, 'Brass'), (26.0, 0.4, 1.9, 'Gold'), (39.0, 0.9, 1.6, 'Brass'), (39.0, 0.4, 1.9, 'Gold')):
        D.add(*sweep_bar(circ(rc, 120), wd, 0.3, z1, closed=True), mat)
    th = (np.arange(48) + 0.5) * TAU / 48
    D.add(*polar_boxes(25.75, 26.25, th, 0.25 / 26, 1.9, 2.3, 'xXyYZ'), 'Lamp')
    D.add(*polar_boxes(38.75, 39.25, th, 0.25 / 39, 1.9, 2.3, 'xXyYZ'), 'Lamp')
    # star chart inlay
    for rc in (15.5, 18.5, 21.5, 30, 33, 36, 43, 46):
        D.add(*sweep_bar(circ(rc, 96), 0.14, 0.3, 0.42, closed=True), 'Gold')
    for i in range(72):
        if i % 3 == 0:
            continue
        t_ = i * TAU / 72
        rr = np.linspace(13.4, RD - 4.0, 8)
        D.add(*sweep_bar(np.c_[rr * math.cos(t_), rr * math.sin(t_)], 0.1, 0.3, 0.4), 'Gold')
    for cx, cy, r in ((9, 4, 27), (-7, -10, 21), (3, -14, 33), (-12, 6, 16)):
        D.add(*sweep_bar(circ(r, 96, (cx, cy)), 0.2, 0.3, 0.46, closed=True), 'Gold')
    th = np.arange(360) * TAU / 360
    ln = np.where(np.arange(360) % 10 == 0, 1.3, 0.6)
    D.add(*polar_boxes(RD - 4.2 - ln, RD - 4.2, th, 0.0016, 0.3, 0.45, 'xXyYZ'), 'Gold')
    # constellations and stars
    sc, ss, sl = [], [], []
    for c in range(46):
        r0 = rng.uniform(15, 47)
        t0 = rng.uniform(0, TAU)
        p = np.array([r0 * math.cos(t0), r0 * math.sin(t0)])
        ang = rng.uniform(0, TAU)
        pts = [p]
        for s in range(int(rng.integers(3, 7))):
            ang += rng.uniform(-1.2, 1.2)
            q = pts[-1] + rng.uniform(1.8, 4.5) * np.array([math.cos(ang), math.sin(ang)])
            if 14 < np.hypot(*q) < 48.5:
                pts.append(q)
        pts = np.array(pts)
        if len(pts) > 1:
            D.add(*sweep_bar(pts, 0.17, 0.3, 0.46), 'Gold')
        for q in pts:
            sc.append(q)
            ss.append(rng.uniform(0.14, 0.34))
            sl.append(rng.random() < 0.45)
    nfs = 420
    r0 = rng.uniform(13.5, 49.5, nfs)
    t0 = rng.uniform(0, TAU, nfs)
    sc = np.concatenate([np.array(sc), np.c_[r0 * np.cos(t0), r0 * np.sin(t0)]])
    ss = np.concatenate([np.array(ss), rng.uniform(0.06, 0.16, nfs)])
    sl = np.concatenate([np.array(sl), rng.random(nfs) < 0.3])
    for lampm, mat in ((True, 'Lamp'), (False, 'Gold')):
        m = sl == lampm
        s = ss[m]
        c = sc[m]
        z = np.zeros(len(s))
        v, f = boxes(np.c_[-s, -s, z + 0.3], np.c_[s, s, z + 0.3 + 0.18], 'xXyYZ')
        v = v @ rotz(math.pi / 4).T
        v[:, :2] += np.repeat(c, 8, axis=0)
        D.add(v, f, mat)
    return D


def radial_bars(S, pts_rz, n, phase, width, thick, mat='Gold'):
    b = B()
    b.add(*sweep_bar(np.asarray(pts_rz, float), width, -thick / 2, thick / 2, faces='TLRB'), mat)
    for k in range(n):
        a_ = phase + k * TAU / n
        r_, tt = np.array([math.cos(a_), math.sin(a_), 0]), np.array([-math.sin(a_), math.cos(a_), 0])
        S.merge(b, fn=lambda V: V[:, 0:1] * r_ + V[:, 2:3] * tt + V[:, 1:2] * np.array([0, 0, 1.0]))


# ====================================================================== upper spire
def ring_platform(b, r0, r1, z, n_lamps, rail=True, up=1.0, mat='Brass'):
    v, f = lathe([(r0, z - 0.35), (r1, z - 0.35), (r1, z), (r0, z)], 72, closed=True)
    b.add(v, f, mat)
    v, f = lathe([(r1 - 0.12, z + 0.95), (r1 + 0.06, z + 0.95), (r1 + 0.06, z + 1.1), (r1 - 0.12, z + 1.1)], 72, closed=True)
    b.add(v, f, 'Gold')
    nb_ = int(TAU * r1 / 0.55)
    th = np.arange(nb_) * TAU / nb_
    b.add(*polar_boxes(r1 - 0.09, r1 + 0.03, th, 0.05 / r1, z, z + 0.95, 'xXyY'), 'Gold')
    th = (np.arange(n_lamps) + 0.5) * TAU / n_lamps
    b.add(*polar_boxes(r1 - 0.2, r1 + 0.14, th, 0.17 / r1, z + 1.1, z + 1.5, 'xXyYZz'), 'Lamp')
    b.add(*polar_boxes(r0, r1, th, 0.35 / r1, z - 0.7, z - 0.35, 'xXyYz'), 'Gold')


def build_spire_top():
    S = B()
    br = 1.56
    prof = [(0.02, 69.6), (br, 69.6), (br, 66.0), (2.5, 66.0), (2.7, 68.6), (3.6, 69.0), (3.6, 69.8), (2.8, 70.3), (3.0, 75.5),
            (4.5, 76.2), (4.5, 77.0), (3.3, 77.6), (3.7, 82.0), (5.7, 82.8), (5.7, 83.6), (4.3, 84.2), (5.1, 87.0),
            (7.7, 87.8), (7.7, 88.6), (6.1, 89.2), (7.6, 90.6), (11.0, 91.2), (11.0, 92.2)]
    v, f = lathe(prof, 16)
    S.add(v, f, 'Gold')
    # gold collar at the socket + lamps
    v, f = lathe([(2.5, 66.0), (2.9, 66.0), (2.9, 66.5), (2.6, 66.5)], 16)
    S.add(v, f, 'Brass')
    # hanging pinnacles under each bulge
    for z, r, n, h, pr in ((69.0, 3.9, 8, 2.6, 0.32), (76.2, 4.9, 12, 3.2, 0.36), (82.8, 6.2, 16, 3.6, 0.4), (87.8, 8.3, 20, 4.2, 0.45), (91.2, 11.2, 24, 5.0, 0.5)):
        pb = pinnacle(h, pr)
        for i in range(n):
            a_ = (i + 0.5) * TAU / n
            S.merge(pb, fn=xf(s=(1, 1, -1), t=(r * math.cos(a_), r * math.sin(a_), z + 0.2)))
    # lit window bands on the shaft stages
    for z0, z1, r, n in ((70.6, 75.2, 3.02, 16), (77.9, 81.8, 3.75, 16), (84.5, 86.8, 5.15, 24), (89.4, 90.4, 7.65, 32)):
        th = (np.arange(n) + 0.5) * TAU / n
        v, f = polar_boxes(r - 0.1, r + 0.06, th, 0.55 * math.pi / n, z0, z1, 'X')
        S.add(v, f, 'Window', np.repeat(win_rnd(n, 0.15), 8))
    # sweeping gothic ribs from the dome ring down to the shaft (crown cage)
    sg = np.linspace(0, 1, 12)
    radial_bars(S, np.c_[12.2 - 8.6 * sg ** 0.8, 90.9 - 12.6 * sg ** 1.7], 12, 0.0, 0.55, 0.5)
    radial_bars(S, np.c_[7.4 - 4.6 * sg ** 0.8, 87.4 - 15.5 * sg ** 1.6], 8, TAU / 16, 0.4, 0.4, 'Brass')
    # lantern above the socket
    th = (np.arange(8) + 0.5) * TAU / 8
    v, f = polar_boxes(2.55, 2.74, th, 0.26, 66.7, 68.3, 'X')
    S.add(v, f, 'Window', np.repeat(0.5 + 0.4 * rng.random(8), 8))
    # ring platforms (chandelier tiers) with arms and hanging rods
    for z, r0, r1, n in ((76.4, 7.4, 8.8, 16), (83.0, 10.2, 11.8, 24), (88.0, 13.2, 14.9, 32)):
        ring_platform(S, r0, r1, z, n)
        rb = {76.4: 4.4, 83.0: 5.6, 88.0: 7.6}[z]
        arm, af = boxes([rb - 0.2, -0.22, z - 0.3], [r0 + 0.1, 0.22, z - 0.02], 'yYzZ')
        na = n // 2
        for i in range(na):
            a_ = i * TAU / na
            S.add(arm @ rotz(a_).T, af, 'Gold')
            rm = (r0 + r1) / 2
            ztop = math.sqrt(92.2 ** 2 - rm ** 2)
            rod, rf = boxes([rm - 0.07, -0.07, z + 1.1], [rm + 0.07, 0.07, ztop + 0.2], 'xXyY')
            S.add(rod @ rotz(a_ + TAU / na / 2).T, rf, 'Gold')
        pb = pinnacle(1.8, 0.22)
        for i in range(n):
            a_ = i * TAU / n
            S.merge(pb, fn=xf(s=(1, 1, -1), t=(r1 * math.cos(a_), r1 * math.sin(a_), z - 0.35)))
    return S


# ====================================================================== bowl + lower spire + clockwork
TERR_A = [16.0, 26.0, 36.0, 40.0, 44.0, 48.0, 49.9]
GEAR_Z = -77.5


def terr_z():
    return [-(math.sqrt(RI ** 2 - a * a)) + 0.3 for a in TERR_A]


def floor_z(rho):
    zs = terr_z()
    for a, z in zip(TERR_A, zs):
        if rho <= a:
            return z
    return zs[-1]


def build_bowl():
    Bw = B()
    zs = terr_z()
    prof = [(TERR_A[-1], zs[-1])]
    for k in range(len(TERR_A) - 1, 0, -1):
        prof += [(TERR_A[k - 1], zs[k]), (TERR_A[k - 1], zs[k - 1])]
    prof += [(0.02, zs[0])]
    v, f = lathe(prof, 120)
    Bw.add(v, f, 'Bronze')
    for k in range(len(TERR_A) - 1):
        a = TERR_A[k]
        zlo, zhi = zs[k], zs[k + 1]
        h = zhi - zlo
        # gold cornice at the lip, railing, lamps
        v, f = lathe([(a - 0.25, zhi - 0.3), (a - 0.25, zhi + 0.06), (a + 0.3, zhi + 0.06)], 120)
        Bw.add(v, f, 'Gold')
        v, f = lathe([(a + 0.1, zhi + 0.9), (a + 0.1, zhi + 1.02), (a + 0.28, zhi + 1.02), (a + 0.28, zhi + 0.9)], 120, closed=True)
        Bw.add(v, f, 'Gold')
        nb_ = int(TAU * a / 0.7)
        th = np.arange(nb_) * TAU / nb_
        Bw.add(*polar_boxes(a + 0.13, a + 0.25, th, 0.05 / a, zhi + 0.06, zhi + 0.9, 'xXyY'), 'Brass')
        nl = int(TAU * a / 4.5)
        th = (np.arange(nl) + 0.5) * TAU / nl
        Bw.add(*polar_boxes(a + 0.02, a + 0.36, th, 0.17 / a, zhi + 1.02, zhi + 1.45, 'xXyYZz'), 'Lamp')
        # lit arcade on the riser
        if h > 1.5:
            nw = int(TAU * a / 1.5)
            th = (np.arange(nw) + 0.5) * TAU / nw
            v, f = polar_boxes(a - 0.07, a + 0.05, th, 0.3 * TAU / nw, zlo + 0.45, zhi - 0.55, 'x')
            Bw.add(v, f, 'Window', np.repeat(win_rnd(nw, 0.25), 8))
            v, f = polar_boxes(a - 0.16, a + 0.05, np.arange(nw) * TAU / nw, 0.12 * TAU / nw, zlo, zhi - 0.3, 'xyY')
            Bw.add(v, f, 'Brass')
    # radial stairs / spokes on the pit floors
    for k, (a0, a1) in enumerate(((9.8, 16.0), (16.5, 26.0), (26.5, 36.0))):
        z = zs[k]
        n = (8, 16, 24)[k]
        for i in range(n):
            t_ = (i + 0.5) * TAU / n
            rr = np.linspace(a0, a1 - 0.3, 3)
            Bw.add(*sweep_bar(np.c_[rr * math.cos(t_), rr * math.sin(t_)], 0.5, z, z + 0.12), 'Gold')
        for rc in ((a0 + a1) / 2,):
            Bw.add(*sweep_bar(circ(rc, 96), 0.4, z, z + 0.12, closed=True), 'Gold')
    return Bw


def face_lancets(S, rv, nf, z0, hs, hwid, xs, off=0.05):
    d = rv * math.cos(math.pi / nf)
    b = B()
    for x in xs:
        lancet(b, x, z0, hwid, hs, 1, wp=off + 0.04)
    V, F, M, R = b.arrays()
    for k in range(nf):
        t_ = (k + 0.5) * TAU / nf
        r_, tt = np.array([math.cos(t_), math.sin(t_), 0]), np.array([-math.sin(t_), math.cos(t_), 0])
        nw = len(xs)
        rv_ = win_rnd(nw + 1, 0.12)
        # slot per lancet: recover by x position
        b2 = B()
        for j, x in enumerate(xs):
            lancet(b2, x, z0, hwid, hs, float(rv_[j]), wp=off + 0.04)
        S.merge(b2, fn=lambda V: (d + V[:, 2:3]) * r_ + V[:, 0:1] * tt + V[:, 1:2] * np.array([0, 0, 1.0]))


def build_spire_low():
    S = B()
    br = 1.66
    zb = -90.9
    prof = [(9.6, zb), (9.6, -89.6), (8.4, -89.0), (8.4, -85.9), (9.0, -85.5), (9.0, -84.8), (7.0, -84.2), (7.0, -80.4),
            (7.6, -80.0), (7.6, -79.3), (5.6, -78.8), (5.6, -76.0), (6.6, -75.6), (6.6, -74.8), (4.6, -74.2), (4.6, -70.9),
            (5.2, -70.5), (5.2, -69.8), (3.2, -69.3), (3.2, -67.4), (2.7, -66.0), (br, -66.0), (br, -69.6), (0.02, -69.6)]
    v, f = lathe(prof, 8)
    S.add(v, f, 'Brass')
    for rv, z0, hs, hw_, xs in ((8.4, -88.8, 1.5, 0.5, (-1.9, 0, 1.9)), (7.0, -84.0, 2.1, 0.48, (-1.5, 0, 1.5)), (4.6, -74.0, 1.8, 0.42, (-0.85, 0.85)), (3.2, -69.1, 0.9, 0.36, (0,))):
        face_lancets(S, rv, 8, z0, hs, hw_, xs)
    # corner shafts + pinnacles on each setback
    for rv, zt, h, pr in ((9.0, -84.8, 3.0, 0.42), (7.6, -79.3, 0.9, 0.3), (6.6, -74.8, 2.6, 0.36), (5.2, -69.8, 2.0, 0.3), (9.6, -89.6, 2.2, 0.4)):
        pb = pinnacle(h, pr)
        for k in range(8):
            a_ = k * TAU / 8
            S.merge(pb, fn=xf(t=((rv - 0.55) * math.cos(a_), (rv - 0.55) * math.sin(a_), zt)))
    # gold edge shafts along the octagon corners
    for rv, z0, z1 in ((8.4, -89.0, -85.9), (7.0, -84.2, -80.4), (5.6, -78.8, -76.0), (4.6, -74.2, -70.9), (3.2, -69.3, -67.4)):
        v, f = boxes([rv - 0.12, -0.2, z0], [rv + 0.14, 0.2, z1], 'XyY')
        for k in range(8):
            S.add(v @ rotz(k * TAU / 8).T, f, 'Gold')
    # socket collar
    v, f = lathe([(2.7, -66.5), (3.0, -66.5), (3.0, -66.0), (2.7, -66.0)], 16)
    S.add(v, f, 'Gold')
    # ring platforms
    ring_platform(S, 6.4, 12.0, -73.8, 24)
    pb = pinnacle(3.6, 0.5)
    for k in range(16):
        a_ = (k + 0.5) * TAU / 16
        S.merge(pb, fn=xf(t=(11.0 * math.cos(a_), 11.0 * math.sin(a_), -73.8)))
    ring_platform(S, 5.0, 6.5, -69.7, 8)
    ring_platform(S, 8.8, 11.0, -84.7, 16)
    # crown of ribs from the big platform up to the socket shaft
    sg = np.linspace(0, 1, 10)
    radial_bars(S, np.c_[11.0 - 7.9 * sg ** 0.75, -72.6 + 5.4 * sg ** 1.8], 8, TAU / 16, 0.5, 0.45)
    th = (np.arange(8) + 0.5) * TAU / 8
    v, f = polar_boxes(2.9, 3.12, th * 0 + th, 0.22, -68.9, -67.6, 'X')
    # flying buttresses below the gear plane
    fz = floor_z(15.0)
    pier = B()
    v, f = lathe([(1.15, fz), (1.15, fz + 0.8), (0.9, fz + 1.0), (0.9, -81.6), (1.1, -81.4), (1.1, -80.8), (0.7, -80.6)], 4, a0=math.pi / 4)
    pier.add(v, f, 'Brass')
    pier.merge(pinnacle(2.0, 0.5), fn=xf(t=(0, 0, -80.7)))
    fly = B()
    for (p0, z0_), (p1, z1_) in (((-0.6, -82.2), (-7.4, -80.7)), ((-0.6, -85.6), (-5.6, -85.0))):
        s = np.linspace(0, 1, 9)
        px = p0 + (p1 - p0) * s
        pz = z0_ + (z1_ - z0_) * s + 1.3 * np.sin(s * math.pi) * 0.8 - 0.9 * s * (1 - s)
        fly.add(*sweep_bar(np.c_[px, pz], 0.5, -0.28, 0.28, faces='TLRB'), 'Gold')
    for k in range(8):
        a_ = (k + 0.5) * TAU / 8
        r_, tt = np.array([math.cos(a_), math.sin(a_), 0]), np.array([-math.sin(a_), math.cos(a_), 0])
        S.merge(pier, fn=xf(R=rotz(a_), t=(14.6 * math.cos(a_), 14.6 * math.sin(a_), 0)))
        S.merge(fly, fn=lambda V: (14.6 + V[:, 0:1]) * r_ + V[:, 2:3] * tt + V[:, 1:2] * np.array([0, 0, 1.0]))
    return S


def euler_for_axis(d):
    d = np.asarray(d, float) / np.linalg.norm(d)
    y = math.asin(max(-1, min(1, d[0])))
    x = math.atan2(-d[1], d[2])
    e = Euler((x, y, 0.0), 'ZYX')
    M = np.array(e.to_matrix())
    assert np.allclose(M[:, 2], d, atol=1e-5), ("euler axis mismatch", M[:, 2], d)
    return e, M


def spin_obj(name, col, b, loc, axis, dps):
    e, M = euler_for_axis(axis)
    ob = b.obj(name, col)
    ob.rotation_mode = 'ZYX'
    ob.rotation_euler = e
    ob.location = loc
    ob["spin_dps"] = float(dps)
    return ob


def build_clockwork(col, Bw):
    out = []
    zs = terr_z()
    t = 1.0
    # ---- horizontal train
    R0, N0, w0 = 20.0, 80, 3.0
    g0 = gear(R0, N0, -t / 2, t / 2, 7.4, 6.1, 10, mat='Brass')
    out.append(spin_obj("ARCH_Gear0", col, g0, (0, 0, GEAR_Z), (0, 0, 1), w0))
    sats = [("ARCH_Gear1", 12.0, 48, 65.0, 'Gold'), ("ARCH_Gear2", 9.0, 36, 160.0, 'Brass'), ("ARCH_Gear3", 12.0, 48, 215.0, 'Gold'), ("ARCH_Gear5", 7.0, 28, 328.0, 'Brass')]
    for name, Rg, Ng, az, mat in sats:
        al = rad(az)
        dist = R0 + Rg
        ph = mesh_phase(al, R0, 0.0, Rg, Ng)
        g = gear(Rg, Ng, -t / 2, t / 2, 1.6, 0.75, 6, mat=mat, phase=ph)
        cx, cy = dist * math.cos(al), dist * math.sin(al)
        zc = GEAR_Z
        if name == "ARCH_Gear2":
            # compound pinion on the same shaft, upper layer
            pin = gear(4.5, 18, 1.7, 2.7, 1.3, 0.75, 4, mat='Gold', phase=ph)
            g.merge(pin)
            v, f = lathe([(1.0, 0.5), (1.0, 1.7)], 16)
            g.add(v, f, 'Gold')
            g2 = (cx, cy, ph)
        out.append(spin_obj(name, col, g, (cx, cy, zc), (0, 0, 1), -w0 * N0 / Ng))
        # static axle post
        fz = floor_z(dist)
        v, f = lathe([(1.5, fz), (1.5, fz + 0.5), (0.7, fz + 0.9), (0.7, zc + 1.4 + (2.4 if name == "ARCH_Gear2" else 0)), (1.0, zc + 1.5 + (2.4 if name == "ARCH_Gear2" else 0)), (0.02, zc + 2.0 + (2.4 if name == "ARCH_Gear2" else 0))], 16)
        Bw.add(v + [cx, cy, 0], f, 'DarkMetal')
    # gear 4 on the upper layer meshing with the pinion of gear 2
    cx2, cy2, ph2 = g2
    R4, N4 = 10.5, 42
    az4 = rad(160.0 + 30.65)
    c4 = np.array([27.5 * math.cos(az4), 27.5 * math.sin(az4)])
    al = math.atan2(c4[1] - cy2, c4[0] - cx2)
    ph4 = mesh_phase(al, 4.5, ph2, R4, N4)
    g4 = gear(R4, N4, -0.5, 0.5, 1.6, 0.75, 6, mat='Brass', phase=ph4, trim='Silver', hubmat='Silver')
    w2 = -w0 * N0 / 36
    out.append(spin_obj("ARCH_Gear4", col, g4, (c4[0], c4[1], GEAR_Z + 2.2), (0, 0, 1), -w2 * 18 / N4))
    fz = floor_z(27.5)
    v, f = lathe([(1.5, fz), (1.5, fz + 0.5), (0.7, fz + 0.9), (0.7, GEAR_Z + 3.4), (1.0, GEAR_Z + 3.5), (0.02, GEAR_Z + 4.0)], 16)
    Bw.add(v + [c4[0], c4[1], 0], f, 'DarkMetal')
    # ---- vertical trains
    for tn, az, specs, w1 in (("A", 112.0, ((38.0, -74.8, 6.0, 24), (40.0, 10.0, 4.0, 16), (128.0, 9.0, 3.0, 12)), 4.0),
                              ("B", 22.0, ((38.5, -75.1, 5.5, 22), (48.0, 8.5, 3.0, 12)), -3.5)):
        al = rad(az)
        r_ = np.array([math.cos(al), math.sin(al), 0.0])
        tt = np.array([-math.sin(al), math.cos(al), 0.0])
        e, M = euler_for_axis(tt)
        xl, yl = M[:, 0], M[:, 1]

        def loc2(c):   # (rho, z) -> local plane angle coords
            w = c[0] * r_ + np.array([0, 0, c[1]])
            return np.array([w @ xl, w @ yl])
        (rho1, z1, Rg1, N1) = specs[0]
        cen = [(rho1, z1)]
        g = gear(Rg1, N1, -0.4, 0.4, 1.1, 0.4, 5, mat='Brass')
        out.append(spin_obj("ARCH_VGear%s1" % tn, col, g, tuple(rho1 * r_ + [0, 0, z1]), tt, w1))
        for i, (ang, dist, Rg, Ng) in enumerate(specs[1:]):
            c = (rho1 - dist * math.cos(rad(ang)), z1 + dist * math.sin(rad(ang)))
            cen.append(c)
            dl = loc2(c) - loc2((rho1, z1))
            a_l = math.atan2(dl[1], dl[0])
            ph = mesh_phase(a_l, Rg1, 0.0, Rg, Ng)
            g = gear(Rg, Ng, -0.4, 0.4, 0.9, 0.4, 4, mat=('Gold', 'Brass')[i % 2], phase=ph, hubmat='Silver')
            out.append(spin_obj("ARCH_VGear%s%d" % (tn, i + 2), col, g, tuple(c[0] * r_ + [0, 0, c[1]]), tt, -w1 * N1 / Ng))
        # static frame: two side plates + axles
        fr = B()
        f0 = (rho1 - 3.4, floor_z(rho1 - 3.4))
        f1 = (rho1 + 3.4, floor_z(rho1 + 3.4))
        paths = [[f0, cen[0], f1]] + [[cen[0], c] for c in cen[1:]]
        for pth in paths:
            for s0, s1 in ((0.75, 1.05), (-1.05, -0.75)):
                fr.add(*sweep_bar(np.array(pth), 0.55, s0, s1, faces='TLRBE'), 'DarkMetal')
        for c in cen:
            v, f = lathe([(0.02, -1.4), (0.36, -1.4), (0.36, 1.4), (0.02, 1.4)], 12)
            fr.add(np.c_[v[:, 0] + c[0], v[:, 1] + c[1], v[:, 2]], f, 'Gold')
        Bw.merge(fr, fn=lambda V: V[:, 0:1] * r_ + V[:, 2:3] * tt + V[:, 1:2] * np.array([0, 0, 1.0]))
    return out


# ====================================================================== main
def main():
    K.reset()
    col = K.coll("ARCH")
    G, HB = B(), B()
    info = build_galleries(G, HB)
    build_ribs(G, info)
    build_bridges(G)
    K.log("galleries+ribs tris", G.tris(), "hull tris", HB.tris())
    objs = [G.obj("ARCH_Galleries", col), HB.obj("ARCH_Hull", col)]
    del G, HB
    # rose
    R3 = rose_frame()
    Rb, Do, Di = build_rose()
    RS = B()
    RS.merge(Rb, fn=lambda V: cap_map(V, R3))
    objs.append(RS.obj("ARCH_Rose", col))
    for nm, b, dps in (("ARCH_RoseDialOuter", Do, 4.0), ("ARCH_RoseDialInner", Di, -6.0)):
        e, M = euler_for_axis(ROSE_AX)
        bb = B()
        bb.merge(b, fn=lambda V: cap_map(V))
        objs.append(spin_obj(nm, col, bb, (0, 0, 0), ROSE_AX, dps))
    # dome + spire
    Dm = B()
    Dm.merge(build_dome(), fn=lambda V: cap_map(V))
    objs.append(Dm.obj("ARCH_Dome", col))
    objs.append(build_spire_top().obj("ARCH_SpireTop", col))
    # bowl, lower spire, clockwork
    Bw = build_bowl()
    objs.append(build_spire_low().obj("ARCH_SpireLow", col))
    objs += build_clockwork(col, Bw)
    Bw.cut_open(C.HULL_OPEN_F)
    objs.append(Bw.obj("ARCH_Bowl", col))
    # report + envelope check
    tot = 0
    for ob in objs:
        me = ob.data
        nt = int(len(me.loops) - 2 * len(me.polygons))
        tot += nt
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3).astype(np.float64)
        Mw = np.array(ob.rotation_euler.to_matrix())
        wco = co @ Mw.T + np.array(ob.location)
        rr = np.linalg.norm(wco, axis=1)
        inside = wco[(rr < C.GIMBAL_R - 1e-3)]
        K.log("OBJ %-22s tris %8d  rmin %.2f rmax %.2f  spin %s  inside66 %d" % (ob.name, nt, rr.min(), rr.max(), ob.get("spin_dps"), len(inside)))
    K.log("TOTAL TRIS", tot, "objects", len(objs), "build %.1fs" % (time.time() - T0))
    K.save_blend(K.P("blend", "arch.blend"))


main()
