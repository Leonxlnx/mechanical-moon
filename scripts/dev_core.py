"""Look-dev for the interior glare: render the same frames with different core settings in one Blender session.

  blender -b blend/moon_scene.blend -P dev_core.py -- --variants variants.json [--res 960x540] [--out dir]

variants.json: [{"name": "b", "frames": [600, 700], "light": 0.7, "vol": 4.0, "emit": 60, "limb": 8,
                 "bloom_s": 0.12, "bloom_t": 9.0, "exp_add": 0.0, "fog_in": 1.0}, ...]
Missing keys keep the value stored in the scene (animated values are read at the frame, then overridden).
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


sc = bpy.context.scene
bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
RES = tuple(int(v) for v in arg("--res", "960x540").split("x"))
OUT = arg("--out", K.P("renders", "core_dev"))
os.makedirs(OUT, exist_ok=True)
K.setup_eevee(sc, samples=12, res=RES)
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=P.get("shadow_scale", 0.8))
sc.eevee.use_fast_gi = False
sc.eevee.volumetric_samples = 64
sc.eevee.volumetric_end = 900.0
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
sc.render.image_settings.file_format = 'JPEG'
sc.render.image_settings.quality = 92
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
core = bpy.data.lights["CoreLight"]
glare = sc.node_tree.nodes.get("Glare")
cg = bpy.data.materials["CoreGlow"].node_tree
emit_node = next(n for n in cg.nodes if n.type == 'MAP_RANGE' and n.inputs["To Min"].default_value > 20.0)
fog = bpy.data.materials["FogMat"].node_tree
fog_in = next((n for n in fog.nodes if n.type == 'MAP_RANGE' and abs(n.inputs["To Min"].default_value - P["fog_inside"]) < 1e-7), None)
BASE = dict(vol=core.volume_factor, emit=emit_node.inputs["To Min"].default_value, limb=emit_node.inputs["To Max"].default_value,
            fog_in=fog_in.inputs["To Min"].default_value if fog_in else 0.0, spec=core.specular_factor)
K.log("DEV base:", BASE)


def fcurves(idb):
    """All f-curves of the action (every slot: a scene and its compositor tree share one slotted action)."""
    ad = getattr(idb, "animation_data", None)
    if not (ad and ad.action):
        return []
    out = []
    for layer in getattr(ad.action, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out or list(ad.action.fcurves)


ANIM = fcurves(core) + fcurves(sc) + fcurves(sc.node_tree) + fcurves(cg) + fcurves(bpy.data.materials["CoreGlow"])
ANIM = list({fc.as_pointer(): fc for fc in ANIM}.values())
K.log("DEV muting %d f-curves" % len(ANIM))


def cam_for(f):
    c = marks[0][1]
    for mf, mc in marks:
        if mf <= f:
            c = mc
    return c


for v in json.load(open(arg("--variants"), encoding="utf-8")):
    for f in v["frames"]:
        for fc in ANIM:
            fc.mute = False
        sc.frame_set(f)
        sc.camera = cam_for(f)
        e0, x0 = core.energy, sc.view_settings.exposure
        t0, s0 = glare.inputs["Threshold"].default_value, glare.inputs["Strength"].default_value
        for fc in ANIM:
            fc.mute = True
        core.energy = e0 * v.get("light", 1.0)
        core.volume_factor = v.get("vol", BASE["vol"])
        core.specular_factor = v.get("spec", BASE["spec"])
        emit_node.inputs["To Min"].default_value = v.get("emit", BASE["emit"])
        emit_node.inputs["To Max"].default_value = v.get("limb", BASE["limb"])
        if fog_in:
            fog_in.inputs["To Min"].default_value = BASE["fog_in"] * v.get("fog_in", 1.0)
        mixn = next(n for n in cg.nodes if n.type == 'MIX_RGB')
        if "col_c" in v:
            mixn.inputs["Color1"].default_value = (*v["col_c"], 1)
        if "col_l" in v:
            mixn.inputs["Color2"].default_value = (*v["col_l"], 1)
        if "noise" in v:
            cg.nodes["CorePlasma"].inputs["Scale"].default_value = v["noise"]
        if "plasma" in v:
            pmn = next(n for n in cg.nodes if n.type == 'MAP_RANGE' and n is not emit_node)
            pmn.inputs["To Min"].default_value, pmn.inputs["To Max"].default_value = v["plasma"]
        if "limb_pow" in v:
            next(n for n in cg.nodes if n.type == 'MATH' and n.operation == 'POWER').inputs[1].default_value = v["limb_pow"]
        glare.inputs["Threshold"].default_value = v.get("bloom_t", t0)
        glare.inputs["Strength"].default_value = v.get("bloom_s", s0)
        sc.view_settings.exposure = x0 + v.get("exp_add", 0.0)
        sc.render.filepath = os.path.join(OUT, "%s_%04d.jpg" % (v["name"], f))
        t = time.time()
        bpy.ops.render.render(write_still=True)
        K.log("DEV %s frame %d  %.1fs  (energy %.0f exp %.2f bloom %.2f/%.1f)" % (
            v["name"], f, time.time() - t, core.energy, sc.view_settings.exposure,
            glare.inputs["Strength"].default_value, glare.inputs["Threshold"].default_value))
K.log("DEV DONE")
