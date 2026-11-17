"""Volumetric cost variants on two shots; writes images for visual comparison."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

sc = bpy.context.scene
K.setup_eevee(sc, samples=16, res=(1920, 1080))
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=0.8)
sc.view_settings.exposure = P["exposure"]
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
out = K.P("renders", "bench")
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 93
fog = bpy.data.objects["Fog"]


def cam_for(f):
    c = marks[0][1]
    for mf, mc in marks:
        if mf <= f:
            c = mc
    return c


def render(f, name):
    sc.frame_set(f)
    sc.camera = cam_for(f)
    sc.render.filepath = os.path.join(out, "p8_%s_%d.jpg" % (name, f))
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t


def step(name):
    ts = [render(f, name) for f in (400, 240)]
    K.log("PROF8 %-30s f400 %.1fs  f240 %.1fs" % (name, ts[0], ts[1]))


render(400, "warm")
step("A_big_fog_tile4_v96")
fog.scale = (1200, 1500, 440)
fog.location = (0, -120, 218)
step("B_small_fog")
ee.volumetric_end = 900.0
ee.volumetric_samples = 64
step("C_small_end900_v64")
ee.volumetric_tile_size = '8'
step("D_C_tile8")
ee.volumetric_samples = 96
step("E_tile8_v96")
ee.volumetric_tile_size = '4'
ee.volumetric_samples = 64
ee.taa_render_samples = 12
step("F_C_s12")
