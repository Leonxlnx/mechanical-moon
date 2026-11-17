"""Print a coarse height map of the shore rocks (max z per 10 m cell) to plan camera positions."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np
import common as K

sc = K.reset()
c = K.append_collection(K.P("blend", "env.blend"), "ENV")
xs = np.arange(-200, 121, 10)
ys = np.arange(-470, -259, 10)
H = np.full((len(ys), len(xs)), -9.0)
for o in c.all_objects:
    if o.type != 'MESH' or not o.name.startswith(("ENV_Shore", "ENV_Stack", "ENV_MidStack")):
        continue
    co, _, _, _ = K.mesh_arrays(o.data)
    M = np.array(o.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    ix = np.floor((w[:, 0] - xs[0]) / 10).astype(int)
    iy = np.floor((w[:, 1] - ys[0]) / 10).astype(int)
    ok = (ix >= 0) & (ix < len(xs)) & (iy >= 0) & (iy < len(ys))
    np.maximum.at(H, (iy[ok], ix[ok]), w[ok, 2])
    print("OBJ", o.name, "x %.0f..%.0f y %.0f..%.0f zmax %.1f" % (w[:, 0].min(), w[:, 0].max(), w[:, 1].min(), w[:, 1].max(), w[:, 2].max()))
print("MAP rows = y (top = far from moon), cols = x from %d step 10; value = max rock z (m), '.' = water" % xs[0])
print("MAP      " + "".join("%4d" % x for x in xs))
for j in range(len(ys)):
    print("MAP %5d " % ys[j] + "".join(("%4.0f" % H[j, i]) if H[j, i] > 0.3 else "   ." for i in range(len(xs))))
