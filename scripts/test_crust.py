import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh, numpy as np
from mathutils import Vector
import common as K, config as C, mats, look

views = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["hero"]
sc = K.reset()
bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
c = K.append_collection(K.P("blend", "crust.blend"), "CRUST")
moon = bpy.data.objects.new("MOON", None)
sc.collection.objects.link(moon)
moon.location = C.MOON_C
for o in c.objects:
    if o.parent is None:
        o.parent = moon
# stand-in hull
me = bpy.data.meshes.new("hull")
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=6, radius=C.HULL_R)
d = np.array([v.co[:] for v in bm.verts])
f = C.open_field(K.normalize(d))
bmesh.ops.delete(bm, geom=[v for v, ff in zip(bm.verts, f) if ff < C.HULL_OPEN_F], context='VERTS')
bm.to_mesh(me)
bm.free()
me.shade_smooth()
me.materials.append(mats.get("HullSkin"))
h = bpy.data.objects.new("hull", me)
sc.collection.objects.link(h)
h.parent = moon
look.apply()
K.add_test_rig(fog=True)
M = Vector(C.MOON_C)
od = Vector(C.OPEN_DIR)
right = Vector(C.OPEN_RIGHT)
up = Vector(C.OPEN_UP)
V = {
    "hero": (C.SHORE_CAM, C.SHORE_CAM_TARGET, 30),
    "rim": (M + od * 150 + right * 95 + up * 60, M + right * 62 + up * 40 + od * 60, 50),
    "close": (M + (od * 0.35 + right * 0.9 + up * 0.25).normalized() * 118, M + (od * 0.62 + right * 0.72 + up * 0.3).normalized() * 100, 35),
    "left": (M + Vector((-300, -120, 40)), M, 35),
    "back": (M + Vector((60, 330, 60)), M, 35),
}
for v in views:
    loc, tgt, lens = V[v]
    K.quick_render(K.P("renders", "crust_%s.png" % v), loc, tgt, lens=lens)
