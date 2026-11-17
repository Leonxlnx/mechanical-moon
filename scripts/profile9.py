"""Time two representative frames at the candidate final settings; keeps the images."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
tag = argv[0] if argv else "x"
sc = bpy.context.scene
K.setup_eevee(sc, samples=16, res=(1920, 1080))
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=0.8)
sc.view_settings.exposure = P["exposure"]
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
ee.volumetric_end = 900.0
ee.volumetric_samples = 64
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
out = K.P("renders", "bench")
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 93


def cam_for(f):
    c = marks[0][1]
    for mf, mc in marks:
        if mf <= f:
            c = mc
    return c


def render(f, name):
    sc.frame_set(f)
    sc.camera = cam_for(f)
    sc.render.filepath = os.path.join(out, "p9_%s_%s_%d.jpg" % (tag, name, f))
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t


render(400, "warm")
for s in (16, 12, 16, 12):
    ee.taa_render_samples = s
    ts = [render(f, "s%d" % s) for f in (400, 240, 700, 1180)]
    K.log("PROF9 %s samples %d: f400 %.1f  f240 %.1f  f700 %.1f  f1180 %.1f" % (tag, s, ts[0], ts[1], ts[2], ts[3]))
