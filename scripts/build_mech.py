"""Build the rotating mechanism -> blend/mech.blend (collection MECH), moon-local coordinates.

  MECH_G1..G5   nested gimbal rings (true gimbal: each ring pivots on a diameter of its parent)
  MECH_Cage     filigree cage around the core, MECH_Core the glowing orb
  MECH_ExtRing  huge exterior orbit ring, MECH_ExtWire thin companion ring
Custom props: gim_axis (euler index), gim_dps, gim_phase (deg)  /  spin_dps (local Z)
"""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, Euler
import common as K, config as C, mats

rng = np.random.default_rng(5)
sc = K.reset()
col = K.coll("MECH")
for n in ("RingEngrave", "RingWindows"):
    bpy.data.materials.new(n)


def M(name):
    return mats.get(name)


# ------------------------------------------------------------------ primitives
def _ico(sub):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
    me = bpy.data.meshes.new("_i")
    bm.to_mesh(me)
    bm.free()
    co, li, _, _ = K.mesh_arrays(me)
    bpy.data.meshes.remove(me)
    return K.normalize(co).astype(np.float32), li.reshape(-1, 3).copy()


ICO = {s: _ico(s) for s in (1, 2, 3, 4)}


class B:
    def __init__(self):
        self.parts = []

    def add(self, v, f, mat, uv=None, R=None, T=None):
        v = np.asarray(v, dtype=np.float64)
        if R is not None:
            v = v @ np.asarray(R).T
        if T is not None:
            v = v + np.asarray(T)[None, :]
        self.parts.append((v, np.asarray(f, dtype=np.int32), mat, uv))

    def build(self, name, sharp=38):
        ml, verts, off = [], [], 0
        byk = {}
        for v, f, m, uv in self.parts:
            if m not in ml:
                ml.append(m)
            k = f.shape[1]
            uvl = uv if uv is not None else np.zeros((len(f) * k, 2), np.float32)
            d = byk.setdefault(k, ([], [], []))
            d[0].append(f + off)
            d[1].append(np.full(len(f), ml.index(m), np.int32))
            d[2].append(np.asarray(uvl, np.float32))
            verts.append(v)
            off += len(v)
        faces, midx, uvs = [], [], []
        for k in sorted(byk):
            faces.append(np.concatenate(byk[k][0]))
            midx.append(np.concatenate(byk[k][1]))
            uvs.append(np.concatenate(byk[k][2]))
        return K.obj_np(name, col, np.concatenate(verts), faces, uv=np.concatenate(uvs), mat_idx=np.concatenate(midx),
                        mats=[M(m) for m in ml], sharp_angle=sharp)


