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
L = {l.name: l for l in bpy.data.lights}
K.log("lights", {n: (l.type, l.use_shadow, round(l.volume_factor, 2)) for n, l in L.items()})


def run(name, n=3):
    ts = []
    for i in range(n):
        sc.render.filepath = os.path.join(out, "p6_" + name + ".jpg")
        t = time.time()
        bpy.ops.render.render(write_still=True)
        ts.append(time.time() - t)
    K.log("PROF6 %-26s min %.1f  (%s)" % (name, min(ts), " ".join("%.1f" % t for t in ts)))


run("warm", 1)
run("base")
for n in ("RimLight", "FlashSun"):
    if n in L:
        L[n].use_shadow = False
run("rim_flash_noshadow")
vf = L["MoonLight"].volume_factor
L["MoonLight"].volume_factor = 0.0
for n in ("RimLight", "FlashSun"):
    if n in L:
        L[n].volume_factor = 0.0
run("suns_volume0")
L["MoonLight"].use_shadow = False
run("moon_noshadow_too")
L["MoonLight"].use_shadow = True
fog = bpy.data.objects["Fog"]
sc_old, loc_old = tuple(fog.scale), tuple(fog.location)
fog.scale = (1100, 1300, 420)
fog.location = (0, -150, 208)
run("fog_small")
ee.use_volumetric_shadows = False
run("no_volshadows")
ee.use_volumetric_shadows = True
ee.volumetric_tile_size = '8'
run("tile8")
ee.taa_render_samples = 12
run("tile8_s12")
ee.taa_render_samples = 16
run("tile8_s16")
ee.volumetric_tile_size = '4'
ee.taa_render_samples = 12
run("tile4_s12")
