"""Find what the frame time is made of. blender -b moon_scene.blend -P profile.py -- [frame]"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
F = int(argv[0]) if argv else 230
sc = bpy.context.scene
K.setup_eevee(sc, samples=12, res=(1920, 1080))
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


def run(name):
    sc.render.filepath = os.path.join(out, "prof_" + name + ".jpg")
    sc.render.image_settings.file_format = 'JPEG'
    t = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    K.log("PROF %-14s %.1fs" % (name, dt))
    return dt


def hide(prefixes, state):
    for o in bpy.data.objects:
        if o.name.startswith(prefixes):
            o.hide_render = state


run("warm")
for s in (1, 4, 12):
    ee.taa_render_samples = s
    run("samples%d" % s)
ee.taa_render_samples = 12
run("again12")
hide(("Fog",), True); run("nofog"); hide(("Fog",), False)
hide(("InteriorProbe",), True); run("noprobe"); hide(("InteriorProbe",), False)
hide(("ARCH_",), True); run("noarch"); hide(("ARCH_",), False)
hide(("CRUST_",), True); run("nocrust"); hide(("CRUST_",), False)
hide(("ENV_",), True); run("noenv"); hide(("ENV_",), False)
hide(("MECH_", "DUST"), True); run("nomech"); hide(("MECH_", "DUST"), False)
for l in bpy.data.lights:
    if l.type == 'SUN':
        l.use_shadow = False
run("nosunshadow")
for l in bpy.data.lights:
    l.use_shadow = False
run("noshadow")
for l in bpy.data.lights:
    l.use_shadow = True
sc.use_nodes = False
run("nocomp")
sc.use_nodes = True
ee.use_raytracing = False
run("nort")
ee.use_raytracing = True
sc.render.resolution_x, sc.render.resolution_y = 960, 540
run("half_res")
