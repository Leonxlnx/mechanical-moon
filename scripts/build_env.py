"""ENVIRONMENT module: stormy night ocean, rocky shore, distant islands, sky world.
Run headless:  blender -b --factory-startup -P build_env.py
Output: blend/env.blend  (collection ENV, world ENV_World, materials ENV_*). No lights / volumes / cameras.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, math, time
import numpy as np
import common as K, config as C, mats as M

N, L = M.N, M.L
T0 = time.time()

# ============================================================== tunables
OCEAN_CORE = (-160.0, 160.0, -366.0, 72.0)   # x0, x1, y0, y1 of the dense displaced water grid
OCEAN_D = 1.2                                # core grid spacing (m)
OCEAN_FADE = 190.0                           # displacement fades to 0 over this distance outside the core
SWELL_STD = 0.62                              # target RMS height of the big swell (m)  -> Hs ~ 5 m
CHOP_STD = 0.24                              # target RMS height of the chop layer (m)
FOLD_FRAC = 0.012                            # fraction of the swell surface allowed to start folding (sets choppiness)
FOAM_FRAC = 0.17                             # fraction of the sea covered by crest foam
TIME_SCALE = 0.60                            # ocean seconds per film second (slightly slowed = heavier feel)
WAVE_DIR = math.radians(-100.0)              # swell travels towards the shore (-Y), slightly oblique

NEAR_STACKS = [  # cx, cy, rx, ry, H, seed, rot   (sea stacks just off the shore)
    (-96, -292, 7.0, 5.5, 9.0, 21, 0.3), (-71, -276, 4.0, 3.5, 6.0, 22, 0.0), (22, -288, 6.0, 7.5, 11.0, 23, 0.5),
    (50, -268, 4.0, 4.0, 5.0, 24, 0.0), (-128, -270, 8.0, 6.0, 13.0, 25, 1.0), (88, -296, 9.0, 6.5, 8.0, 26, 0.2),
    (-6, -301, 3.2, 2.6, 2.6, 27, 0.0), (-150, -300, 6.0, 9.0, 7.0, 28, 0.7), (120, -280, 5.0, 4.0, 6.5, 29, 0.1),
]
MID_STACKS = [   # further out, all > 220 m from world origin
    (-250, -150, 16, 12, 28, 31, 0.4), (-285, -118, 9, 8, 17, 32, 0.0), (255, -175, 14, 18, 24, 33, 0.2),
    (300, -140, 8, 8, 14, 34, 0.0), (-211, 130, 18, 13, 30, 35, 0.9), (-236, 150, 9, 9, 16, 36, 0.0),
    (235, 101, 15, 20, 23, 37, 0.3), (262, 76, 8, 7, 12, 38, 0.0),
]
ISLANDS = [      # distant headlands / islands (hazy silhouettes)
    (-380, 420, 200, 90, 75, 41, 0.3), (480, 560, 240, 110, 95, 42, -0.4), (-1100, 300, 300, 150, 125, 43, 1.2),
    (1200, -100, 280, 150, 110, 44, 1.4), (150, 1500, 380, 130, 100, 45, 0.1), (700, -650, 200, 120, 80, 46, -0.6),
    (-820, -520, 260, 120, 90, 47, 0.5),
]


def sstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def n2(x, y, scale, octaves=4, seed=0, ridged=False, gain=0.5):
    p = np.stack([x / scale, y / scale, np.full_like(x, seed * 0.371)], -1)
    return K.fbm3(p, octaves, seed=seed, ridged=ridged, gain=gain).astype(np.float64)


def terrace(h, x, y, step, amount, seed):
    tilt = 0.10 * x + 0.04 * y + 0.8 * step * n2(x, y, 22 * step, 2, seed=seed)
    q = (h + tilt) / step
    fq = np.floor(q)
    st = fq + sstep(0.62, 1.0, q - fq)
    return h * (1 - amount) + (st * step - tilt) * amount


def cell2(x, y, size, seed):
    """2D cellular noise on a warped domain: returns (random value per cell 0..1, distance to cell border proxy)."""
    wx = x + 0.30 * size * n2(x, y, size * 1.7, 2, seed=seed + 5)
    wy = y + 0.30 * size * n2(x, y, size * 1.7, 2, seed=seed + 6)
    px, py = wx / size, wy / size
    ix, iy = np.floor(px).astype(np.int64), np.floor(py).astype(np.int64)
    best = np.full(x.shape, 1e9)
    second = np.full(x.shape, 1e9)
    rid = np.zeros(x.shape)
    z0 = np.zeros_like(ix)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            cx, cy = ix + dx, iy + dy
            hx = K._hash3(cx, cy, z0, seed)
            hy = K._hash3(cx, cy, z0 + 1, seed)
            hr = K._hash3(cx, cy, z0 + 2, seed)
            d = np.hypot(cx + hx - px, cy + hy - py)
            closer = d < best
            second = np.where(closer, best, np.minimum(second, d))
            rid = np.where(closer, hr, rid)
            best = np.where(closer, d, best)
    return rid, second - best


# ============================================================== height fields
CAMX, CAMY, CAMZ = C.SHORE_CAM
_vd = np.array([C.SHORE_CAM_TARGET[0] - CAMX, C.SHORE_CAM_TARGET[1] - CAMY]); _vd /= np.linalg.norm(_vd)
# hero crags framing the shore camera: cx, cy, radius, extra height
CRAGS = [(-50.0, -325.0, 9.5, 7.5), (-27.5, -327.0, 7.5, 6.0), (-88.0, -327.0, 8.0, 5.5), (10.0, -326.0, 9.0, 6.0),
         (-113.0, -330.0, 6.0, 4.0), (30.0, -330.0, 5.0, 3.5), (-68.0, -322.0, 5.0, 3.0), (-8.0, -322.0, 5.0, 2.5)]
# hero silhouette as seen from the shore camera: azimuth (deg, right positive, relative to the view axis) -> max elevation (deg)
DOLLY_MAX_SLOPE = 0.16   # tan(max elevation) of shore rocks seen from the dolly corridor (y = SHORE_CAM y, z = 9)
HERO_AZ = [-60, -36, -25, -15, -7, 8, 18, 28, 37, 60]
HERO_EL = [15.0, 13.0, 9.5, 3.5, -2.5, -2.5, 2.5, 6.5, 8.5, 10.0]


def shore_height(x, y):
    side = sstep(115, 200, x) + (1 - sstep(-265, -175, x))
    coast = -320.5 + 6.5 * n2(x, 0 * x, 60, 3, seed=3) + 3.0 * n2(x, 0 * x, 17, 3, seed=4) - 190 * side
    s = coast - y + 3.5 * n2(x, y, 25, 3, seed=5)
    h = -8 + 13 * sstep(-13, 3, s) + 1.6 * sstep(3, 26, s) + 26 * sstep(26, 100, s)
    back = sstep(100, 138, s)
    h = h * (1 - back) - 8 * back
    land = sstep(-6, 4, s)
    h += land * (1.3 * n2(x, y, 13, 4, seed=7, ridged=True) + 0.4 * n2(x, y, 3.5, 3, seed=8))
    # jagged blocks between the camera corridor and the sea
    band = sstep(0, 5, s) * (1 - sstep(11, 17, s))
    teeth = sstep(0.05, 0.55, n2(x, y, 11, 3, seed=9, ridged=True))
    h += band * 3.6 * teeth
    for i, (cx, cy, rad, hh) in enumerate(CRAGS):
        d = np.hypot(x - cx, y - cy) + 0.22 * rad * n2(x, y, 0.8 * rad, 3, seed=60 + i)
        h += hh * (1 - sstep(rad * 0.5, rad, d))
    # fractures / gullies
    cr = n2(x * 1.0, y * 2.3, 8, 2, seed=12, ridged=True)
    h -= land * 2.0 * sstep(0.80, 0.97, cr)
    # hero silhouette clamp (rock masses in the lower corners of the hero frame, moon and light streak stay clear)
    vx, vy = x - CAMX, y - CAMY
    along = vx * _vd[0] + vy * _vd[1]
    az = np.degrees(np.arctan2(vx * _vd[1] - vy * _vd[0], along))
    dist = np.hypot(vx, vy)
    el = np.interp(az, HERO_AZ, HERO_EL) + 1.3 * n2(x, y, 5, 2, seed=14) * sstep(3, 10, np.abs(az - 0.5))
    hmax = CAMZ + dist * np.tan(np.radians(el)) + 30 * sstep(60, 110, dist)
    front = sstep(-1.0, 1.5, along)
    h -= front * np.maximum(h - hmax, 0)
    # dolly path: from anywhere on the shore corridor the rocks in front stay below ~9 deg elevation
    inx = sstep(-142, -126, x) * (1 - sstep(46, 62, x))
    hmax2 = CAMZ + 0.6 + DOLLY_MAX_SLOPE * np.clip(y - CAMY, 0, None)
    h -= inx * sstep(-1.0, 1.0, y - CAMY) * np.maximum(h - hmax2, 0)
    # camera corridor along the shore (dolly path): keep the ground under z = 7
    cor = (1 - sstep(1.5, 4.5, np.abs(y - CAMY))) * sstep(-128, -114, x) * (1 - sstep(34, 48, x))
    h -= cor * np.maximum(h - 6.9, 0)
    # strata: big ledges + thin beds
    h = terrace(h, x, y, 2.9, 0.85 * land, 11)
    h = terrace(h, x, y, 0.7, 0.5 * land, 13)
    r1, e1 = cell2(x, y, 4.4, 71)
    r2, e2 = cell2(x, y, 1.6, 72)
    h += land * (1.6 * (r1 - 0.5) * sstep(0.0, 0.22, e1) + 0.6 * (r2 - 0.5) * sstep(0.0, 0.3, e2)
                 + 0.25 * n2(x, y, 2.6, 3, seed=15, ridged=True))
    h -= land * (0.8 * (1 - sstep(0.0, 0.10, e1)) + 0.28 * (1 - sstep(0.0, 0.12, e2)))
    h += sstep(30, 70, s) * (1 - back) * 9.0 * n2(x, y, 38, 4, seed=17, ridged=True)
    h -= cor * np.maximum(h - 7.0, 0)
    cor2 = (1 - sstep(1.0, 3.0, dist))
    h -= cor2 * np.maximum(h - 7.1, 0)
    return h


def stack_height(x, y, cx, cy, rx, ry, H, seed, rot=0.0, cliff=0.55, step=None, base=-8.0):
    c, s_ = math.cos(rot), math.sin(rot)
    u = ((x - cx) * c + (y - cy) * s_) / rx
    v = (-(x - cx) * s_ + (y - cy) * c) / ry
    sc = max(rx, ry)
    r = np.hypot(u, v) + 0.26 * n2(x, y, sc * 0.6, 3, seed=seed) + 0.10 * n2(x, y, sc * 0.15, 2, seed=seed + 1)
    prof = 1 - sstep(cliff, 1.0, r)
    top = 0.68 + 0.32 * n2(x, y, sc * 0.45, 4, seed=seed + 2, ridged=True)
    h = base + (H - base) * prof * top
    cr = n2(x * 2.0, y, sc * 0.35, 2, seed=seed + 3, ridged=True)
    h -= prof * 0.12 * H * sstep(0.78, 0.97, cr)
    step = step or max(0.9, H / 9.0)
    h = terrace(h, x, y, step, 0.75 * sstep(0.0, 0.3, prof), seed + 4)
    r1, e1 = cell2(x, y, sc * 0.30, seed + 7)
    r2, e2 = cell2(x, y, sc * 0.11, seed + 8)
    w = sstep(0.0, 0.25, prof)
    h += w * H * (0.16 * (r1 - 0.5) * sstep(0.0, 0.22, e1) + 0.06 * (r2 - 0.5) * sstep(0.0, 0.3, e2))
    h -= w * H * (0.07 * (1 - sstep(0.0, 0.10, e1)) + 0.025 * (1 - sstep(0.0, 0.12, e2)))
    return h


def near_rock_height(x, y):
    """Rock height (z) of shore + near stacks at arbitrary points; -30 = no rock. Used for foam masks."""
    h = np.full(x.shape, -30.0)
    m = (x > -300) & (x < 240) & (y > -480) & (y < -270)
    if m.any():
        h[m] = shore_height(x[m], y[m])
    for (cx, cy, rx, ry, H, seed, rot) in NEAR_STACKS + MID_STACKS:
        R_ = 1.6 * max(rx, ry)
        m = (np.abs(x - cx) < R_) & (np.abs(y - cy) < R_)
        if m.any():
            h[m] = np.maximum(h[m], stack_height(x[m], y[m], cx, cy, rx, ry, H, seed, rot))
    return h


# ============================================================== mesh helpers
def graded_axis(lo, hi, d, far_lo, far_hi, g):
    n = int(round((hi - lo) / d))
    core = lo + np.arange(n + 1) * d

    def grow(limit):
        out, x, s = [], 0.0, d
        while x < limit:
            s *= g
            x += s
            out.append(x)
        return np.array(out)
    return np.concatenate([lo - grow(lo - far_lo)[::-1], core, core[-1] + grow(far_hi - core[-1])])


def grid_quads(nx, ny):
    idx = np.arange(nx * ny).reshape(ny, nx)
    return np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)


def patch_mesh(name, col, xs, ys, hfn, step, mat, trim=-7.0, jitter=0.3, sharp=42):
    X, Y = np.meshgrid(xs, ys)
    x, y = X.ravel(), Y.ravel()
    z = hfn(x, y)
    lay = np.floor((z + 0.10 * x + 0.04 * y) / step)
    p = np.stack([x / (5.0 * step), y / (5.0 * step), lay * 3.17], -1)
    land = sstep(-3, 0, z)
    jx = K.noise3(p, 101) * jitter * land
    jy = K.noise3(p + 40.5, 102) * jitter * land
    verts = np.stack([x + jx, y + jy, z], -1)
    quads = grid_quads(len(xs), len(ys))
    keep = z[quads].max(axis=1) > trim
    quads = quads[keep]
    used = np.zeros(len(verts), bool)
    used[quads.ravel()] = True
    remap = np.cumsum(used) - 1
    ob = K.obj_np(name, col, verts[used], remap[quads], mats=[mat], sharp_angle=sharp)
    return ob


# ============================================================== shader helpers
def _set(nt, sock, v):
    if v is None:
        return
    if isinstance(v, (int, float)):
        sock.default_value = v
    elif isinstance(v, (tuple, list)):
        sock.default_value = v
    else:
        nt.links.new(v, sock)


def fmath(nt, op, a, b=None, c=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        _set(nt, n.inputs[i], v)
    return n.outputs[0]


def vmath(nt, op, a, b=None, scale=None):
    n = nt.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    _set(nt, n.inputs[0], a)
    _set(nt, n.inputs[1], b)
    if scale is not None:
        _set(nt, n.inputs[3], scale)
    return n.outputs[1] if op in ('DOT_PRODUCT', 'LENGTH', 'DISTANCE') else n.outputs[0]


def mixrgb(nt, fac, a, b, blend='MIX'):
    n = nt.nodes.new("ShaderNodeMixRGB")
    n.blend_type = blend
    _set(nt, n.inputs[0], fac)
    _set(nt, n.inputs[1], a)
    _set(nt, n.inputs[2], b)
    return n.outputs[0]


def maprange(nt, v, a, b, c=0.0, d=1.0, interp='SMOOTHSTEP'):
    n = nt.nodes.new("ShaderNodeMapRange")
    n.interpolation_type = interp
    n.clamp = True
    _set(nt, n.inputs["Value"], v)
    for k, val in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
        _set(nt, n.inputs[k], val)
    return n.outputs["Result"]


def noise(nt, vec, scale, detail, rough=0.5, dim='3D', w=None, lac=2.0, out="Fac"):
    n = nt.nodes.new("ShaderNodeTexNoise")
    n.noise_dimensions = dim
    _set(nt, n.inputs["Vector"], vec)
    if dim == '4D':
        _set(nt, n.inputs["W"], w)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    n.inputs["Lacunarity"].default_value = lac
    return n.outputs[out]


def comb(nt, x, y, z):
    n = nt.nodes.new("ShaderNodeCombineXYZ")
    _set(nt, n.inputs[0], x); _set(nt, n.inputs[1], y); _set(nt, n.inputs[2], z)
    return n.outputs[0]


def sepxyz(nt, v):
    n = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(v, n.inputs[0])
    return n.outputs[0], n.outputs[1], n.outputs[2]


def attr(nt, name, out="Fac"):
    n = nt.nodes.new("ShaderNodeAttribute")
    n.attribute_name = name
    return n.outputs[out]


def time_node(nt):
    """Value node 'ENV_Time' = film time in seconds, driven by the frame number (never stops)."""
    n = nt.nodes.new("ShaderNodeValue")
    n.name = "ENV_Time"
    n.label = "ENV_Time (s)"
    fc = nt.driver_add('nodes["ENV_Time"].outputs[0].default_value')
    fc.driver.type = 'SCRIPTED'
    fc.driver.expression = "frame/30.0"
    return n.outputs[0]


# ============================================================== materials
def mat_water():
    m = bpy.data.materials.new("ENV_Water")
    nt = M.clear(m)
    out = N(nt, "ShaderNodeOutputMaterial")
    b = N(nt, "ShaderNodeBsdfPrincipled")
    b.name = "ENV_WaterBSDF"
    geo = N(nt, "ShaderNodeNewGeometry")
    t = time_node(nt)
    dist = N(nt, "ShaderNodeCameraData").outputs["View Distance"]
    a_foam, a_fade, a_shore = attr(nt, "foam"), attr(nt, "fade"), attr(nt, "shore")
    sx, sy, sz = sepxyz(nt, geo.outputs["Position"])
    p2 = comb(nt, sx, sy, 0.0)
    pa = vmath(nt, 'ADD', p2, comb(nt, fmath(nt, 'MULTIPLY', t, 0.3), fmath(nt, 'MULTIPLY', t, 1.1), 0.0))
    na = noise(nt, pa, 0.56, 4.0, 0.55, '4D', w=fmath(nt, 'MULTIPLY', t, 0.30))
    nb = noise(nt, pa, 3.4, 3.0, 0.60, '4D', w=fmath(nt, 'MULTIPLY', t, 0.70))
    # far swell (only where the geometry displacement has faded out): crests along X, travelling to -Y
    pc = comb(nt, fmath(nt, 'MULTIPLY', sx, 0.35), fmath(nt, 'ADD', sy, fmath(nt, 'MULTIPLY', t, 9.0)),
              fmath(nt, 'MULTIPLY', t, 2.0))
    nc = noise(nt, pc, 0.055, 2.0, 0.5, '3D')
    fa = maprange(nt, dist, 200.0, 3000.0, 1.0, 0.25)
    fb = maprange(nt, dist, 40.0, 500.0, 1.0, 0.0)
    farw = fmath(nt, 'SUBTRACT', 1.0, a_fade, clamp=True)
    ha = fmath(nt, 'MULTIPLY', fmath(nt, 'MULTIPLY', na, 0.42), fa); ha.node.name = "ENV_RippleMed"
    hb = fmath(nt, 'MULTIPLY', fmath(nt, 'MULTIPLY', nb, 0.06), fb); hb.node.name = "ENV_RippleFine"
    hc = fmath(nt, 'MULTIPLY', fmath(nt, 'MULTIPLY', nc, 2.8), farw); hc.node.name = "ENV_FarSwell"
    h = fmath(nt, 'ADD', fmath(nt, 'ADD', ha, hb), hc)
    bump = N(nt, "ShaderNodeBump", inputs={"Strength": 1.0, "Distance": 1.0})
    bump.name = "ENV_WaterBump"
    L(nt, h, bump.inputs["Height"])
    L(nt, bump.outputs["Normal"], b.inputs["Normal"])
    # colour
    lift = maprange(nt, sz, -0.35, 1.4, 0.0, 1.0)
    base = mixrgb(nt, lift, (0.008, 0.022, 0.038, 1), (0.040, 0.125, 0.140, 1)); base.node.name = "ENV_WaterColor"
    # foam
    nf = noise(nt, pa, 0.9, 3.0, 0.6, '4D', w=fmath(nt, 'MULTIPLY', t, 0.25))
    lace = noise(nt, pa, 6.0, 4.0, 0.72, '4D', w=fmath(nt, 'MULTIPLY', t, 0.35))
    fo = fmath(nt, 'MULTIPLY', a_foam, fmath(nt, 'POWER', a_fade, 3.0))
    lm = maprange(nt, fmath(nt, 'ADD', fmath(nt, 'MULTIPLY', lace, 0.55), fmath(nt, 'MULTIPLY', nf, 0.45)), 0.43, 0.63)
    f1 = fmath(nt, 'MULTIPLY', maprange(nt, fo, 0.03, 0.55), lm)
    f1.node.name = "ENV_CrestFoam"
    nf2 = noise(nt, p2, 0.75, 4.0, 0.6, '4D', w=fmath(nt, 'MULTIPLY', t, 0.40))
    lm2 = maprange(nt, fmath(nt, 'ADD', fmath(nt, 'MULTIPLY', lace, 0.5), fmath(nt, 'MULTIPLY', nf2, 0.5)), 0.30, 0.55)
    f2 = fmath(nt, 'MULTIPLY', maprange(nt, a_shore, 0.25, 0.9), lm2)
    f2.node.name = "ENV_ShoreFoam"
    ps = comb(nt, sx, fmath(nt, 'MULTIPLY', sy, 0.30), fmath(nt, 'MULTIPLY', t, 0.4))
    ns = noise(nt, ps, 0.62, 3.0, 0.6, '3D')
    f3 = fmath(nt, 'MULTIPLY', fmath(nt, 'MULTIPLY', maprange(nt, ns, 0.60, 0.85), lace), 0.14)
    f3.node.name = "ENV_StreakFoam"
    foam = fmath(nt, 'MULTIPLY', fmath(nt, 'ADD', fmath(nt, 'MAXIMUM', f1, f2), f3, clamp=True), 0.9)
    col = mixrgb(nt, foam, base, (0.60, 0.66, 0.72, 1)); col.node.name = "ENV_FoamColor"
    L(nt, col, b.inputs["Base Color"])
    rough = maprange(nt, dist, 60.0, 3000.0, 0.13, 0.32); rough.node.name = "ENV_WaterRough"
    rough = fmath(nt, 'ADD', rough, fmath(nt, 'MULTIPLY', foam, 0.5))
    L(nt, rough, b.inputs["Roughness"])
    b.inputs["IOR"].default_value = 1.33
    b.inputs["Specular IOR Level"].default_value = 1.0
    L(nt, b.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_rock():
    m = bpy.data.materials.new("ENV_Rock")
    nt = M.clear(m)
    out = N(nt, "ShaderNodeOutputMaterial")
    b = N(nt, "ShaderNodeBsdfPrincipled")
    b.name = "ENV_RockBSDF"
    pos = N(nt, "ShaderNodeNewGeometry").outputs["Position"]
    dist = N(nt, "ShaderNodeCameraData").outputs["View Distance"]
    sx, sy, sz = sepxyz(nt, pos)
    n_big = noise(nt, pos, 0.12, 4.0, 0.55)
    n_med = noise(nt, pos, 1.3, 5.0, 0.6)
    n_fine = noise(nt, pos, 7.0, 5.0, 0.65)
    # strata: thin beds in z (dipping like the geometry terraces, warped)
    zt = fmath(nt, 'ADD', fmath(nt, 'ADD', sz, fmath(nt, 'MULTIPLY', sx, 0.10)), fmath(nt, 'MULTIPLY', sy, 0.04))
    zt = fmath(nt, 'ADD', zt, fmath(nt, 'MULTIPLY', n_big, 1.2))
    ps = comb(nt, fmath(nt, 'MULTIPLY', sx, 0.10), fmath(nt, 'MULTIPLY', sy, 0.10), fmath(nt, 'MULTIPLY', zt, 1.5))
    strata = noise(nt, ps, 1.0, 3.0, 0.62)
    # fracture network: ridged noise stretched vertically
    pr = comb(nt, sx, sy, fmath(nt, 'MULTIPLY', sz, 0.35))
    rn = nt.nodes.new("ShaderNodeTexNoise")
    rn.noise_dimensions = '3D'
    try:
        rn.noise_type = 'RIDGED_MULTIFRACTAL'
    except Exception as e:
        print("ridged:", e)
    L(nt, pr, rn.inputs["Vector"])
    rn.inputs["Scale"].default_value = 0.55
    rn.inputs["Detail"].default_value = 5.0
    rn.inputs["Roughness"].default_value = 0.6
    cracks = maprange(nt, rn.outputs["Fac"], 1.02, 1.30, 0.0, 1.0)
    cf = fmath(nt, 'ADD', fmath(nt, 'MULTIPLY', strata, 0.55), fmath(nt, 'MULTIPLY', n_med, 0.5))
    col = mixrgb(nt, maprange(nt, cf, 0.38, 0.72), (0.018, 0.018, 0.021, 1), (0.105, 0.098, 0.092, 1))
    col.node.name = "ENV_RockColor"
    col = mixrgb(nt, fmath(nt, 'MULTIPLY', cracks, 0.5), col, (0.006, 0.006, 0.007, 1))
    # wet / dark near the waterline
    wl = maprange(nt, fmath(nt, 'ADD', sz, fmath(nt, 'MULTIPLY', n_big, 1.0)), 1.0, 4.0, 1.0, 0.0)
    col = mixrgb(nt, fmath(nt, 'MULTIPLY', wl, 0.5), col, (0.008, 0.009, 0.011, 1))
    L(nt, col, b.inputs["Base Color"])
    rdry = maprange(nt, n_med, 0.3, 0.7, 0.36, 0.68, 'LINEAR'); rdry.node.name = "ENV_RockRough"
    rough = fmath(nt, 'SUBTRACT', rdry, fmath(nt, 'MULTIPLY', wl, 0.20))
    rough = fmath(nt, 'ADD', rough, maprange(nt, dist, 120.0, 500.0, 0.0, 0.35), clamp=True)
    L(nt, rough, b.inputs["Roughness"])
    b.inputs["Specular IOR Level"].default_value = 0.5
    hgt = fmath(nt, 'ADD', fmath(nt, 'MULTIPLY', n_med, 0.60), fmath(nt, 'MULTIPLY', n_fine, 0.11))
    hgt = fmath(nt, 'ADD', hgt, fmath(nt, 'MULTIPLY', strata, 0.38))
    hgt = fmath(nt, 'SUBTRACT', hgt, fmath(nt, 'MULTIPLY', cracks, 0.35))
    bump = N(nt, "ShaderNodeBump", inputs={"Strength": 1.0, "Distance": 0.42})
    bump.name = "ENV_RockBump"
    L(nt, hgt, bump.inputs["Height"])
    L(nt, bump.outputs["Normal"], b.inputs["Normal"])
    L(nt, b.outputs["BSDF"], out.inputs["Surface"])
    return m


def mat_spray():
    m = bpy.data.materials.new("ENV_Spray")
    nt = M.clear(m)
    out = N(nt, "ShaderNodeOutputMaterial")
    b = N(nt, "ShaderNodeBsdfPrincipled")
    geo = N(nt, "ShaderNodeNewGeometry")
    t = time_node(nt)
    oi = N(nt, "ShaderNodeObjectInfo")
    tc = N(nt, "ShaderNodeTexCoord")
    facing = fmath(nt, 'ABSOLUTE', vmath(nt, 'DOT_PRODUCT', geo.outputs["Normal"], geo.outputs["Incoming"]))
    edge = fmath(nt, 'POWER', facing, 2.4)
    ox, oy, oz = sepxyz(nt, tc.outputs["Object"])
    rnd = oi.outputs["Random"]
    pn = comb(nt, fmath(nt, 'ADD', ox, fmath(nt, 'MULTIPLY', rnd, 37.0)), oy,
              fmath(nt, 'SUBTRACT', oz, fmath(nt, 'MULTIPLY', t, 0.45)))
    nz = noise(nt, pn, 1.6, 4.0, 0.6)
    ph = fmath(nt, 'MULTIPLY_ADD', t, 0.85, fmath(nt, 'MULTIPLY', rnd, 43.0))
    pulse = fmath(nt, 'POWER', fmath(nt, 'MAXIMUM', fmath(nt, 'SINE', ph), 0.0), 1.6)
    pulse.node.name = "ENV_SprayPulse"
    top = maprange(nt, oz, 0.3, 1.9, 1.0, 0.15)
    a = fmath(nt, 'MULTIPLY', edge, maprange(nt, nz, 0.36, 0.72))
    a = fmath(nt, 'MULTIPLY', fmath(nt, 'MULTIPLY', a, pulse), top)
    a = fmath(nt, 'MULTIPLY', a, 0.42, clamp=True); a.node.name = "ENV_SprayAlpha"
    b.inputs["Base Color"].default_value = (0.75, 0.8, 0.86, 1)
    b.inputs["Roughness"].default_value = 0.95
    b.inputs["Specular IOR Level"].default_value = 0.1
    L(nt, a, b.inputs["Alpha"])
    L(nt, b.outputs["BSDF"], out.inputs["Surface"])
    try:
        m.surface_render_method = 'BLENDED'
        m.use_transparency_overlap = True
    except Exception as e:
        print("spray blend:", e)
    return m


# ============================================================== world
def build_world():
    w = bpy.data.worlds.new("ENV_World")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = N(nt, "ShaderNodeOutputWorld")
    bg = N(nt, "ShaderNodeBackground")
    bg.name = "ENV_SkyBackground"
    t = time_node(nt)
    tc = N(nt, "ShaderNodeTexCoord")
    dn = vmath(nt, 'NORMALIZE', tc.outputs["Generated"])
    x, y, z = sepxyz(nt, dn)
    zc = fmath(nt, 'MAXIMUM', z, 0.0)
    den = fmath(nt, 'ADD', zc, 0.20)
    px = fmath(nt, 'ADD', fmath(nt, 'DIVIDE', x, den), fmath(nt, 'MULTIPLY', t, 0.0055))
    py = fmath(nt, 'ADD', fmath(nt, 'DIVIDE', y, den), fmath(nt, 'MULTIPLY', t, -0.0022))
    px.node.name = "ENV_CloudDriftX"; py.node.name = "ENV_CloudDriftY"
    p = comb(nt, px, py, fmath(nt, 'MULTIPLY', t, 0.004))
    warp = vmath(nt, 'SCALE', vmath(nt, 'SUBTRACT', noise(nt, p, 0.6, 2.0, 0.5, out="Color"), (0.5, 0.5, 0.5)), scale=0.6)
    pw = vmath(nt, 'ADD', p, warp)
    ld = K.normalize(np.array(C.MOONLIGHT_DIR[:2]))
    pl = vmath(nt, 'ADD', pw, (float(ld[0]) * 0.11, float(ld[1]) * 0.11, 0.0))
    n1 = noise(nt, pw, 0.72, 8.0, 0.60, lac=2.1)
    n1b = noise(nt, pl, 0.72, 8.0, 0.60, lac=2.1)
    nd = noise(nt, pw, 5.5, 4.0, 0.6)
    nn = fmath(nt, 'ADD', n1, fmath(nt, 'MULTIPLY', fmath(nt, 'SUBTRACT', nd, 0.5), 0.20))
    horiz = maprange(nt, z, 0.0, 0.5, 1.0, 0.0)
    lo = fmath(nt, 'MULTIPLY_ADD', horiz, -0.09, 0.49); lo.node.name = "ENV_CloudCoverage"
    e = fmath(nt, 'SUBTRACT', nn, lo)
    dens = maprange(nt, e, 0.0, 0.10)
    dens = fmath(nt, 'MULTIPLY', dens, maprange(nt, z, 0.0, 0.09, 0.25, 1.0))
    thick = maprange(nt, e, 0.03, 0.20)
    shade = fmath(nt, 'MULTIPLY_ADD', fmath(nt, 'SUBTRACT', n1, n1b), 5.5, 0.42, clamp=True)
    rim = fmath(nt, 'MULTIPLY_ADD', thick, -0.93, 1.0)
    bfac = fmath(nt, 'MULTIPLY', fmath(nt, 'MULTIPLY_ADD', shade, 0.75, 0.25), fmath(nt, 'POWER', rim, 1.6))
    bfac = fmath(nt, 'MULTIPLY', bfac, fmath(nt, 'MULTIPLY_ADD', horiz, -0.45, 1.0), clamp=True)
    ccol = mixrgb(nt, bfac, (0.0015, 0.0025, 0.006, 1), (0.20, 0.27, 0.40, 1)); ccol.node.name = "ENV_CloudColor"
    # sky gradient + pale horizon band
    sky = mixrgb(nt, fmath(nt, 'POWER', zc, 0.55), (0.020, 0.036, 0.075, 1), (0.0035, 0.007, 0.020, 1))
    sky.node.name = "ENV_SkyGradient"
    band = fmath(nt, 'POWER', fmath(nt, 'SUBTRACT', 1.0, zc), 26.0)
    band.node.name = "ENV_HorizonBand"
    sky = mixrgb(nt, fmath(nt, 'MULTIPLY', band, 1.0), sky, (0.085, 0.14, 0.25, 1), 'ADD')
    # stars
    vor = N(nt, "ShaderNodeTexVoronoi", feature='F1', inputs={"Scale": 150.0})
    L(nt, dn, vor.inputs["Vector"])
    sr, sg, sb_ = sepxyz(nt, vor.outputs["Color"])
    rad = fmath(nt, 'MULTIPLY_ADD', sg, 0.14, 0.10)
    core = fmath(nt, 'SUBTRACT', 1.0, fmath(nt, 'DIVIDE', vor.outputs["Distance"], rad), clamp=True)
    star = fmath(nt, 'MULTIPLY', fmath(nt, 'POWER', core, 2.5), fmath(nt, 'POWER', maprange(nt, sr, 0.93, 1.0, 0.0, 1.0, 'LINEAR'), 2.0))
    star = fmath(nt, 'MULTIPLY', star, 5.0); star.node.name = "ENV_StarBrightness"
    star = fmath(nt, 'MULTIPLY', star, maprange(nt, z, 0.03, 0.30))
    clear = fmath(nt, 'POWER', fmath(nt, 'SUBTRACT', 1.0, dens, clamp=True), 3.0)
    star = fmath(nt, 'MULTIPLY', star, clear)
    scol = mixrgb(nt, sb_, (0.75, 0.85, 1.0, 1), (1.0, 0.93, 0.82, 1))
    sky = mixrgb(nt, star, sky, scol, 'ADD')
    col = mixrgb(nt, fmath(nt, 'MULTIPLY', dens, 0.96), sky, ccol)
    # warm core-light spill in the clouds around the moon direction (as seen from the shore)
    md = K.normalize(np.array(C.MOON_C) - np.array(C.SHORE_CAM))
    wd = fmath(nt, 'MAXIMUM', vmath(nt, 'DOT_PRODUCT', dn, tuple(float(v) for v in md)), 0.0)
    warm = fmath(nt, 'MULTIPLY', fmath(nt, 'POWER', wd, 8.0), fmath(nt, 'MULTIPLY_ADD', dens, 0.75, 0.25))
    warm = fmath(nt, 'MULTIPLY', warm, 0.022); warm.node.name = "ENV_WarmSpill"
    col = mixrgb(nt, warm, col, (1.0, 0.52, 0.20, 1), 'ADD')
    # below the horizon: sea-haze colour (only seen past the edge of the water plane)
    col = mixrgb(nt, maprange(nt, z, -0.03, 0.0, 1.0, 0.0), col, (0.012, 0.020, 0.040, 1))
    L(nt, col, bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    L(nt, bg.outputs[0], out.inputs["Surface"])
    return w


# ============================================================== ocean
def eval_z(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3), me


def build_ocean(col, mat):
    x0, x1, y0, y1 = OCEAN_CORE
    xs = graded_axis(x0, x1, OCEAN_D, -26000, 26000, 1.07)
    ys = graded_axis(y0, y1, OCEAN_D, -26000, 26000, 1.07)
    nx, ny = len(xs), len(ys)
    X, Y = np.meshgrid(xs, ys)
    x, y = X.ravel(), Y.ravel()
    verts = np.stack([x, y, np.zeros_like(x)], -1)
    dx = np.maximum(np.abs(x - (x0 + x1) / 2) - (x1 - x0) / 2, 0)
    dy = np.maximum(np.abs(y - (y0 + y1) / 2) - (y1 - y0) / 2, 0)
    fade = 1 - sstep(0, OCEAN_FADE, np.hypot(dx, dy))
    rh = near_rock_height(x, y)
    fade = fade * (1 - 0.82 * sstep(-2.5, 2.5, rh))
    shore = sstep(-6.0, -0.3, rh)
    ob = K.obj_np("ENV_Ocean", col, verts, grid_quads(nx, ny), mats=[mat],
                  attrs={"fade": ('POINT', fade), "shore": ('POINT', shore), "rest": ('POINT', verts)})
    bpy.context.view_layer.objects.active = ob
    K.log("ocean grid %dx%d = %d quads" % (nx, ny, (nx - 1) * (ny - 1)))

    def ocean(name, **kw):
        md = ob.modifiers.new(name, 'OCEAN')
        md.geometry_mode = 'DISPLACE'
        md.size = 1.0
        md.depth = 200.0
        md.use_normals = False
        for k, v in kw.items():
            setattr(md, k, v)
        return md
    sw = ocean("ENV_Swell", spectrum='PHILLIPS', spatial_size=236, resolution=22, viewport_resolution=22,
               wind_velocity=20.0, wave_alignment=2.5, wave_direction=WAVE_DIR, damping=0.85, choppiness=1.0,
               wave_scale=1.0, wave_scale_min=0.01, random_seed=3, use_foam=True, foam_layer_name="foam",
               foam_coverage=0.15)
    ch = ocean("ENV_Chop", spectrum='PHILLIPS', spatial_size=74, resolution=16, viewport_resolution=16,
               wind_velocity=7.0, wave_alignment=1.0, wave_direction=WAVE_DIR + 0.5, damping=0.5, choppiness=0.6,
               wave_scale=1.0, wave_scale_min=2.6, random_seed=7)
    # --- calibrate amplitudes on the core block
    ix = np.where((xs >= x0 - 1e-3) & (xs <= x1 + 1e-3))[0]
    iy = np.where((ys >= y0 - 1e-3) & (ys <= -80))[0]

    def core_z():
        co, me = eval_z(ob)
        return co[:, 2].reshape(ny, nx)[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1].astype(np.float64), me
    for md, target in ((sw, SWELL_STD), (ch, CHOP_STD)):
        other = ch if md is sw else sw
        other.show_viewport = False
        md.show_viewport = True
        md.time = 10.0
        for it in range(2):
            z, _ = core_z()
            sd = z.std()
            K.log("  %s scale %.4f -> std %.3f" % (md.name, md.wave_scale, sd))
            if sd < 1e-6:
                break
            md.wave_scale = md.wave_scale * target / sd
        other.show_viewport = True
    # --- make sure the swell travels towards -Y (the shore)
    ch.show_viewport = False
    sw.time = 10.0
    z1, _ = core_z()
    sw.time = 12.0
    z2, _ = core_z()
    k = 20
    a = float((z2[k:, :] * z1[:-k, :]).mean())    # pattern moved towards +Y
    bneg = float((z2[:-k, :] * z1[k:, :]).mean())  # pattern moved towards -Y
    K.log("  swell direction check: corr(+Y)=%.3f corr(-Y)=%.3f" % (a, bneg))
    if a > bneg:
        sw.wave_direction += math.pi
        ch.wave_direction += math.pi
        K.log("  -> flipped wave direction")
    sw.time = 10.0
    # --- tune the crest foam amount (fraction of the core area with clearly visible foam)
    cmask = np.zeros((ny, nx), bool)
    cmask[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1] = True
    cmask = cmask.ravel()

    def foam_frac():
        co, me = eval_z(ob)
        ca = me.attributes.get("foam")
        arr = np.empty(len(ca.data) * 4, np.float32)
        ca.data.foreach_get("color", arr)
        li = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", li)
        f = arr.reshape(-1, 4)[:, 0][cmask[li]]
        return float((f > 0.25).mean()), float(f.mean())
    # choppiness: as sharp as possible while only FOLD_FRAC of the surface is close to folding over
    # (measured geometrically: Jacobian of the horizontal displacement on the core grid)
    def fold_frac():
        co, _ = eval_z(ob)
        gx = co[:, 0].reshape(ny, nx)[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1].astype(np.float64)
        gy = co[:, 1].reshape(ny, nx)[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1].astype(np.float64)
        xu, xv = np.diff(gx, axis=1)[:-1, :], np.diff(gx, axis=0)[:, :-1]
        yu, yv = np.diff(gy, axis=1)[:-1, :], np.diff(gy, axis=0)[:, :-1]
        jac = (xu * yv - xv * yu) / (OCEAN_D * OCEAN_D)
        return float((jac < 0.25).mean())
    lo_k, hi_k = 0.05, 1.6
    for it in range(7):
        kch = 0.5 * (lo_k + hi_k)
        sw.choppiness = kch
        ff = fold_frac()
        if ff > FOLD_FRAC:
            hi_k = kch
        else:
            lo_k = kch
    K.log('  swell choppiness %.3f -> near-fold fraction %.4f' % (sw.choppiness, ff))
    lo_c, hi_c = -3.0, 0.5
    for it in range(8):
        c = 0.5 * (lo_c + hi_c)
        sw.foam_coverage = c
        fr, fm = foam_frac()
        if abs(sw.foam_coverage - c) > 1e-4:
            K.log("  foam_coverage clamped to %.3f" % sw.foam_coverage)
        if fr > FOAM_FRAC:
            hi_c = c
        else:
            lo_c = c
    K.log("  foam_coverage %.3f -> frac(foam>0.25)=%.3f mean %.3f" % (sw.foam_coverage, fr, fm))
    ch.show_viewport = True
    z, me = core_z()
    K.log("  combined: std %.2f  min %.2f  max %.2f" % (z.std(), z.min(), z.max()))
    # --- time drivers (never stop)
    for md, off in ((sw, 20.0), (ch, 7.0)):
        fc = ob.driver_add('modifiers["%s"].time' % md.name)
        fc.driver.type = 'SCRIPTED'
        fc.driver.expression = "%.2f+frame*%.6f" % (off, TIME_SCALE / C.FPS)
    # --- geometry nodes: fade the displacement towards the far plane / under the shore rocks
    ng = bpy.data.node_groups.new("ENV_OceanFade", 'GeometryNodeTree')
    ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = ng.nodes.new("NodeGroupInput")
    go = ng.nodes.new("NodeGroupOutput")
    sp = ng.nodes.new("GeometryNodeSetPosition")
    na = ng.nodes.new("GeometryNodeInputNamedAttribute"); na.data_type = 'FLOAT_VECTOR'
    na.inputs["Name"].default_value = "rest"
    nf = ng.nodes.new("GeometryNodeInputNamedAttribute"); nf.data_type = 'FLOAT'
    nf.inputs["Name"].default_value = "fade"
    ps = ng.nodes.new("GeometryNodeInputPosition")
    sub = ng.nodes.new("ShaderNodeVectorMath"); sub.operation = 'SUBTRACT'
    scl = ng.nodes.new("ShaderNodeVectorMath"); scl.operation = 'SCALE'
    add = ng.nodes.new("ShaderNodeVectorMath"); add.operation = 'ADD'
    ng.links.new(ps.outputs[0], sub.inputs[0]); ng.links.new(na.outputs[0], sub.inputs[1])
    ng.links.new(sub.outputs[0], scl.inputs[0]); ng.links.new(nf.outputs[0], scl.inputs[3])
    ng.links.new(na.outputs[0], add.inputs[0]); ng.links.new(scl.outputs[0], add.inputs[1])
    ng.links.new(gi.outputs[0], sp.inputs["Geometry"]); ng.links.new(add.outputs[0], sp.inputs["Position"])
    ng.links.new(sp.outputs[0], go.inputs[0])
    gm = ob.modifiers.new("ENV_OceanFade", 'NODES')
    gm.node_group = ng
    co, _ = eval_z(ob)
    zz = co[:, 2].reshape(ny, nx)
    K.log("  after fade: core std %.2f, far-corner z %.3f, max|z| under land %.2f" % (
        zz[iy[0]:iy[-1] + 1, ix[0]:ix[-1] + 1].std(), float(zz[0, 0]), float(np.abs(co[rh > 4.0, 2]).max())))
    return ob


# ============================================================== rocks
def build_rocks(col, mat):
    obs = []
    xs = graded_axis(-115, 35, 0.33, -275, 215, 1.07)
    ys = graded_axis(-360, -316, 0.33, -462, -284, 1.07)
    obs.append(patch_mesh("ENV_Shore", col, xs, ys, shore_height, 2.9, mat, jitter=0.12))
    K.log("shore built", K.tri_count([obs[-1]]))
    for group, lst, res_div, cliff in (("ENV_Stack", NEAR_STACKS, 26, 0.55), ("ENV_MidStack", MID_STACKS, 30, 0.6),
                                       ("ENV_Island", ISLANDS, 50, 0.72)):
        for i, (cx, cy, rx, ry, H, seed, rot) in enumerate(lst):
            sc = max(rx, ry)
            d = max(sc / res_div, 0.22)
            ext = 1.5 * sc
            ax = np.arange(cx - ext, cx + ext + d, d)
            ay = np.arange(cy - ext, cy + ext + d, d)
            step = max(0.9, H / 9.0)
            fn = (lambda x, y, a=(cx, cy, rx, ry, H, seed, rot), c=cliff: stack_height(x, y, *a, cliff=c))
            obs.append(patch_mesh("%s_%02d" % (group, i), col, ax, ay, fn, step, mat, jitter=0.25 * d))
    return obs


def build_spray(col, mat):
    import bmesh
    me = bpy.data.meshes.new("ENV_SprayPuff")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
    for v in bm.verts:
        v.co.z += 0.8
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.materials.append(mat)
    rng = np.random.RandomState(5)
    pts = []
    yy = np.arange(-290.0, -350.0, -0.4)
    for xc in np.arange(-150.0, 82.0, 5.5):
        xq = xc + rng.uniform(-2, 2)
        h = shore_height(np.full_like(yy, xq), yy)
        hit = np.where(h > -0.8)[0]
        if len(hit):
            pts.append((xq, yy[hit[0]] + 0.8, rng.uniform(1.8, 3.2), rng.uniform(1.6, 3.4)))
    for (cx, cy, rx, ry, H, seed, rot) in NEAR_STACKS:
        for a in (0.9, 1.6, 2.3):
            pts.append((cx + math.cos(a) * rx * 0.85, cy + math.sin(a) * ry * 0.85, rng.uniform(1.4, 2.4), rng.uniform(1.4, 2.8)))
    obs = []
    for i, (px, py, sxy, sz) in enumerate(pts):
        ob = bpy.data.objects.new("ENV_Spray_%02d" % i, me)
        ob.location = (px, py, 0.2)
        ob.scale = (sxy * rng.uniform(0.9, 1.4), sxy, sz)
        ob.rotation_euler = (0, 0, rng.uniform(0, 6.28))
        ob.visible_shadow = False
        col.objects.link(ob)
        obs.append(ob)
    return obs


# ============================================================== main
def main():
    sc = K.reset()
    sc.frame_start, sc.frame_end = 1, C.FRAMES
    sc.render.fps = C.FPS
    col = K.coll("ENV")
    m_water, m_rock, m_spray = mat_water(), mat_rock(), mat_spray()
    rocks = build_rocks(col, m_rock)
    K.log("rocks: %d objects, %d tris" % (len(rocks), K.tri_count(rocks)))
    ocean = build_ocean(col, m_water)
    K.log("ocean tris", K.tri_count([ocean]))
    spray = build_spray(col, m_spray)
    K.log("spray puffs: %d, tris %d" % (len(spray), K.tri_count(spray)))
    sc.world = build_world()
    for o in col.objects:
        if not o.name.startswith('ENV_Spray'):
            K.log('  %-16s %7d tris' % (o.name, K.tri_count([o])))
    K.log('TOTAL ENV tris %d (water %d, rocks %d, spray %d)' % (K.tri_count(list(col.objects)), K.tri_count([ocean]), K.tri_count(rocks), K.tri_count(spray)))
    sc.frame_set(1)
    K.setup_eevee(sc)
    K.save_blend(K.P("blend", "env.blend"))
    K.log("ENV BUILD OK in %.1fs" % (time.time() - T0))


if __name__ == "__main__":
    main()
