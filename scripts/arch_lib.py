"""Geometry helpers for build_arch.py: quad-only builder + primitives + sphere mappings."""
import numpy as np, math
import common as K, config as C, mats

RI = C.HULL_IN
TAU = 2 * math.pi


class B:
    """Accumulates quads with material names and a per-vertex 'rnd' float."""

    def __init__(s):
        s.v, s.f, s.m, s.r, s.n, s.names = [], [], [], [], 0, []

    def mi(s, name):
        if name not in s.names:
            s.names.append(name)
        return s.names.index(name)

    def add(s, v, f, mat, rnd=0.0):
        v = np.asarray(v, np.float32).reshape(-1, 3)
        f = np.asarray(f, np.int64).reshape(-1, 4)
        if not len(f):
            return
        s.v.append(v)
        s.f.append(f + s.n)
        s.m.append(np.full(len(f), s.mi(mat), np.int32))
        s.r.append(np.full(len(v), rnd, np.float32) if np.ndim(rnd) == 0 else np.asarray(rnd, np.float32))
        s.n += len(v)

    def arrays(s):
        if not s.v:
            return np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int64), np.zeros(0, np.int32), np.zeros(0, np.float32)
        return np.concatenate(s.v), np.concatenate(s.f), np.concatenate(s.m), np.concatenate(s.r)

    def merge(s, o, fn=None, flip=None, rnd=None):
        V, F, M, R = o.arrays()
        if not len(F):
            return
        if fn is not None:
            if flip is None:
                flip = is_flip(fn, V.mean(0).astype(np.float64))
            V = fn(V.astype(np.float64))
        if flip:
            F = F[:, ::-1]
        remap = np.array([s.mi(n) for n in o.names], np.int32)
        s.v.append(np.asarray(V, np.float32))
        s.f.append(F + s.n)
        s.m.append(remap[M])
        s.r.append(R if rnd is None else np.asarray(rnd, np.float32))
        s.n += len(V)

    def merge_instances(s, o, Vinst, flip=False, Rinst=None):
        V, F, M, R = o.arrays()
        k = Vinst.shape[0]
        n = len(V)
        if k == 0 or not len(F):
            return
        if flip:
            F = F[:, ::-1]
        FF = (F[None] + (np.arange(k) * n)[:, None, None]).reshape(-1, 4) + s.n
        remap = np.array([s.mi(nm) for nm in o.names], np.int32)
        s.v.append(Vinst.reshape(-1, 3).astype(np.float32))
        s.f.append(FF)
        s.m.append(np.tile(remap[M], k))
        s.r.append(np.tile(R, k) if Rinst is None else Rinst.reshape(-1).astype(np.float32))
        s.n += k * n

    def cut_open(s, thresh):
        """Drop faces whose centroid direction lies inside the big opening."""
        V, F, M, R = s.arrays()
        c = V[F].mean(1).astype(np.float64)
        keep = C.open_field(c / np.linalg.norm(c, axis=1, keepdims=True)) >= thresh
        s.v, s.f, s.m, s.r, s.n = [V], [F[keep]], [M[keep]], [R], len(V)

    def tris(s):
        return 2 * sum(len(f) for f in s.f)

    def obj(s, name, col, sharp=30):
        V, F, M, R = s.arrays()
        u, inv = np.unique(F, return_inverse=True)
        V = V[u]
        R = R[u]
        F = inv.reshape(F.shape)
        ml = [mats.get(n) if not n.startswith("ARCH_") else arch_mat(n) for n in s.names]
        ob = K.obj_np(name, col, V, F.astype(np.int32), attrs={"rnd": ('POINT', R)}, mats=ml, mat_idx=M, sharp_angle=sharp)
        return ob


_ARCH_MATS = {}


def arch_mat(name):
    import bpy
    m = bpy.data.materials.get(name)
    if m is None:
        m = _ARCH_MATS[name](name)
    return m


