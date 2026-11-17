"""Build the fractured lunar rock crust -> blend/crust.blend (collection CRUST), moon-local coordinates.

Objects:
  CRUST_Near   static cracked plates around the opening (deep rocky walls, visible gaps)
  CRUST_Far    static fused plates on the rest of the sphere (hairline cracks)
  CRUST_L###   loose plates around the rim, lifted and tilted (own objects, custom props for animation)
  CRUST_F###   free floating fragments in front of the opening
  CRUST_Rock## individual debris rocks, CRUST_Gravel# clouds of small debris
Materials (placeholders, real node trees are built by look.py): MoonRock (slot 0, top surface, UV mapped),
MoonRockRaw (slot 1, fracture walls / undersides / debris).
Vertex attributes: depth (0 top .. 1 bottom of a fracture wall), rim (1 on plate edge), openf (open_field value).
"""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Quaternion
import common as K, config as C

SUBDIV = 9
DISP = 1.2
rng = np.random.default_rng(11)
sc = K.reset()
col = K.coll("CRUST")
mat_top = bpy.data.materials.new("MoonRock")
mat_raw = bpy.data.materials.new("MoonRockRaw")
R_BOT = C.HULL_R + 0.04

# ---------------------------------------------------------------- base sphere
t0 = time.time()
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=SUBDIV, radius=1.0)
base = bpy.context.object
co, li, ls, lt = K.mesh_arrays(base.data)
tris = li.reshape(-1, 3).astype(np.int64)
bme = base.data
bpy.data.objects.remove(base)
bpy.data.meshes.remove(bme)
NV, M = len(co), len(tris)
dirs = K.normalize(co)
K.log("sphere verts %d tris %d" % (NV, M))

