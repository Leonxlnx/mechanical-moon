"""Isolate the FIXED per-frame cost (1 sample) and test cheaper volumetrics. -- [frame]"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
F = int(argv[0]) if argv else 230
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
oc = bpy.data.objects.get("ENV_Ocean")
if oc:
    for m in oc.modifiers:
        K.log("OCEAN MOD", m.name, m.type, getattr(m, "resolution", None), getattr(m, "viewport_resolution", None), getattr(m, "spatial_size", None), getattr(m, "repeat_x", None))
K.log("LIGHTLINK attr:", hasattr(bpy.data.objects[0], "light_linking"))


def run(name):
    sc.render.filepath = os.path.join(out, "p2_" + name + ".jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    K.log("PROF2 %-16s %.1fs" % (name, time.time() - t))


def hide(prefixes, state):
    for o in bpy.data.objects:
        if o.name.startswith(prefixes):
            o.hide_render = state


run("warm")
run("s1_base")
run("s1_base_again")
sc.use_nodes = False; run("s1_nocomp"); sc.use_nodes = True
hide(("Fog",), True); run("s1_nofog"); hide(("Fog",), False)
if oc:
    for m in oc.modifiers:
        m.show_render = False
    run("s1_noOceanMods")
    for m in oc.modifiers:
        m.show_render = True
hide(("ENV_",), True); run("s1_noenv"); hide(("ENV_",), False)
for l in bpy.data.lights:
    l.use_shadow = False
run("s1_noshadow")
for l in bpy.data.lights:
    l.use_shadow = True
pr = bpy.data.objects.get("InteriorProbe")
if pr:
    for c in list(pr.users_collection):
        c.objects.unlink(pr)
    run("s1_noprobe")
hide(("ARCH_", "CRUST_", "MECH_", "ENV_", "DUST", "Bolt"), True); run("s1_empty"); hide(("ARCH_", "CRUST_", "MECH_", "ENV_", "DUST", "Bolt"), False)
ee.use_overscan = False; run("s1_nooverscan")
# per-sample volumetric cost variants at 12 samples
ee.taa_render_samples = 12
run("s12_tile4")
ee.volumetric_tile_size = '8'
run("s12_tile8")
ee.volumetric_samples = 40
run("s12_tile8_v40")
ee.volumetric_tile_size = '4'
ee.volumetric_samples = 40
ee.volumetric_shadow_samples = 8
run("s12_tile4_v40_sh8")