def is_flip(fn, p0):
    e = 1e-3
    P = np.array([p0, p0 + [e, 0, 0], p0 + [0, e, 0], p0 + [0, 0, e]], dtype=np.float64)
    Q = np.asarray(fn(P), dtype=np.float64)
    return np.linalg.det(np.stack([Q[1] - Q[0], Q[2] - Q[0], Q[3] - Q[0]])) < 0


# ------------------------------------------------------------------ primitives
_BF = {'x': (0, 4, 6, 2), 'X': (1, 3, 7, 5), 'y': (0, 1, 5, 4), 'Y': (2, 6, 7, 3), 'z': (0, 2, 3, 1), 'Z': (4, 5, 7, 6)}


def boxes(c0, c1, faces='xXyYzZ'):
    c0 = np.atleast_2d(np.asarray(c0, float))
    c1 = np.atleast_2d(np.asarray(c1, float))
    lo = np.minimum(c0, c1)
    hi = np.maximum(c0, c1)
    k = len(lo)
    idx = np.arange(8)
    sel = np.stack([idx & 1, (idx >> 1) & 1, (idx >> 2) & 1], -1).astype(bool)
    v = np.where(sel[None], hi[:, None, :], lo[:, None, :])
    f = np.array([_BF[c] for c in faces])
    F = (f[None] + (np.arange(k) * 8)[:, None, None]).reshape(-1, 4)
    return v.reshape(-1, 3), F


def pol(v):
    v = np.asarray(v, float)
    return np.stack([v[:, 0] * np.cos(v[:, 1]), v[:, 0] * np.sin(v[:, 1]), v[:, 2]], -1)


def polar_boxes(r0, r1, th, dth, z0, z1, faces='xXyYzZ'):
    th = np.atleast_1d(np.asarray(th, float))
    k = len(th)
    bc = lambda a: np.broadcast_to(np.asarray(a, float), (k,))
    v, f = boxes(np.stack([bc(r0), th - bc(dth), bc(z0)], -1), np.stack([bc(r1), th + bc(dth), bc(z1)], -1), faces)
    return pol(v), f


def lathe(prof, nseg, closed=False, a0=0.0, a1=None):
    """Surface of revolution about Z. prof: (m,2) = (radius, z), listed CCW in the (r,z) plane for outward normals."""
    prof = np.asarray(prof, float)
    m = len(prof)
    full = a1 is None
    na = nseg if full else nseg + 1
    ang = a0 + (np.arange(na) / nseg) * (TAU if full else (a1 - a0))
    r = np.broadcast_to(prof[:, 0][None, :], (na, m))
    z = np.broadcast_to(prof[:, 1][None, :], (na, m))
    v = np.stack([r * np.cos(ang)[:, None], r * np.sin(ang)[:, None], z], -1).reshape(-1, 3)
    i = np.arange(nseg)
    i2 = (i + 1) % na if full else i + 1
    j = np.arange(m if closed else m - 1)
    j2 = (j + 1) % m
    I, J = np.meshgrid(i, j, indexing='ij')
    I2 = i2[I]
    J2 = j2[J]
    F = np.stack([I * m + J, I2 * m + J, I2 * m + J2, I * m + J2], -1).reshape(-1, 4)
    return v, F


def sweep_bar(pts, width, z0, z1, closed=False, faces='TLR'):
    """Rectangular bar along a 2D polyline in the xy plane, extruded z0..z1 (top face normal +z)."""
    pts = np.asarray(pts, float)
    n = len(pts)
    if closed:
        d = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    else:
        d = np.gradient(pts, axis=0)
    d = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([-d[:, 1], d[:, 0]], -1)
    w = np.broadcast_to(np.asarray(width, float), (n,))[:, None] * 0.5
    Lp = pts + nrm * w
    Rp = pts - nrm * w
    za = np.broadcast_to(np.asarray(z0, float), (n,))
    zb = np.broadcast_to(np.asarray(z1, float), (n,))
    v = np.concatenate([np.c_[Lp, zb], np.c_[Rp, zb], np.c_[Lp, za], np.c_[Rp, za]])
    i = np.arange(n if closed else n - 1)
    i2 = (i + 1) % n
    fl = []
    if 'T' in faces:
        fl.append(np.stack([n + i, n + i2, i2, i], -1))
    if 'L' in faces:
        fl.append(np.stack([i, i2, 2 * n + i2, 2 * n + i], -1))
    if 'R' in faces:
        fl.append(np.stack([n + i2, n + i, 3 * n + i, 3 * n + i2], -1))
    if 'B' in faces:
        fl.append(np.stack([2 * n + i, 2 * n + i2, 3 * n + i2, 3 * n + i], -1))
    if 'E' in faces and not closed:
        fl.append(np.array([[0, 2 * n, 3 * n, n], [n - 1, 2 * n - 1, 4 * n - 1, 3 * n - 1]]))
    return v, np.concatenate(fl)


