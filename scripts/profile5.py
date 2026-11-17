import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

F = 230
sc = bpy.context.scene
K.setup_eevee(sc, samples=1, res=(1920, 1080))
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=0.8)
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
ee.gi_cubemap_resolution = '256'
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
cam = marks[0][1]
for mf, mc in marks:
    if mf <= F:
        cam = mc
sc.frame_set(F)
sc.camera = cam
out = K.P("renders", "bench")
sc.render.image_settings.file_format = 'JPEG'
GROUPS = {"CRUST": ("CRUST_",), "ARCH": ("ARCH_",), "ENV": ("ENV_",), "MECH": ("MECH_", "DUST", "Bolt"), "FOG": ("Fog",)}


def only(names):
    for o in bpy.data.objects:
        if o.type in ('MESH', 'LIGHT_PROBE'):
            vis = any(o.name.startswith(GROUPS[n]) for n in names)
            o.hide_render = not vis


def run(name, n=3):
    ts = []
    for i in range(n):
        sc.render.filepath = os.path.join(out, "p5_" + name + ".jpg")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        ts.append(time.time() - t)
    K.log("PROF5 %-22s min %.1f  (%s)" % (name, min(ts), " ".join("%.1f" % t for t in ts)))


only([]); run("warm", 1)
only(list(GROUPS)); run("all", 2)
only([]); run("none")
for g in GROUPS:
    only([g]); run("only_" + g)
only(["CRUST", "ARCH", "ENV", "MECH"]); run("all_but_fog")
for l in bpy.data.lights:
    l.use_shadow = False
run("all_but_fog_noshadow")
for l in bpy.data.lights:
    l.use_shadow = True
only(list(GROUPS))
ee.taa_render_samples = 12
run("all_s12")
ee.volumetric_tile_size = '8'
run("all_s12_tile8")
