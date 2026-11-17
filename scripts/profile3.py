import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

F = 230
sc = bpy.context.scene
K.setup_eevee(sc, samples=1, res=(1920, 1080))
K._set(sc.eevee, shadow_pool_size='1024', shadow_resolution_scale=0.8)
sc.view_settings.exposure = P["exposure"]
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
ee.volumetric_samples = 64
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
cam = marks[0][1]
for mf, mc in marks:
    if mf <= F:
        cam = mc
sc.frame_set(F)
sc.camera = cam
out = K.P("renders", "bench")
sc.render.image_settings.file_format = 'JPEG'


def run(name):
    sc.render.filepath = os.path.join(out, "p3_" + name + ".jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    K.log("PROF3 %-18s %.1fs" % (name, time.time() - t))


run("warm")
run("s1_cube1024")
ee.gi_cubemap_resolution = '256'
run("s1_cube256")
run("s1_cube256_b")
w = sc.world
sc.world = None
run("s1_noworld")
sc.world = w
for l in bpy.data.lights:
    if l.name.startswith(("RimLight", "FlashSun")):
        l.use_shadow = False
run("s1_rimNoShadow")
ee.volumetric_tile_size = '8'
ee.taa_render_samples = 12
run("s12_final_tile8")
ee.taa_render_samples = 16
run("s16_final_tile8")
ee.volumetric_tile_size = '4'
ee.taa_render_samples = 12
run("s12_final_tile4")
