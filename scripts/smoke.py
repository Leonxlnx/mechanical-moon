import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np, math
import common as K, config as C, mats

sc = K.reset()
col = K.coll("T")
# quad grid sphere patch test via mesh_np
n = 64
u, v = np.meshgrid(np.linspace(0, 2 * np.pi, n), np.linspace(-1.2, 1.2, n))
verts = np.stack([np.cos(u) * np.cos(v), np.sin(u) * np.cos(v), np.sin(v)], -1).reshape(-1, 3) * 30
idx = np.arange(n * n).reshape(n, n)
quads = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
rnd = np.random.rand(len(verts))
for i, name in enumerate(["Gold", "Brass", "Bronze", "DarkMetal", "Silver", "Window", "Enamel", "HullSkin"]):
    ob = K.obj_np("s_" + name, col, verts * 0.4, quads, attrs={"rnd": ('POINT', rnd)}, mats=[mats.get(name)], sharp_angle=40)
    a = i / 8 * 2 * math.pi
    ob.location = (C.MOON_C[0] + math.cos(a) * 55, C.MOON_C[1] + math.sin(a) * 55, C.MOON_C[2])
print("field", C.open_field(K.normalize(np.random.randn(5, 3))))
K.add_test_rig(fog=True, stand_in_moon=False)
dt = K.quick_render(K.P("renders", "smoke.png"), (0, -260, 150), C.MOON_C, lens=35)
print("SMOKE OK", dt, "tris", K.tri_count())
