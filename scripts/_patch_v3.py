"""One-off patcher for the v3 look pass after the art-director review (kept for reference)."""
import os, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def sub(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)


# ------------------------------------------------------------------ ocean: everything ~2.6x finer and lower so the moon reads bigger
sub('build_env.py', [
    ('SWELL_STD = 1.5 ', 'SWELL_STD = 0.62 '),
    ('CHOP_STD = 0.55 ', 'CHOP_STD = 0.24 '),
    ('TIME_SCALE = 0.85 ', 'TIME_SCALE = 0.60 '),
    ('sw = ocean("ENV_Swell", spectrum=\'PHILLIPS\', spatial_size=613, resolution=22, viewport_resolution=22,\n               wind_velocity=32.0,',
     'sw = ocean("ENV_Swell", spectrum=\'PHILLIPS\', spatial_size=236, resolution=22, viewport_resolution=22,\n               wind_velocity=20.0,'),
    ('ch = ocean("ENV_Chop", spectrum=\'PHILLIPS\', spatial_size=151, resolution=16, viewport_resolution=16,\n               wind_velocity=11.0,',
     'ch = ocean("ENV_Chop", spectrum=\'PHILLIPS\', spatial_size=74, resolution=16, viewport_resolution=16,\n               wind_velocity=7.0,'),
    ("na = noise(nt, pa, 0.22, 4.0, 0.55, '4D'", "na = noise(nt, pa, 0.56, 4.0, 0.55, '4D'"),
    ("nb = noise(nt, pa, 1.4, 3.0, 0.60, '4D'", "nb = noise(nt, pa, 3.4, 3.0, 0.60, '4D'"),
    ("nc = noise(nt, pc, 0.022, 2.0, 0.5, '3D')", "nc = noise(nt, pc, 0.055, 2.0, 0.5, '3D')"),
    ('hc = fmath(nt, \'MULTIPLY\', fmath(nt, \'MULTIPLY\', nc, 7.0), farw)', 'hc = fmath(nt, \'MULTIPLY\', fmath(nt, \'MULTIPLY\', nc, 2.8), farw)'),
    ('ha = fmath(nt, \'MULTIPLY\', fmath(nt, \'MULTIPLY\', na, 1.0), fa)', 'ha = fmath(nt, \'MULTIPLY\', fmath(nt, \'MULTIPLY\', na, 0.42), fa)'),
    ('hb = fmath(nt, \'MULTIPLY\', fmath(nt, \'MULTIPLY\', nb, 0.14), fb)', 'hb = fmath(nt, \'MULTIPLY\', fmath(nt, \'MULTIPLY\', nb, 0.06), fb)'),
    ("nf = noise(nt, pa, 0.35, 3.0, 0.6, '4D'", "nf = noise(nt, pa, 0.9, 3.0, 0.6, '4D'"),
    ("lace = noise(nt, pa, 2.4, 5.0, 0.72, '4D'", "lace = noise(nt, pa, 6.0, 4.0, 0.72, '4D'"),
    ("nf2 = noise(nt, p2, 0.3, 4.0, 0.6, '4D'", "nf2 = noise(nt, p2, 0.75, 4.0, 0.6, '4D'"),
    ("ns = noise(nt, ps, 0.25, 3.0, 0.6, '3D')", "ns = noise(nt, ps, 0.62, 3.0, 0.6, '3D')"),
    ('lift = maprange(nt, sz, -0.8, 3.2, 0.0, 1.0)', 'lift = maprange(nt, sz, -0.35, 1.4, 0.0, 1.0)'),
])