# ---------------------------------------------------------------- heights (low-passed map -> geometry)
Hmap = np.load(K.P("textures", "moon_height.npy"))
Hh, Hw = Hmap.shape
Hlp = Hmap.reshape(Hh // 4, 4, Hw // 4, 4).mean(axis=(1, 3))
del Hmap
Lh, Lw = Hlp.shape
lon = np.arctan2(dirs[:, 1], dirs[:, 0])
lat = np.arcsin(np.clip(dirs[:, 2], -1, 1))


def sample_h(d):
    lo = np.arctan2(d[:, 1], d[:, 0])
    la = np.arcsin(np.clip(d[:, 2], -1, 1))
    x = (lo + np.pi) / (2 * np.pi) * Lw - 0.5
    y = (la + np.pi / 2) / np.pi * Lh - 0.5
    x0 = np.floor(x).astype(np.int64); tx = x - x0
    y0 = np.floor(y).astype(np.int64); ty = y - y0
    x1 = (x0 + 1) % Lw; x0 = x0 % Lw
    y1 = np.clip(y0 + 1, 0, Lh - 1); y0 = np.clip(y0, 0, Lh - 1)
    h_ = (Hlp[y0, x0] * (1 - tx) * (1 - ty) + Hlp[y0, x1] * tx * (1 - ty) + Hlp[y1, x0] * (1 - tx) * ty + Hlp[y1, x1] * tx * ty)
    return h_ + 0.10 * K.fbm3(d * 55.0, 3, seed=77)


hv = sample_h(dirs)
P0 = dirs * (C.R + DISP * hv)[:, None]
U0 = (lon + np.pi) / (2 * np.pi)
V0 = (lat + np.pi / 2) / np.pi
fvert = C.open_field(dirs)
K.log("heights done: min %.2f max %.2f" % (hv.min(), hv.max()))

# ---------------------------------------------------------------- plates (warped spherical voronoi)
cf = K.normalize(dirs[tris].mean(axis=1))
cand = K.normalize(rng.standard_normal((2000, 3)))
fc = C.open_field(cand)
prob = 0.80 * np.exp(-((fc - 1.03) / 0.20) ** 2) + 0.10 * np.exp(-((fc - 1.0) / 0.55) ** 2) + 0.03
s1 = cand[rng.random(len(cand)) < prob]
cand2 = K.normalize(rng.standard_normal((1000, 3)))
fc2 = C.open_field(cand2)
s2 = cand2[rng.random(len(cand2)) < 0.22 * np.exp(-((fc2 - 1.0) / 0.07) ** 2)]
seeds = np.concatenate([s1, s2])
NP_ = len(seeds)
fs = C.open_field(seeds)
K.log("plates: %d" % NP_)
wv = np.stack([K.fbm3(cf * 9.0 + o, 3, seed=s) for o, s in ((0.0, 101), (31.7, 102), (57.3, 103))], -1)
wv2 = np.stack([K.noise3(cf * 44.0 + o, seed=s) for o, s in ((0.0, 111), (13.1, 112), (71.9, 113))], -1)
cw = K.normalize(cf + 0.05 * wv + 0.013 * wv2).astype(np.float32)
del wv, wv2
S = seeds.astype(np.float32)
plate = np.empty(M, dtype=np.int32)
for i in range(0, M, 100000):
    plate[i:i + 100000] = np.argmax(cw[i:i + 100000] @ S.T, axis=1)
del cw

# classes: 0 removed, 1 floater, 2 loose, 3 cracked, 4 fused
jit = rng.normal(0, 0.03, NP_)
cls = np.where(fs + jit < 1.0, 0, np.where(fs < 1.15, 2, np.where(fs < 1.55, 3, 4))).astype(np.int32)
fl = (cls == 0) & (fs > 0.80) & (rng.random(NP_) < 0.36)
cls[fl] = 1
K.log("classes removed/floater/loose/cracked/fused:", [int((cls == k).sum()) for k in range(5)])

# trim (half gap) and wall roughness amplitude per plate
gap = np.full(NP_, 0.07)
amp = np.full(NP_, 0.05)
c3 = cls == 3
gap[c3] = (0.60 - 0.44 * np.clip((fs[c3] - 1.17) / 0.38, 0, 1)) * rng.uniform(0.7, 1.3, int(c3.sum()))
amp[c3] = np.clip(gap[c3] * 1.3, 0.1, 0.8)
c12 = (cls == 1) | (cls == 2)
gap[c12] = 0.3
amp[c12] = 0.45
# loose pieces are thinner than the full crust and taper towards their underside (broken shards, not extruded slabs)
prad = np.sqrt(np.bincount(plate, minlength=NP_) * 0.155 / np.pi)
rbot = np.full(NP_, R_BOT)
rbot[c12] = C.R - rng.uniform(2.0, 4.4, int(c12.sum()))
und = np.full(NP_, 0.55)
und[c12] = rng.uniform(1.3, 2.6, int(c12.sum())) * np.clip(prad[c12] / 5.0, 0.15, 1.0)

# neighbours across each directed edge
a_ = tris
b_ = np.roll(tris, -1, axis=1)
key = (a_ * NV + b_).ravel()
opp = (b_ * NV + a_).ravel()
order = np.argsort(key)
pos = np.searchsorted(key[order], opp)
nb_face = (order[pos] // 3).reshape(M, 3)
pl_eff = np.where(cls[plate] >= 1, plate, -1)
is_b = pl_eff[nb_face] != pl_eff[:, None]
del key, opp, order, pos, nb_face
K.log("topology done %.1fs" % (time.time() - t0))


def build_group(fidx, rows, bottom):
    """Returns dict(verts, tris, quads, uv, mat_idx, depth, rim, openf) for the given faces."""
    f_tris = tris[fidx]
    f_pl = plate[fidx].astype(np.int64)
    keyv = (f_pl[:, None] * NV + f_tris).ravel()
    uk, inv = np.unique(keyv, return_inverse=True)
    lv_plate = (uk // NV).astype(np.int64)
    lv_orig = (uk % NV).astype(np.int64)
    top = inv.reshape(-1, 3).astype(np.int32)
    n_top = len(uk)
    pos_top = P0[lv_orig].copy()
    d_top = dirs[lv_orig]
    # boundary edges and outward tangent normals
    fi, ki = np.nonzero(is_b[fidx])
    ea = top[fi, ki]
    eb = top[fi, (ki + 1) % 3]
    # smooth the triangle-grid zigzag out of the plate outlines
    nxt = np.full(n_top, -1, dtype=np.int64)
    prv = np.full(n_top, -1, dtype=np.int64)
    nxt[ea] = eb
    prv[eb] = ea
    bsel = np.nonzero((nxt >= 0) & (prv >= 0))[0]
    for _ in range(1):
        pos_top[bsel] = 0.5 * pos_top[bsel] + 0.25 * (pos_top[nxt[bsel]] + pos_top[prv[bsel]])
    e = pos_top[eb] - pos_top[ea]
    n_out = K.normalize(np.cross(e, K.normalize(d_top[ea] + d_top[eb])))
    vn = np.zeros((n_top, 3))
    np.add.at(vn, ea, n_out)
    np.add.at(vn, eb, n_out)
    isb = np.zeros(n_top, dtype=bool)
    isb[ea] = True
    isb[eb] = True
    bidx = np.nonzero(isb)[0]
    nbv = len(bidx)
    vnb = K.normalize(vn[bidx])
    gp = gap[lv_plate[bidx]] * np.clip(0.75 + 1.3 * K.fbm3(d_top[bidx] * 21.0, 2, seed=207), 0.25, 2.2)
    am = amp[lv_plate[bidx]]
    pb0 = pos_top[bidx].copy()
    pos_top[bidx] -= vnb * (gp * 0.5)[:, None]
    bmap = np.full(n_top, -1, dtype=np.int64)
    bmap[bidx] = np.arange(nbv)
    # walls
    t = np.linspace(0.0, 1.0, rows + 1)
    r_top = np.linalg.norm(pb0, axis=1)
    rb = rbot[lv_plate[bidx]]
    rk = r_top[:, None] * (1 - t)[None, :] + rb[:, None] * t[None, :]
    dirb = pb0 / r_top[:, None]
    basep = dirb[:, None, :] * rk[:, :, None]
    pflat = basep.reshape(-1, 3)
    nz = (K.fbm3(pflat * 0.55, 3, seed=201) * 0.75 + K.fbm3(pflat * 2.3, 2, seed=202, ridged=True) * 0.34).reshape(nbv, rows + 1)
    rr = rk.ravel()
    strata = 0.32 * K.noise3(np.stack([rr * 1.9, np.zeros_like(rr), np.zeros_like(rr)], -1), seed=203).reshape(nbv, rows + 1)
    under = 0.5 + 0.5 * K.noise3(dirb * 23.0, seed=204)
    ramp = np.minimum(1.0, t * 3.5)[None, :]
    off = -gp[:, None] * 0.5 + am[:, None] * ramp * (nz + strata) - (am * und[lv_plate[bidx]])[:, None] * t[None, :] * under[:, None]
    wall = basep + vnb[:, None, :] * off[:, :, None]
    wv_ = wall.reshape(-1, 3)
    wbase = n_top
    bi = bmap[ea]
    bj = bmap[eb]
    kk = np.arange(rows)[None, :]
    wi0 = wbase + bi[:, None] * (rows + 1) + kk
    wj0 = wbase + bj[:, None] * (rows + 1) + kk
    quads = np.stack([wj0, wi0, wi0 + 1, wj0 + 1], -1).reshape(-1, 4).astype(np.int32)
    verts = [pos_top, wv_]
    depth = [np.zeros(n_top), np.tile(t, nbv)]
    rim = [isb.astype(np.float64), np.zeros(len(wv_))]
    openf = [fvert[lv_orig], np.repeat(fvert[lv_orig[bidx]], rows + 1)]
    tri_list = [top]
    # uv for top loops (seam fix per face)
    uu = U0[lv_orig][top]
    vv = V0[lv_orig][top]
    span = uu.max(axis=1) - uu.min(axis=1) > 0.5
    uu = np.where(span[:, None] & (uu < 0.5), uu + 1.0, uu)
    uv_top = np.stack([uu, vv], -1).reshape(-1, 2)
    uv = [uv_top]
    midx = [np.zeros(len(top), dtype=np.int32)]
    if bottom:
        pb = d_top * rbot[lv_plate][:, None]
        pb[bidx] = wall[:, rows, :]
        off_b = n_top + len(wv_)
        verts.append(pb)
        depth.append(np.full(n_top, 0.2))
        rim.append(np.zeros(n_top))
        openf.append(fvert[lv_orig])
        tri_list.append(top[:, ::-1] + off_b)
        uv.append(np.stack([uu[:, ::-1], vv[:, ::-1]], -1).reshape(-1, 2))
        midx.append(np.ones(len(top), dtype=np.int32))
    uv.append(np.zeros((len(quads) * 4, 2)))
    midx.append(np.ones(len(quads), dtype=np.int32))
    return dict(verts=np.concatenate(verts), tris=np.concatenate(tri_list), quads=quads, uv=np.concatenate(uv),
                mat_idx=np.concatenate(midx), depth=np.concatenate(depth), rim=np.concatenate(rim),
                openf=np.concatenate(openf))


def make_obj(name, g, origin=None):
    v = g["verts"]
    if origin is not None:
        v = v - origin[None, :]
    ob = K.obj_np(name, col, v, [g["tris"], g["quads"]], uv=g["uv"], mat_idx=g["mat_idx"],
                  attrs={"depth": ('POINT', g["depth"]), "rim": ('POINT', g["rim"]), "openf": ('POINT', g["openf"])},
                  mats=[mat_top, mat_raw], smooth=True)
    # fracture walls are faceted (crisp broken rock), tops/undersides stay smooth
    sm = np.ones(len(ob.data.polygons), dtype=bool)
    sm[len(g["tris"]):] = False
    ob.data.polygons.foreach_set("use_smooth", sm)
    return ob


# ---------------------------------------------------------------- static groups
fcls = cls[plate]
g = build_group(np.nonzero(fcls == 3)[0], 7, False)
make_obj("CRUST_Near", g)
K.log("CRUST_Near verts %d tris %d quads %d" % (len(g["verts"]), len(g["tris"]), len(g["quads"])))
g = build_group(np.nonzero(fcls == 4)[0], 2, False)
make_obj("CRUST_Far", g)
K.log("CRUST_Far verts %d tris %d quads %d" % (len(g["verts"]), len(g["tris"]), len(g["quads"])))

# ---------------------------------------------------------------- loose plates and floaters
order_f = np.argsort(plate, kind='stable')
starts = np.searchsorted(plate[order_f], np.arange(NP_ + 1))
od = np.asarray(C.OPEN_DIR)
n_loose = n_float = 0
for p in np.nonzero(c12)[0]:
    fidx = order_f[starts[p]:starts[p + 1]]
    if len(fidx) < 12:
        continue
    g = build_group(fidx, 7, True)
    g["openf"] = np.full(len(g["openf"]), 3.0)
    cen = P0[np.unique(tris[fidx])].mean(axis=0)
    n = cen / np.linalg.norm(cen)
    half = float(np.max(np.linalg.norm(P0[np.unique(tris[fidx])] - cen, axis=1)))
    gdir = od - n * float(od @ n)
    gdir = gdir / max(np.linalg.norm(gdir), 1e-6)
    axis = np.cross(gdir, n)
    if cls[p] == 2:
        s = float(np.clip((1.17 - fs[p]) / 0.17, 0, 1))
        ang = math.radians(rng.uniform(1.0, 4.0) + 9.0 * s ** 1.5 * rng.uniform(0.3, 1.0))
        lift = 0.25 + math.sin(ang) * half * 0.95 + 3.0 * s ** 1.6 * rng.uniform(0.2, 1.0)
        loc = cen + n * lift + gdir * (-0.4 * s * rng.uniform(0, 1))
        q = Quaternion(Vector(axis), ang) @ Quaternion(Vector(n), math.radians(rng.uniform(-2.5, 2.5)))
        name = "CRUST_L%03d" % n_loose
        n_loose += 1
        kind = 0.0
    else:
        s = float(np.clip((1.0 - fs[p]) / 0.20, 0, 1))
        lift = rng.uniform(4.0, 12.0) + 16.0 * s * rng.uniform(0.3, 1.0)
        lateral = K.normalize(np.cross(n, rng.standard_normal(3)))
        loc = cen + n * lift + lateral * rng.uniform(0, 7.0) + gdir * rng.uniform(-4, 6)
        rax = K.normalize(axis + 0.8 * rng.standard_normal(3))
        q = Quaternion(Vector(rax), math.radians(rng.uniform(12, 55)))
        name = "CRUST_F%03d" % n_float
        n_float += 1
        kind = 1.0
    ob = make_obj(name, g, origin=cen)
    ob.location = loc
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = q
    ob["kind"] = kind
    ob["nrm"] = [float(v) for v in n]
    ob["phase"] = float(rng.uniform(0, 6.283))
    ob["period"] = float(rng.uniform(9, 19))
    ob["bob"] = float(rng.uniform(0.12, 0.45) if kind == 0.0 else rng.uniform(0.6, 1.8))
    ob["size"] = half
K.log("loose %d floaters %d  %.1fs" % (n_loose, n_float, time.time() - t0))

# ---------------------------------------------------------------- debris rocks
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1.0)
rme = bpy.data.meshes.new("_r")
bm.to_mesh(rme)
bm.free()
rco, rli, _, _ = K.mesh_arrays(rme)
rtri = rli.reshape(-1, 3)
bpy.data.meshes.remove(rme)
rdir = K.normalize(rco)
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
rme = bpy.data.meshes.new("_r2")
bm.to_mesh(rme)
bm.free()
sco, sli, _, _ = K.mesh_arrays(rme)
stri = sli.reshape(-1, 3)
bpy.data.meshes.remove(rme)
sdir = K.normalize(sco)


def rock_shape(d, seed, size):
    o = seed * 3.71
    cell = np.round(K.fbm3(d * 1.1 + o, 2, seed=300 + seed) * 3.2) / 3.2            # terraced lobes -> flat facets, hard edges
    rad = 1.0 + 0.55 * cell + 0.20 * K.fbm3(d * 4.5 + o, 2, seed=400 + seed, ridged=True)
    sc3 = np.array([rng.uniform(0.6, 1.35), rng.uniform(0.6, 1.35), rng.uniform(0.5, 1.0)])
    return d * rad[:, None] * sc3[None, :] * size


def rim_points(n, rlo, rhi, pw):
    out = []
    while len(out) < n:
        d = K.normalize(rng.standard_normal((400, 3)))
        f = C.open_field(d)
        ok = (f > 0.90) & (f < 1.28)
        for dd in d[ok]:
            out.append(dd * (rlo + (rhi - rlo) * rng.random() ** pw))
            if len(out) >= n:
                break
    return np.array(out)


pts = rim_points(38, 96.0, 130.0, 1.8)
for i, pnt in enumerate(pts):
    size = float(np.exp(rng.uniform(np.log(0.7), np.log(3.6))))
    v = rock_shape(rdir, i, size)
    ob = K.obj_np("CRUST_Rock%02d" % i, col, v, rtri, mats=[mat_raw], smooth=False,
                  attrs={"depth": ('POINT', np.full(len(v), 0.25)), "rim": ('POINT', np.zeros(len(v))), "openf": ('POINT', np.ones(len(v)))})
    ob.location = pnt
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Quaternion(Vector(K.normalize(rng.standard_normal(3))), rng.uniform(0, 3.1))
    ob["kind"] = 2.0
    ob["phase"] = float(rng.uniform(0, 6.283))
    ob["period"] = float(rng.uniform(10, 24))
    ob["bob"] = float(rng.uniform(0.5, 2.0))
    ob["nrm"] = [float(v_) for v_ in K.normalize(pnt)]
    ob["size"] = size
for ci in range(4):
    pts = rim_points(170, 93.0, 128.0, 1.5)
    parts = []
    for i, pnt in enumerate(pts):
        size = float(np.exp(rng.uniform(np.log(0.08), np.log(0.7))))
        parts.append((rock_shape(sdir, 1000 + ci * 200 + i, size) + pnt[None, :], stri))
    v, f = K.join_meshes(parts)
    ob = K.obj_np("CRUST_Gravel%d" % ci, col, v, f, mats=[mat_raw], smooth=False,
                  attrs={"depth": ('POINT', np.full(len(v), 0.25)), "rim": ('POINT', np.zeros(len(v))), "openf": ('POINT', np.ones(len(v)))})
    ob["kind"] = 3.0
    ob["phase"] = float(ci)
K.log("debris done")

# ---------------------------------------------------------------- loose rocks lying on the static plates (close-up detail)
if os.environ.get("CRUST_ROCKS", "0") == "1":
    cand = K.normalize(rng.standard_normal((40000, 3)))
    fcd = C.open_field(cand)
    keep = (fcd > 1.17) & (fcd < 2.1) & (rng.random(len(cand)) < np.exp(-(fcd - 1.17) / 0.40))
    rd = cand[keep][:3000]
    rr = C.R + DISP * sample_h(rd)
    parts2, parts3 = [], []
    for i in range(len(rd)):
        sz = float(np.exp(rng.uniform(np.log(0.10), np.log(1.0))) ** 1.0)
        if rng.random() < 0.75:
            sz = min(sz, rng.uniform(0.10, 0.38))
        big = sz > 0.45
        v = rock_shape(rdir if big else sdir, 5000 + i, sz)
        zax = rd[i]
        xax = K.normalize(np.cross(zax, rng.standard_normal(3)))
        yax = np.cross(zax, xax)
        Rm = np.stack([xax, yax, zax], -1)
        v = v @ Rm.T + rd[i][None, :] * (rr[i] - 0.22 * sz)
        (parts3 if big else parts2).append((v, rtri if big else stri))
    allp = parts2 + parts3
    v, f = K.join_meshes([(a, b) for a, b in allp])
    ob = K.obj_np("CRUST_SurfRocks", col, v, f, mats=[mat_raw], smooth=False,
                  attrs={"depth": ('POINT', np.full(len(v), 0.2)), "rim": ('POINT', np.zeros(len(v))), "openf": ('POINT', np.full(len(v), 3.0))})
    K.log("surface rocks: %d  tris %d" % (len(rd), len(f)))
K.log("TRIS total %d  objects %d" % (K.tri_count(), len(col.objects)))
K.save_blend(K.P("blend", os.environ.get("CRUST_OUT", "crust.blend")))
K.log("CRUST DONE %.1fs" % (time.time() - t0))