def fill_strip(Lp, Rp, z):
    Lp = np.asarray(Lp, float)
    Rp = np.asarray(Rp, float)
    n = len(Lp)
    zz = np.broadcast_to(np.asarray(z, float), (n,))
    v = np.concatenate([np.c_[Lp, zz], np.c_[Rp, zz]])
    i = np.arange(n - 1)
    return v, np.stack([n + i, n + i + 1, i + 1, i], -1)


def annulus(r0, r1, nseg, z, nr=1):
    rr = np.linspace(r0, r1, nr + 1)
    th = np.arange(nseg) / nseg * TAU
    Rg, T = np.meshgrid(rr, th, indexing='ij')
    v = np.stack([Rg * np.cos(T), Rg * np.sin(T), np.full_like(Rg, z)], -1).reshape(-1, 3)
    j = np.arange(nr)
    i = np.arange(nseg)
    J, I = np.meshgrid(j, i, indexing='ij')
    I2 = (I + 1) % nseg
    F = np.stack([J * nseg + I, (J + 1) * nseg + I, (J + 1) * nseg + I2, J * nseg + I2], -1).reshape(-1, 4)
    return v, F


def arch_half(a, c, n):
    """Right half of a pointed arch from spring (a,0) to apex (0,h). Arc centre (-c,0), radius a+c."""
    R = a + c
    t1 = math.acos(c / R)
    t = np.linspace(0, t1, n + 1)
    return np.stack([-c + R * np.cos(t), R * np.sin(t)], -1)


def circ(r, n, c=(0, 0), a0=0.0):
    t = a0 + np.arange(n) / n * TAU
    return np.stack([c[0] + r * np.cos(t), c[1] + r * np.sin(t)], -1)


def diamond(c, r, h, axis=2):
    v, f = lathe([(0.01, -h), (r, 0.0), (0.01, h)], 4)
    if axis == 1:
        v = v[:, [0, 2, 1]]
        f = f[:, ::-1]
    return v + np.asarray(c, float), f


def mir(v, f):
    v = np.array(v, float)
    v[:, 0] *= -1
    return v, np.asarray(f)[:, ::-1]


def add_sym(b, v, f, mat, rnd=0.0):
    b.add(v, f, mat, rnd)
    v2, f2 = mir(v, f)
    b.add(v2, f2, mat, rnd)


def compact(V, F):
    u, inv = np.unique(F, return_inverse=True)
    return V[u], inv.reshape(F.shape)


# ------------------------------------------------------------------ mappings
def sph(lon, lat, r):
    return np.stack([r * np.cos(lat) * np.cos(lon), r * np.cos(lat) * np.sin(lon), r * np.sin(lat) + 0 * lon], -1)


def cap_map(P, Rm=None, sign=1.0, R0=RI):
    """(a, b, w): azimuthal-equidistant plane coords (metres) around +Z (or the rotated axis), w = depth inward."""
    P = np.asarray(P, float)
    rho = np.hypot(P[:, 0], P[:, 1])
    th = np.arctan2(P[:, 1], P[:, 0])
    phi = rho / RI
    r = R0 - P[:, 2]
    loc = np.stack([r * np.sin(phi) * np.cos(th), r * np.sin(phi) * np.sin(th), sign * r * np.cos(phi)], -1)
    return loc @ Rm.T if Rm is not None else loc


