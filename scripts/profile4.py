import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

F = 230
sc = bpy.context.scene
K.setup_eevee(sc, samples=1, res=(1920, 1080))
K._set(sc.eevee, shadow_pool_size='1024', shadow_resolution_scale=0.8)
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
cam = marks[0][1]
for mf, mc in marks:
    if mf <= F:
        cam = mc
sc.frame_set(F)
sc.camera = cam
out = K.P("renders", "bench")
sc.render.image_settings.file_format = 'JPEG'
for o in bpy.data.objects:
    if o.type in ('MESH', 'LIGHT_PROBE'):
        o.hide_render = True


def run(name, n=2):
    ts = []
    for i in range(n):
        sc.render.filepath = os.path.join(out, "p4_" + name + ".jpg")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        ts.append(time.time() - t)
    K.log("PROF4 %-22s %s" % (name, " ".join("%.1f" % t for t in ts)))


run("warm", 1)
run("empty_pool1024")
ee.shadow_pool_size = '256'
run("empty_pool256")
ee.gi_cubemap_resolution = '256'
run("empty_cube256")
ee.volumetric_tile_size = '16'
run("empty_tile16")
ee.use_overscan = False
run("empty_nooverscan")
ee.use_raytracing = False
run("empty_nort")
sc.use_nodes = False
run("empty_nocomp")
for l in bpy.data.lights:
    l.use_shadow = False
run("empty_noshadows")
sc.render.resolution_x, sc.render.resolution_y = 960, 540
run("empty_540p")
K.log("objects total", len(bpy.data.objects), "fcurves", sum(len(a.fcurves) for a in bpy.data.actions))
# pure frame change cost
t = time.time()
for f in range(231, 236):
    sc.frame_set(f)
K.log("PROF4 frame_set x5: %.1fs" % (time.time() - t))
