"""Test renders of blend/arch.blend (run build_arch.py first).
blender -b --factory-startup -P test_arch.py -- a b c d e      (default: a b c d e)
Views: a hero from the shore, b from the opening to the rose, c grazing gallery close-up, d lower spire + gears,
e dome + upper spire, f rose, g gears close, h wall close, i cut edge from outside, j/k spires, m vertical gears.
Add 'cull' to hide back faces (normal check). Interior views are rendered at EXPO stops (standard rig unchanged)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np, math
import common as K, config as C
from arch_lib import sph

views = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else list("abcde")
bpy.ops.wm.open_mainfile(filepath=K.P("blend", "arch.blend"))
root = bpy.data.objects.new("TEST_MoonRoot", None)
bpy.context.scene.collection.objects.link(root)
root.location = C.MOON_C
for ob in bpy.data.collections["ARCH"].objects:
    if ob.parent is None:
        ob.parent = root
K.add_test_rig(fog=True)
EXPO = -2.0   # interior test views are rendered 2 stops down so the detail can be judged (rig is unchanged)
MC = np.array(C.MOON_C)
OD = np.asarray(C.OPEN_DIR)
rad = math.radians


def loc(lon, lat, r):
    return tuple(MC + sph(np.array([rad(lon)]), np.array([rad(lat)]), r)[0])


V = {
    "a": (C.SHORE_CAM, C.SHORE_CAM_TARGET, 30),
    "b": (tuple(MC + OD * 85), tuple(MC - OD * 90), 24),
    "c": (loc(169, 5, 80.5), loc(136, 12, 90.0), 35),
    "d": (tuple(MC + np.array([20, -42, -28.0])), tuple(MC + np.array([0, 6, -82.0])), 24),
    "e": (tuple(MC + np.array([-14, -34, 22.0])), tuple(MC + np.array([0, 0, 90.0])), 20),
    "f": (tuple(MC + OD * 40 + np.array([0, 0, 10.0])), tuple(MC - OD * 92), 50),     # rose close
    "g": (loc(60, -20, 62), loc(100, -62, 80), 28),                                    # gears close
    "h": (loc(200, 30, 70), loc(215, 33, 91), 30),                                     # wall frontal close
}
V["j"] = (tuple(MC + np.array([34, -30, 58.0])), tuple(MC + np.array([0, 0, 79.0])), 35)     # upper spire
V["k"] = (tuple(MC + np.array([30, -34, -52.0])), tuple(MC + np.array([0, 0, -76.0])), 35)   # lower spire
_a = rad(112.0)
V["m"] = (tuple(MC + np.array([20 * math.cos(_a) - 22 * math.sin(_a), 20 * math.sin(_a) + 22 * math.cos(_a), -62.0])),
          tuple(MC + np.array([37 * math.cos(_a), 37 * math.sin(_a), -74.0])), 35)        # vertical gear train A
if "cull" in views:      # debugging aid: hide back faces to reveal flipped normals
    views.remove("cull")
    for m in bpy.data.materials:
        m.use_backface_culling = True
    CULL = "_cull"
else:
    CULL = ""
OR = np.asarray(C.OPEN_RIGHT)
de = OD * math.cos(rad(46)) + OR * math.sin(rad(46))
V["i"] = (tuple(MC + OD * 135 + OR * 30), tuple(MC + de * 92), 60)                     # cut edge from outside
for k in views:
    p, t, lens = V[k]
    bpy.context.scene.view_settings.exposure = 0.0 if k in "ai" else EXPO
    dt = K.quick_render(K.P("renders", "arch_%s%s.png" % (k, CULL)), p, t, lens=lens)
    print("VIEW", k, "%.1fs" % dt)