def rotz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def xf(R=None, t=(0, 0, 0), s=None):
    t = np.asarray(t, float)

    def fn(V):
        V = np.asarray(V, float)
        if s is not None:
            V = V * np.asarray(s, float)
        if R is not None:
            V = V @ np.asarray(R).T
        return V + t
    return fn


def pinnacle(h, r, lamp=True, mat='Gold'):
    b = B()
    p = [(r, 0), (r, 0.5 * h), (1.3 * r, 0.53 * h), (1.3 * r, 0.6 * h), (0.75 * r, 0.64 * h), (0.04 * r, h)]
    v, f = lathe(p, 4, a0=math.pi / 4)
    b.add(v, f, mat)
    if lamp:
        v, f = lathe([(0.02, h - 0.15 * r), (0.5 * r, h + 0.3 * r), (0.02, h + 0.75 * r)], 4, a0=math.pi / 4)
        b.add(v, f, 'Lamp')
    return b


def gear(Rp, N, z0, z1, hub_r, bore_r, nsp, mat='Brass', phase=0.0, trim='Gold', hubmat='Gold'):
    """Spur gear about Z, tooth 0 centred at angle `phase`."""
    b = B()
    m = 2 * Rp / N
    Rt = Rp + 0.9 * m
    Rr = Rp - 1.1 * m
    rim = max(1.0, 0.13 * Rp)
    Ri = Rr - rim
    na = 4 * N
    k = np.arange(na)
    sub = k % 4
    ang = (k // 4 + np.array([-0.27, -0.13, 0.13, 0.27])[sub]) * TAU / N + phase
    rad = np.where((sub == 1) | (sub == 2), Rt, Rr)
    r = np.stack([np.full(na, Ri), rad, rad, np.full(na, Ri)], 1)
    z = np.broadcast_to(np.array([z0, z0, z1, z1])[None], (na, 4))
    v = np.stack([r * np.cos(ang)[:, None], r * np.sin(ang)[:, None], z], -1).reshape(-1, 3)
    I, J = np.meshgrid(k, np.arange(4), indexing='ij')
    I2 = (I + 1) % na
    J2 = (J + 1) % 4
    b.add(v, np.stack([I * 4 + J, I2 * 4 + J, I2 * 4 + J2, I * 4 + J2], -1).reshape(-1, 4), mat)
    t = z1 - z0
    za, zb = z0 + 0.2 * t, z1 - 0.2 * t
    sw = max(0.3, 0.06 * Rp)
    sv, sf = boxes([hub_r - 0.1, -sw, za], [Ri + 0.1, sw, zb], 'yYzZ')
    for i in range(nsp):
        b.add(sv @ rotz(phase + (i + 0.5) * TAU / nsp).T, sf, mat)
    if Ri - hub_r > 5:
        rm = hub_r + 0.55 * (Ri - hub_r)
        v, f = lathe([(rm - 0.35, za), (rm + 0.35, za), (rm + 0.35, zb), (rm - 0.35, zb)], 64, closed=True)
        b.add(v, f, mat)
    v, f = lathe([(bore_r, z0 - 0.3), (hub_r, z0 - 0.3), (hub_r, z1 + 0.3), (hub_r * 0.82, z1 + 0.6), (bore_r, z1 + 0.6)], 32, closed=True)
    b.add(v, f, hubmat)
    v, f = lathe([(Rr - 0.12, z1), (Rr - 0.12, z1 + 0.12), (Ri + 0.1, z1 + 0.12), (Ri + 0.1, z1)], max(48, N))
    b.add(v, f, trim)
    v, f = lathe([(Ri + 0.1, z0), (Ri + 0.1, z0 - 0.12), (Rr - 0.12, z0 - 0.12), (Rr - 0.12, z0)], max(48, N))
    b.add(v, f, trim)
    return b


def mesh_phase(alpha, R0, rz0, R1, N1):
    """Rotation for gear 1 (centre in direction alpha from gear 0) so teeth interleave."""
    return alpha + math.pi - (R0 / R1) * (rz0 - alpha) - math.pi / N1
