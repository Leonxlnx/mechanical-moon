"""Why does the shaft brightness jump between frames 10 and 11? Try shadow / volume settings."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, numpy as np
import common as K

sc = bpy.context.scene
K.setup_eevee(sc, samples=12, res=(960, 540))
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
ee.volumetric_end = 900.0
ee.volumetric_samples = 64
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
sc.camera = marks[0][1]
out = K.P("renders", "flick")
sc.render.image_settings.file_format = 'PNG'
core = bpy.data.lights["CoreLight"]
print("DIAG core light: soft %.2f max_res %.3f pool %s scale %.2f" % (core.shadow_soft_size, core.shadow_maximum_resolution, ee.shadow_pool_size, ee.shadow_resolution_scale))


def region_mean(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    bpy.data.images.remove(img)
    # region B (x 625..725, y 235..295 from the top) -> rows counted from the bottom
    r = px[h - 295:h - 235, 625:725, :3].mean()
    a = px[h - 280:h - 220, 450:550, :3].mean()
    return a * 255, r * 255


def run(name):
    vals = []
    for f in (9, 10, 11, 12):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(out, "d_%s_%d.png" % (name, f))
        bpy.ops.render.render(write_still=True)
        vals.append(region_mean(sc.render.filepath))
    print("DIAG %-22s A: %s | B: %s" % (name, " ".join("%.1f" % v[0] for v in vals), " ".join("%.1f" % v[1] for v in vals)))


run("base")
ee.shadow_pool_size = '1024'
run("pool1024")
ee.shadow_resolution_scale = 0.4
run("pool1024_scale0.4")
ee.shadow_resolution_scale = 0.8
core.shadow_maximum_resolution = 0.3
run("core_maxres0.3")
core.shadow_maximum_resolution = 0.10
ee.volumetric_shadow_samples = 64
run("volshadow64")
ee.volumetric_shadow_samples = 24
for o in bpy.data.objects:
    if o.name.startswith("MECH_Cage"):
        o.visible_shadow = False
run("cage_noshadow")
for o in bpy.data.objects:
    if o.name.startswith("MECH_G"):
        o.visible_shadow = False
run("rings_noshadow")