# ------------------------------------------------------------------ crust: thin tapered shards, no glow bands on loose pieces, nothing floating in front of the opening
sub('build_crust.py', [
    ('''c12 = (cls == 1) | (cls == 2)
gap[c12] = 0.3
amp[c12] = 1.0''',
     '''c12 = (cls == 1) | (cls == 2)
gap[c12] = 0.3
amp[c12] = 1.0
# loose pieces are thinner than the full crust and taper towards their underside (broken shards, not extruded slabs)
prad = np.sqrt(np.bincount(plate, minlength=NP_) * 0.155 / np.pi)
rbot = np.full(NP_, R_BOT)
rbot[c12] = C.R - rng.uniform(2.0, 4.4, int(c12.sum()))
und = np.full(NP_, 0.55)
und[c12] = rng.uniform(1.3, 2.6, int(c12.sum())) * np.clip(prad[c12] / 5.0, 0.15, 1.0)'''),
    ('''    rk = r_top[:, None] * (1 - t)[None, :] + R_BOT * t[None, :]''',
     '''    rb = rbot[lv_plate[bidx]]
    rk = r_top[:, None] * (1 - t)[None, :] + rb[:, None] * t[None, :]'''),
    ('''    off = -gp[:, None] * 0.5 + am[:, None] * ramp * (nz + strata) - am[:, None] * 0.55 * t[None, :] * under[:, None]''',
     '''    off = -gp[:, None] * 0.5 + am[:, None] * ramp * (nz + strata) - (am * und[lv_plate[bidx]])[:, None] * t[None, :] * under[:, None]'''),
    ('''        pb = d_top * R_BOT''', '''        pb = d_top * rbot[lv_plate][:, None]'''),
    ('''    g["openf"] = np.full(len(g["openf"]), 3.0) if cls[p] == 1 else np.maximum(g["openf"], 1.7)''',
     '''    g["openf"] = np.full(len(g["openf"]), 3.0)'''),
    ('''        ok = (f > 0.45) & (f < 1.22)''', '''        ok = (f > 0.90) & (f < 1.28)'''),
])

# ------------------------------------------------------------------ mechanism: no human-scale truss on the orbit ring
sub('build_mech.py', [
    ('''def ext_ring(name, r, w, t, nseg, lattice=True):''', '''def ext_ring(name, r, w, t, nseg, lattice=True, truss=False):'''),
    ('''        off = w / 2 + 3.2
        for sgn in (-1, 1):''', '''        off = w / 2 + 3.2
        for sgn in ((-1, 1) if truss else ()):'''),
])

# ------------------------------------------------------------------ canonical materials
sub('mats.py', [
    ('"Gold":      lambda m: _metal(m, (1.00, 0.68, 0.25), 0.18, 0.40, wear_dark=0.62, scale=1.7, bump=0.10),',
     '"Gold":      lambda m: _metal(m, (1.00, 0.66, 0.22), 0.13, 0.30, wear_dark=0.55, scale=1.7, bump=0.08),'),
    ('"Brass":     lambda m: _metal(m, (0.80, 0.54, 0.22), 0.28, 0.52, wear_dark=0.55, scale=1.9, bump=0.16),',
     '"Brass":     lambda m: _metal(m, (0.50, 0.30, 0.11), 0.22, 0.42, wear_dark=0.5, scale=1.9, bump=0.14),'),
    ('"Bronze":    lambda m: _metal(m, (0.30, 0.18, 0.08), 0.38, 0.62, wear_dark=0.6, scale=2.1, bump=0.2),',
     '"Bronze":    lambda m: _metal(m, (0.16, 0.095, 0.045), 0.30, 0.52, wear_dark=0.55, scale=2.1, bump=0.18),'),
    ('"DarkMetal": lambda m: _metal(m, (0.045, 0.043, 0.048), 0.35, 0.60, wear_dark=0.5, scale=0.8, bump=0.2),',
     '"DarkMetal": lambda m: _metal(m, (0.085, 0.060, 0.040), 0.26, 0.48, wear_dark=0.5, scale=1.6, bump=0.16),'),
    ('"Window":    lambda m: _emit(m, (1.0, 0.52, 0.17), 4.2, attr="rnd"),', '"Window":    lambda m: _emit(m, (1.0, 0.55, 0.20), 3.2, attr="rnd", dark_below=0.44),'),
    ('"Lamp":      lambda m: _emit(m, (1.0, 0.74, 0.42), 24.0),', '"Lamp":      lambda m: _emit(m, (1.0, 0.66, 0.32), 9.0),'),
    ('''def _emit(mat, color, strength, attr=None, base=(0.02, 0.012, 0.005)):''', '''def _emit(mat, color, strength, attr=None, base=(0.02, 0.012, 0.005), dark_below=0.12):'''),
    ('''inputs={"From Min": 0.12, "From Max": 1.0, "To Min": 0.0, "To Max": strength * 1.6})''',
     '''inputs={"From Min": dark_below, "From Max": 1.0, "To Min": 0.0, "To Max": strength * 1.6})'''),
])
print("v3 patch ok")