def sweep(poly, r, nseg, tooth=None, th0=0.0, th1=2 * math.pi):
    """Sweep an open polyline [(rho, z), ...] around Z at radius r. Returns verts, quads, uv (u in degrees, v 0..1).
    tooth = (flags per point, height): flagged points get a square-wave radius (nseg must be a multiple of 4)."""
    poly = np.asarray(poly, dtype=np.float64)
    k = len(poly)
    th = np.linspace(th0, th1, nseg + 1)
    rho = np.repeat(poly[None, :, 0], nseg + 1, axis=0)
    if tooth is not None:
        flags, hgt = tooth
        pat = np.array([0.0, 1.0, 1.0, 0.0])[np.arange(nseg + 1) % 4]
        rho = rho + pat[:, None] * np.asarray(flags, dtype=np.float64)[None, :] * hgt
    rad = r + rho
    v = np.stack([rad * np.cos(th)[:, None], rad * np.sin(th)[:, None], np.repeat(poly[None, :, 1], nseg + 1, axis=0)], -1).reshape(-1, 3)
    i = np.arange(nseg)[:, None]
    j = np.arange(k - 1)[None, :]
    a = i * k + j
    q = np.stack([a, a + k, a + k + 1, a + 1], -1).reshape(-1, 4)
    seglen = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    vv = np.concatenate([[0], np.cumsum(seglen)]) / max(seglen.sum(), 1e-9)
    # orientation: normal of (dtheta x dprofile) in profile coords is (dz, -drho); must point away from the profile centre
    d = poly[1] - poly[0]
    mid = (poly[1] + poly[0]) * 0.5
    if d[1] * mid[0] - d[0] * mid[1] < 0:
        q = q[:, ::-1]
    ud = np.degrees(th)
    quv = np.stack([np.stack([ud[q // k], vv[q % k]], -1)], 0)[0].reshape(-1, 2)
    return v, q, quv


def cyl(p0, p1, rad, n=20, rad1=None):
    """Cylinder/cone from p0 to p1 with end caps. Returns [(verts, quads), (verts, ngon caps)]."""
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    ax = p1 - p0
    L_ = np.linalg.norm(ax)
    ax = ax / L_
    ref = np.array([0, 0, 1.0]) if abs(ax[2]) < 0.9 else np.array([1.0, 0, 0])
    u = K.normalize(np.cross(ax, ref))
    w = np.cross(ax, u)
    th = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ring = np.cos(th)[:, None] * u[None, :] + np.sin(th)[:, None] * w[None, :]
    r1 = rad if rad1 is None else rad1
    v = np.concatenate([p0 + ring * rad, p1 + ring * r1, p0 + ring * rad, p1 + ring * r1])
    i = np.arange(n)
    j = (i + 1) % n
    q = np.stack([i, j, j + n, i + n], -1)
    caps = np.stack([2 * n + i[::-1], 3 * n + i])
    return v, q, caps


def add_cyl(b, p0, p1, rad, mat, n=20, rad1=None, R=None, T=None):
    v, q, caps = cyl(p0, p1, rad, n, rad1)
    b.add(v, q, mat, R=R, T=T)
    b.add(v, caps, mat, R=R, T=T)


def add_box(b, c, h, mat, R=None, T=None):
    c = np.asarray(c, float)
    h = np.asarray(h, float)
    s = np.array([[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], float)
    v = c + s * h
    q = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])
    b.add(v, q, mat, R=R, T=T)


def add_sphere(b, c, rad, mat, sub=3, R=None, T=None, squash=1.0):
    v, f = ICO[sub]
    b.add(v * np.array([rad, rad, rad * squash]) + np.asarray(c, float), f, mat, R=R, T=T)


def tube(points, rad, sides=6, closed=True, ref=None):
    """Tube along a polyline. ref: per-point reference vectors (default: radial from origin)."""
    p = np.asarray(points, float)
    n = len(p)
    if closed:
        tan = np.roll(p, -1, axis=0) - np.roll(p, 1, axis=0)
    else:
        tan = np.gradient(p, axis=0)
    tan = K.normalize(tan)
    rf = K.normalize(p) if ref is None else np.asarray(ref, float)
    n1 = K.normalize(np.cross(tan, rf))
    n2 = np.cross(tan, n1)
    th = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    v = (p[:, None, :] + rad * (np.cos(th)[None, :, None] * n1[:, None, :] + np.sin(th)[None, :, None] * n2[:, None, :])).reshape(-1, 3)
    i = np.arange(n if closed else n - 1)[:, None]
    j = np.arange(sides)[None, :]
    i2 = (i + 1) % n
    j2 = (j + 1) % sides
    q = np.stack([i * sides + j, i2 * sides + j, i2 * sides + j2, i * sides + j2], -1).reshape(-1, 4)
    return v, q


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def rot_to(zdir, xhint=(1, 0, 0)):
    z = K.normalize(np.asarray(zdir, float))
    x = np.asarray(xhint, float)
    x = K.normalize(x - z * float(x @ z))
    y = np.cross(z, x)
    return np.stack([x, y, z], -1)


# ------------------------------------------------------------------ a gimbal ring (in its own frame: plane XY, pins along X)
def gimbal_ring(name, r, w, t, pin_out, nseg=720, teeth=False, planets=0, stations=3, seed=0):
    rg = np.random.default_rng(100 + seed)
    b = B()
    f = 0.17 * w
    c = 0.30 * t
    P = [(t / 2, -w / 2), (t / 2, -w / 2 + f), (t / 2 - c, -w / 2 + f), (t / 2 - c, w / 2 - f), (t / 2, w / 2 - f), (t / 2, w / 2),
         (-t / 2, w / 2), (-t / 2, w / 2 - f), (-t / 2 + c, w / 2 - f), (-t / 2 + c, -w / 2 + f), (-t / 2, -w / 2 + f), (-t / 2, -w / 2)]
    segs = [("Gold", [0, 1, 2]), ("RingEngrave", [2, 3]), ("Gold", [3, 4, 5]), ("RingWindows", [5, 6]),
            ("Gold", [6, 7, 8]), ("RingEngrave", [8, 9]), ("Gold", [9, 10, 11]), ("RingWindows", [11, 0])]
    for mat, idx in segs:
        poly = [P[i] for i in idx]
        tooth = None
        if teeth and mat == "Gold" and idx in ([0, 1, 2], [3, 4, 5]):
            flags = [1.0 if abs(P[i][0] - t / 2) < 1e-6 else 0.0 for i in idx]
            tooth = (flags, 0.32 * t)
        v, q, uv = sweep(poly, r, nseg, tooth=tooth)
        b.add(v, q, mat, uv=uv)
    # ribs across both channels every 10 degrees
    for k in range(36):
        a = math.radians(k * 10 + 5)
        Rm = rot_z(a)
        add_box(b, (r + t / 2 - c / 2, 0, 0), (c / 2 + 0.02, 0.16 * w / 4.5 + 0.08, w / 2 - f), "Brass", R=Rm)
        add_box(b, (r - t / 2 + c / 2, 0, 0), (c / 2 + 0.02, 0.16 * w / 4.5 + 0.08, w / 2 - f), "Brass", R=Rm)
    # carriages riding on the ring, with lamps
    for k in range(stations):
        a = rg.uniform(0.35, 1.2) + k * 2 * math.pi / stations
        if abs(math.sin(a)) < 0.25:
            a += 0.4
        Rm = rot_z(a)
        add_box(b, (r, 0, 0), (t / 2 + 0.45, 1.6 + 0.25 * w, w / 2 + 0.45), "DarkMetal", R=Rm)
        add_box(b, (r, 0, 0), (t / 2 + 0.62, 0.22, w / 2 + 0.62), "Gold", R=Rm)
        add_box(b, (r, 1.2 + 0.2 * w, 0), (t / 2 + 0.62, 0.16, w / 2 + 0.62), "Gold", R=Rm)
        add_box(b, (r, -1.2 - 0.2 * w, 0), (t / 2 + 0.62, 0.16, w / 2 + 0.62), "Gold", R=Rm)
        for sz in (-1, 1):
            for sy in (-1, 1):
                add_sphere(b, (r + t / 2 + 0.55, sy * (0.7 + 0.12 * w), sz * (w / 2 + 0.2)), 0.26, "Lamp", sub=1, R=Rm)
                add_sphere(b, (r - t / 2 - 0.55, sy * (0.7 + 0.12 * w), sz * (w / 2 + 0.2)), 0.26, "Lamp", sub=1, R=Rm)
    # pivot pins + bearing hubs along +-X
    for sgn in (-1, 1):
        x_in = sgn * (r - t / 2 - 0.5)
        x_ring = sgn * (r + t / 2)
        x_out = sgn * pin_out
        add_cyl(b, (x_in, 0, 0), (x_out, 0, 0), 0.24 * w + 0.15, "Silver", n=24)
        add_cyl(b, (sgn * (r - t / 2 - 1.1), 0, 0), (sgn * (r + t / 2 + 1.1), 0, 0), 0.62 * w, "DarkMetal", n=32)
        add_cyl(b, (sgn * (r - t / 2 - 1.4), 0, 0), (sgn * (r - t / 2 - 1.1), 0, 0), 0.50 * w, "Gold", n=32)
        add_cyl(b, (sgn * (r + t / 2 + 1.1), 0, 0), (sgn * (r + t / 2 + 1.5), 0, 0), 0.50 * w, "Gold", n=32)
        add_cyl(b, (sgn * (pin_out - 1.6), 0, 0), (x_out, 0, 0), 0.40 * w, "Brass", n=32)
        for k in range(8):
            a = k * math.pi / 4
            add_sphere(b, (sgn * (r + t / 2 + 1.15), math.cos(a) * 0.5 * w, math.sin(a) * 0.5 * w), 0.14 * w / 4.5 + 0.08, "Gold", sub=1)
    # orrery planets on arms
    for k in range(planets):
        a = rg.uniform(0, 2 * math.pi)
        if abs(math.cos(a)) > 0.9:
            a += 0.7
        Rm = rot_z(a)
        pr = rg.uniform(1.5, 2.9)
        arm = rg.uniform(4.0, 7.5)
        side = 1 if k % 2 == 0 else -1
        add_cyl(b, (r, 0, side * w / 2), (r, 0, side * (w / 2 + arm)), 0.16, "Brass", n=10, R=Rm)
        add_sphere(b, (r, 0, side * (w / 2 + arm + pr * 0.8)), pr, "Silver" if k % 2 else "MoonRockRaw", sub=3, R=Rm)
        v, q = tube([(r + math.cos(u) * pr * 1.5, math.sin(u) * pr * 1.5, side * (w / 2 + arm + pr * 0.8)) for u in np.linspace(0, 2 * math.pi, 48, endpoint=False)],
                    0.09, sides=5, ref=[(0, 0, 1)] * 48)
        b.add(v, q, "Gold", R=Rm)
    ob = b.build(name)
    return ob


bpy.data.materials.new("MoonRockRaw")
# name, radius, axial width, radial thickness, deg/s, start phase
# slow, majestic rates: the shadow shafts these throw into the mist must sweep, not strobe
RINGS = [("MECH_G1", 62.0, 4.6, 2.7, 4.2, 28.0),
         ("MECH_G2", 53.0, 4.0, 2.4, -5.8, 52.0),
         ("MECH_G3", 44.5, 3.6, 2.1, 7.2, -38.0),
         ("MECH_G4", 36.5, 3.1, 1.9, -8.4, 64.0),
         ("MECH_G5", 29.0, 2.7, 1.7, 9.6, -25.0)]
parent = None
objs = []
for i, (name, r, w, t, dps, ph) in enumerate(RINGS):
    if i == 0:
        pin_out = 69.0
    else:
        pr, pw, pt = RINGS[i - 1][1:4]
        pin_out = pr - pt / 2 + 0.6
    ob = gimbal_ring(name, r, w, t, pin_out, nseg=720 if r > 40 else 540, teeth=(i in (1, 3)), planets=(3 if i == 0 else (2 if i == 2 else 0)),
                     stations=3 if i < 3 else 2, seed=i)
    if i == 0:
        ob.rotation_mode = 'XYZ'
        ob.rotation_euler = (0.0, -math.pi / 2, math.radians(ph))
        ob["gim_axis"] = 2
    else:
        ob.parent = parent
        ob.rotation_mode = 'ZYX'
        ob.rotation_euler = (0.0, math.radians(ph), math.pi / 2)
        ob["gim_axis"] = 1
    ob["gim_dps"] = dps
    ob["gim_phase"] = ph
    parent = ob
    objs.append(ob)
    K.log(name, "tris", K.tri_count([ob]))

# ------------------------------------------------------------------ core cage + core
b = B()
RC = 13.5
vi, fi = ICO[1]
centers = list(K.normalize(vi[:12] if len(vi) >= 12 else vi))
v0, f0 = _ico(1)
# flower-of-life: circles around the 12 icosahedron vertices and the 20 face centres
ico_v = []
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
ico_v = [np.array(v.co[:]) for v in bm.verts]
ico_f = [K.normalize(np.mean([np.array(v.co[:]) for v in f.verts], axis=0)) for f in bm.faces]
bm.free()
for cdir, ang, rad in [(d, 37.4, 0.17) for d in ico_v] + [(d, 22.0, 0.11) for d in ico_f]:
    cdir = K.normalize(cdir)
    Rm = rot_to(cdir)
    a = math.radians(ang)
    u = np.linspace(0, 2 * math.pi, 72, endpoint=False)
    pts = np.stack([math.sin(a) * np.cos(u), math.sin(a) * np.sin(u), np.full_like(u, math.cos(a))], -1) * RC
    pts = pts @ Rm.T
    v, q = tube(pts, rad, sides=5)
    b.add(v, q, "Gold")
for d in ico_v:
    add_sphere(b, K.normalize(d) * RC, 0.42, "Brass", sub=1)
# inner geodesic lattice
v2, f2 = ICO[2]
edges = set()
for tri in f2:
    for a_, b_ in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
        edges.add((min(a_, b_), max(a_, b_)))
for a_, b_ in edges:
    v, q, caps = cyl(v2[a_] * 10.2, v2[b_] * 10.2, 0.10, n=5)
    b.add(v, q, "Brass")
# three orthogonal bands + pivot pins to G5
for Rm in (np.eye(3), rot_to((1, 0, 0), (0, 1, 0)), rot_to((0, 1, 0), (0, 0, 1))):
    for mat, poly in (("Gold", [(0.28, -0.55), (0.28, 0.55)]), ("Gold", [(0.28, 0.55), (-0.28, 0.55)]),
                      ("Gold", [(-0.28, 0.55), (-0.28, -0.55)]), ("Gold", [(-0.28, -0.55), (0.28, -0.55)])):
        v, q, uv = sweep(poly, 15.6, 240)
        b.add(v, q, mat, uv=uv, R=Rm)
g5r, g5t = RINGS[4][1], RINGS[4][3]
for sgn in (-1, 1):
    add_cyl(b, (sgn * 15.2, 0, 0), (sgn * (g5r - g5t / 2 + 0.5), 0, 0), 0.42, "Silver", n=16)
    add_cyl(b, (sgn * 15.0, 0, 0), (sgn * 17.2, 0, 0), 1.15, "DarkMetal", n=24)
    add_cyl(b, (sgn * (g5r - g5t / 2 - 1.6), 0, 0), (sgn * (g5r - g5t / 2 + 0.2), 0, 0), 1.3, "Brass", n=24)
cage = b.build("MECH_Cage")
cage.parent = parent
cage.rotation_mode = 'ZYX'
cage.rotation_euler = (0.0, math.radians(15.0), math.pi / 2)
cage["gim_axis"] = 1
cage["gim_dps"] = 6.0
cage["gim_phase"] = 15.0
b = B()
add_sphere(b, (0, 0, 0), C.CORE_R, "CoreGlow", sub=4)
core = b.build("MECH_Core", sharp=180)
core.visible_shadow = False
K.log("cage tris", K.tri_count([cage]))

# ------------------------------------------------------------------ exterior orbit ring
def ext_ring(name, r, w, t, nseg, lattice=True, truss=False):
    b = B()
    f = 0.2 * w
    c = 0.3 * t
    P = [(t / 2, -w / 2), (t / 2, -w / 2 + f), (t / 2 - c, -w / 2 + f), (t / 2 - c, w / 2 - f), (t / 2, w / 2 - f), (t / 2, w / 2),
         (-t / 2, w / 2), (-t / 2, w / 2 - f), (-t / 2 + c, w / 2 - f), (-t / 2 + c, -w / 2 + f), (-t / 2, -w / 2 + f), (-t / 2, -w / 2)]
    segs = [("Gold", [0, 1, 2]), ("RingWindows", [2, 3]), ("Gold", [3, 4, 5]), ("RingEngrave", [5, 6]),
            ("Gold", [6, 7, 8]), ("RingWindows", [8, 9]), ("Gold", [9, 10, 11]), ("RingEngrave", [11, 0])]
    for mat, idx in segs:
        v, q, uv = sweep([P[i] for i in idx], r, nseg)
        b.add(v, q, mat, uv=uv)
    if lattice:
        # two thin rails above/below, tied to the main ring by a zig-zag truss
        off = w / 2 + 3.2
        for sgn in ((-1, 1) if truss else ()):
            u = np.linspace(0, 2 * math.pi, 360, endpoint=False)
            for rr in (r - 1.3, r + 1.3):
                pts = np.stack([rr * np.cos(u), rr * np.sin(u), np.full_like(u, sgn * off)], -1)
                v, q = tube(pts, 0.20, sides=6, ref=[(0, 0, 1)] * 360)
                b.add(v, q, "Brass")
            n_t = 180
            for k in range(n_t):
                a0 = 2 * math.pi * k / n_t
                a1 = 2 * math.pi * (k + 0.5) / n_t
                a2 = 2 * math.pi * (k + 1) / n_t
                for (aa, ab, ra, rb, za, zb) in ((a0, a1, r - 1.3, r + 1.3, off, off), (a1, a2, r + 1.3, r - 1.3, off, off),
                                                 (a0, a0, r - 1.3, r - t / 2, off, w / 2), (a1, a1, r + 1.3, r + t / 2, off, w / 2)):
                    v, q, caps = cyl((ra * math.cos(aa), ra * math.sin(aa), sgn * za), (rb * math.cos(ab), rb * math.sin(ab), sgn * zb), 0.085, n=4)
                    b.add(v, q, "Brass")
        # station modules with lamps every 30 degrees
        for k in range(12):
            a = math.radians(k * 30 + 7)
            Rm = rot_z(a)
            big = (k % 3 == 0)
            hx, hy, hz = (t / 2 + (1.3 if big else 0.7), 4.2 if big else 2.4, w / 2 + (1.5 if big else 0.8))
            add_box(b, (r, 0, 0), (hx, hy, hz), "DarkMetal", R=Rm)
            for yy in (-hy, 0, hy):
                add_box(b, (r, yy, 0), (hx + 0.18, 0.2, hz + 0.18), "Gold", R=Rm)
            for sz in (-1, 1):
                for sy in (-1, -0.33, 0.33, 1):
                    add_sphere(b, (r + hx + 0.1, sy * hy * 0.8, sz * hz * 0.6), 0.30, "Lamp", sub=1, R=Rm)
                    add_sphere(b, (r - hx - 0.1, sy * hy * 0.8, sz * hz * 0.6), 0.30, "Lamp", sub=1, R=Rm)
            if big:
                add_cyl(b, (r, 0, hz), (r, 0, hz + 7.5), 0.5, "Brass", n=10, rad1=0.08, R=Rm)
                add_cyl(b, (r, 0, -hz), (r, 0, -hz - 7.5), 0.5, "Brass", n=10, rad1=0.08, R=Rm)
                add_sphere(b, (r, 0, hz + 7.7), 0.45, "Lamp", sub=1, R=Rm)
                add_sphere(b, (r, 0, -hz - 7.7), 0.45, "Lamp", sub=1, R=Rm)
    return b.build(name)


ext = ext_ring("MECH_ExtRing", 146.0, 5.2, 2.6, 1440)
ext.rotation_mode = 'ZXY'
ext.rotation_euler = (math.radians(30.0), math.radians(14.0), 0.0)
ext["spin_dps"] = 2.6
wire = ext_ring("MECH_ExtWire", 158.0, 1.1, 0.8, 720, lattice=False)
wire.rotation_mode = 'ZXY'
wire.rotation_euler = (math.radians(-18.0), math.radians(-34.0), 0.0)
wire["spin_dps"] = -3.6
K.log("ext ring tris", K.tri_count([ext, wire]))
K.log("MECH total tris %d" % K.tri_count())
K.save_blend(K.P("blend", "mech.blend"))
K.log("MECH DONE")
