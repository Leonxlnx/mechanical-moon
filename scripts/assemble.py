"""Assemble the full scene from the module .blend files, light it, and optionally render stills / save.

  blender -b --factory-startup -P assemble.py -- [--stills hero,inside] [--res 960x540] [--samples 16]
                                                 [--frame 1] [--save] [--anim] [--tag name]
"""
import sys, os, math, time, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix, Euler
import common as K, config as C, mats, look
from mats import clear, N, L
from params import P
if os.environ.get("VARIANT"):
    import importlib as _il
    P = dict(P)
    P.update(_il.import_module("params_" + os.environ["VARIANT"]).P)

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, flag=False):
    if name in argv:
        return True if flag else argv[argv.index(name) + 1]
    return default


STILLS = [s for s in (arg("--stills", "") or "").split(",") if s]
RES = tuple(int(v) for v in arg("--res", "960x540").split("x"))
SAMPLES = int(arg("--samples", 16))
FRAME = int(arg("--frame", 1))
TAG = arg("--tag", "")
t0 = time.time()

sc = K.reset()
bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
MC = Vector(C.MOON_C)

# ------------------------------------------------------------------ modules
moon = bpy.data.objects.new("MOON", None)
sc.collection.objects.link(moon)
moon.location = MC
have = {}
for name, fn in (("CRUST", P.get("crust_blend", "crust.blend")), ("MECH", "mech.blend"), ("ARCH", "arch.blend"), ("ENV", "env.blend")):
    p = K.P("blend", fn)
    have[name] = False
    if os.path.exists(p):
        try:
            c = K.append_collection(p, name)
            have[name] = True
            if name != "ENV":
                for o in c.all_objects:
                    if o.parent is None:
                        o.parent = moon
        except Exception as e:
            K.log("could not append", name, e)
K.log("modules", have)

if not have["ARCH"]:
    me = bpy.data.meshes.new("StandInHull")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=6, radius=C.HULL_R)
    d = np.array([v.co[:] for v in bm.verts])
    f = C.open_field(K.normalize(d))
    bmesh.ops.delete(bm, geom=[v for v, ff in zip(bm.verts, f) if ff < C.HULL_OPEN_F], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.materials.append(mats.get("HullSkin"))
    h = bpy.data.objects.new("StandInHull", me)
    sc.collection.objects.link(h)
    h.parent = moon

if have["ENV"]:
    with bpy.data.libraries.load(K.P("blend", "env.blend"), link=False) as (src, dst):
        if "ENV_World" in src.worlds:
            dst.worlds = ["ENV_World"]
    if dst.worlds:
        sc.world = dst.worlds[0]
if sc.world is None:
    w = bpy.data.worlds.new("FallbackWorld")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.010, 0.018, 0.045, 1)
    sc.world = w
    if not have["ENV"]:
        me = bpy.data.meshes.new("StandInSea")
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=2, y_segments=2, size=4000)
        bm.to_mesh(me)
        bm.free()
        so = bpy.data.objects.new("StandInSea", me)
        sc.collection.objects.link(so)
        m = bpy.data.materials.new("StandInSeaMat")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.004, 0.008, 0.014, 1)
        b.inputs["Roughness"].default_value = 0.12
        me.materials.append(m)

if P.get("sky_baked", True) and os.path.exists(K.P("textures", "sky_bake.exr")):
    # baked equirect of ENV_World (see bake_sky.py): one texture fetch per sky pixel instead of ~20 noise evaluations
    w = bpy.data.worlds.new("SkyBaked")
    w.use_nodes = True
    wt = w.node_tree
    wt.nodes.clear()
    wo = wt.nodes.new("ShaderNodeOutputWorld")
    wb = wt.nodes.new("ShaderNodeBackground")
    we = wt.nodes.new("ShaderNodeTexEnvironment")
    we.image = bpy.data.images.load(K.P("textures", "sky_bake.exr"))
    we.interpolation = 'Linear'
    wt.links.new(we.outputs["Color"], wb.inputs["Color"])
    wt.links.new(wb.outputs[0], wo.inputs["Surface"])
    sc.world = w
if sc.world and sc.world.node_tree:
    wt = sc.world.node_tree
    for nd in [n for n in wt.nodes if n.type == 'BACKGROUND']:
        s_in = nd.inputs["Strength"]
        mul = wt.nodes.new("ShaderNodeMath")
        mul.name = "WorldGain"
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = P.get("world_strength", 1.0)
        if s_in.is_linked:
            wt.links.new(s_in.links[0].from_socket, mul.inputs[0])
        else:
            mul.inputs[0].default_value = s_in.default_value
        wt.links.new(mul.outputs[0], s_in)

# ------------------------------------------------------------------ materials: merge duplicates, rebuild canonical + hero
import re
for m in list(bpy.data.materials):
    mm = re.match(r"^(.*)\.\d{3}$", m.name)
    if mm and bpy.data.materials.get(mm.group(1)) is not None:
        m.user_remap(bpy.data.materials[mm.group(1)])
        bpy.data.materials.remove(m)
mats.rebuild_all()
look.apply(P)


def _scale_color(sock, k):
    c = sock.default_value
    sock.default_value = (c[0] * k[0], c[1] * k[1], c[2] * k[2], c[3])


def _node(mat_name, node_name):
    m = bpy.data.materials.get(mat_name)
    return m.node_tree.nodes.get(node_name) if m and m.node_tree else None


def _col_inputs(n):
    return [s for s in n.inputs if s.type == 'RGBA']


# environment overrides (node names documented by the ENV module)
n = _node("ENV_Rock", "ENV_RockColor")
if n:
    for s in _col_inputs(n):
        _scale_color(s, P.get("env_rock_mul", (1, 1, 1)))
n = _node("ENV_Rock", "ENV_RockRough")
if n:
    n.inputs["To Min"].default_value = P.get("env_rock_rough", (0.36, 0.68))[0]
    n.inputs["To Max"].default_value = P.get("env_rock_rough", (0.36, 0.68))[1]
# distant headlands: darker, matte copy of the rock so they sit back as silhouettes in the haze
_er = bpy.data.materials.get("ENV_Rock")
if _er:
    far = _er.copy()
    far.name = "ENV_RockFar"
    fn = far.node_tree.nodes.get("ENV_RockColor")
    if fn:
        for s_ in _col_inputs(fn):
            _scale_color(s_, P.get("env_far_mul", (0.45, 0.5, 0.6)))
    fr_ = far.node_tree.nodes.get("ENV_RockRough")
    if fr_:
        fr_.inputs["To Min"].default_value = 0.8
        fr_.inputs["To Max"].default_value = 0.95
    for o in bpy.data.objects:
        if o.name.startswith(("ENV_Island", "ENV_MidStack")) and o.type == 'MESH':
            for i_, ms in enumerate(o.material_slots):
                if ms.material == _er:
                    ms.material = far
n = _node("ENV_Water", "ENV_WaterColor")
if n:
    cs = _col_inputs(n)
    if len(cs) >= 2:
        _scale_color(cs[-1], P.get("env_crest_mul", (1, 1, 1)))
        _scale_color(cs[-2], P.get("env_trough_mul", (1, 1, 1)))
n = _node("ENV_Water", "ENV_FoamColor")
if n:
    cs = _col_inputs(n)
    if cs:
        _scale_color(cs[-1], P.get("env_foam_mul", (1, 1, 1)))
n = _node("ENV_Water", "ENV_WaterBump")
if n and "Strength" in n.inputs:
    n.inputs["Strength"].default_value *= P.get("env_bump_mul", 1.0)
n = _node("ENV_Water", "ENV_WaterRough")
if n:
    n.inputs["To Min"].default_value = P.get("env_water_rough", (0.13, 0.32))[0]
    n.inputs["To Max"].default_value = P.get("env_water_rough", (0.13, 0.32))[1]

# ------------------------------------------------------------------ dust motes drifting inside the shell (depth cue in the light)
rngd = np.random.default_rng(42)
nd = int(P.get("dust_count", 2600)) // 2 * 2
dp = K.normalize(rngd.standard_normal((nd, 3))) * (rngd.uniform(0.25, 1.0, nd) ** (1 / 2.2) * 88.0)[:, None]
ds = np.exp(rngd.uniform(np.log(0.035), np.log(0.13), nd))
octv = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
octf = np.array([[0, 2, 4], [2, 1, 4], [1, 3, 4], [3, 0, 4], [2, 0, 5], [1, 2, 5], [3, 1, 5], [0, 3, 5]])
dv = (octv[None, :, :] * ds[:, None, None] + dp[:, None, :]).reshape(-1, 3)
df = (octf[None, :, :] + (np.arange(nd) * 6)[:, None, None]).reshape(-1, 3)
dm = bpy.data.materials.new("DustMote")
dm.use_nodes = True
_b = dm.node_tree.nodes["Principled BSDF"]
_b.inputs["Base Color"].default_value = (1.0, 0.85, 0.6, 1)
_b.inputs["Emission Color"].default_value = (1.0, 0.7, 0.35, 1)
_b.inputs["Emission Strength"].default_value = P.get("dust_emit", 2.0)
for i in range(2):
    half = slice(i * (nd // 2) * 6, (i + 1) * (nd // 2) * 6)
    fsel = df[i * (nd // 2) * 8:(i + 1) * (nd // 2) * 8] - i * (nd // 2) * 6
    dob = K.obj_np("DUST_%d" % i, K.coll("FX"), dv[half], fsel, mats=[dm], smooth=False)
    dob.parent = moon
    dob.visible_shadow = False
    dob["spin_dps"] = 0.9 if i == 0 else -0.6
    dob.rotation_euler = (0.4 * i, 0.3, 0.0)

# ------------------------------------------------------------------ v3 scene edits
if P.get("remove_islands"):
    for o in list(bpy.data.objects):
        if o.name.startswith("ENV_Island"):
            bpy.data.objects.remove(o)
cg_ = bpy.data.objects.get("MECH_Cage")
if cg_:
    cg_.visible_shadow = False      # its filigree wrapped the light: strobing shadow sheets in the mist and 40 % less light
co_ = bpy.data.objects.get("MECH_Core")
if co_:
    s_ = P.get("core_scale", 1.0)
    co_.scale = (s_, s_, s_)
for m_ in bpy.data.materials:
    if m_.name.startswith("ARCH_Glass") and m_.node_tree:
        for n_ in m_.node_tree.nodes:
            if n_.type == 'BSDF_PRINCIPLED':
                c_ = list(n_.inputs["Emission Color"].default_value)
                mx = max(c_[:3]) or 1.0
                c_[:3] = [(v / mx) ** 1.8 for v in c_[:3]]         # push towards a saturated hue
                n_.inputs["Emission Color"].default_value = c_
            if n_.type == 'MAP_RANGE':
                n_.inputs["To Max"].default_value *= P.get("glass_boost", 1.0)

# soft horizon: far water dissolves into the sky colour (the fog volume cannot reach that far)
wm = bpy.data.materials.get("ENV_Water")
if wm and wm.node_tree and P.get("horizon_fade", True):
    wnt = wm.node_tree
    wout = next((n_ for n_ in wnt.nodes if n_.type == 'OUTPUT_MATERIAL' and n_.inputs["Surface"].is_linked), None)
    if wout:
        src_ = wout.inputs["Surface"].links[0].from_socket
        cdn = wnt.nodes.new("ShaderNodeCameraData")
        hmr = wnt.nodes.new("ShaderNodeMapRange")
        hmr.interpolation_type = 'SMOOTHSTEP'
        hmr.inputs["From Min"].default_value = P.get("horizon_near", 450.0)
        hmr.inputs["From Max"].default_value = P.get("horizon_far", 2400.0)
        wnt.links.new(cdn.outputs["View Distance"], hmr.inputs["Value"])
        hem = wnt.nodes.new("ShaderNodeEmission")
        hem.inputs["Color"].default_value = (*P.get("horizon_color", (0.045, 0.072, 0.13)), 1)
        hem.inputs["Strength"].default_value = P.get("world_strength", 1.0)
        hmix = wnt.nodes.new("ShaderNodeMixShader")
        wnt.links.new(hmr.outputs["Result"], hmix.inputs["Fac"])
        wnt.links.new(src_, hmix.inputs[1])
        wnt.links.new(hem.outputs[0], hmix.inputs[2])
        wnt.links.new(hmix.outputs[0], wout.inputs["Surface"])

# ------------------------------------------------------------------ lights
lc = K.coll("LIGHTS")


def sun(name, direction, strength, color, angle):
    sd = bpy.data.lights.new(name, 'SUN')
    sd.energy = strength
    sd.color = color
    sd.angle = math.radians(angle)
    so = bpy.data.objects.new(name, sd)
    so.rotation_euler = Vector(direction).normalized().to_track_quat('Z', 'Y').to_euler()
    so.location = (0, 0, 500)
    lc.objects.link(so)
    K._set(sd, shadow_maximum_resolution=P.get("sun_shadow_res", 0.30), use_shadow_jitter=True, shadow_jitter_overblur=10.0)
    return so


ld = bpy.data.lights.new("CoreLight", 'POINT')
ld.energy = P["core_power"]
ld.color = P["core_color"]
ld.shadow_soft_size = P["core_soft"]
K._set(ld, shadow_maximum_resolution=P.get("core_shadow_res", 0.10), use_shadow_jitter=True, shadow_jitter_overblur=10.0)
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=P.get("shadow_scale", 0.8))
K._set(ld, volume_factor=P.get("core_volume", 1.0), specular_factor=P.get("core_spec", 1.0))
core_light = bpy.data.objects.new("CoreLight", ld)
core_light.parent = moon
lc.objects.link(core_light)
ml = sun("MoonLight", P["moon_dir"], P["moon_strength"], P["moon_color"], P["moon_angle"])
K._set(ml.data, volume_factor=0.0, specular_factor=P.get("moon_spec", 1.0))          # sun volumetric shadows were the main render cost; the haze is lit by core + sky
# exterior-only receivers for the shadowless rim / flash lights (so they never leak into the interior)
ext_rc = bpy.data.collections.new("EXTERIOR_RECEIVERS")
ext_rc.use_fake_user = True
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith(("CRUST_", "ENV_", "MECH_Ext")):
        ext_rc.objects.link(o)
if P["rim_strength"] > 0:
    rl_ = sun("RimLight", P["rim_dir"], P["rim_strength"], P["rim_color"], 3.0)
    K._set(rl_.data, volume_factor=0.0, use_shadow=False)
    try:
        rl_.light_linking.receiver_collection = ext_rc
    except Exception as e:
        K.log("light linking:", e)

# broad golden glitter column on the sea: a big spec-only light standing in for the glowing opening
if P.get("sea_glint", 0) > 0:
    gd = bpy.data.lights.new("SeaGlint", 'POINT')
    gd.energy = P["sea_glint"]
    gd.color = P.get("sea_glint_color", (1.0, 0.62, 0.26))
    gd.shadow_soft_size = P.get("sea_glint_radius", 40.0)
    K._set(gd, use_shadow=False, diffuse_factor=0.0, specular_factor=1.0, volume_factor=0.0)
    go = bpy.data.objects.new("SeaGlint", gd)
    go.parent = moon
    go.location = Vector(C.OPEN_DIR) * 35.0
    lc.objects.link(go)
    sea_rc = bpy.data.collections.new("SEA_RECEIVERS")
    sea_rc.use_fake_user = True
    for o in bpy.data.objects:
        if o.name.startswith("ENV_Ocean"):
            sea_rc.objects.link(o)
    try:
        go.light_linking.receiver_collection = sea_rc
    except Exception as e:
        K.log("sea glint linking:", e)

for o in bpy.data.objects:
    if o.name.startswith(("MECH_Core", "MECH_Cage")):
        try:
            o.hide_probe_sphere = True
        except Exception as e:
            K.log("hide_probe_sphere:", e)
if P["probe"]:
    try:
        pr = bpy.data.lightprobes.new("InteriorProbe", 'SPHERE')
        pr.influence_type = 'ELIPSOID'
        pr.influence_distance = C.HULL_R - 0.5
        pr.falloff = 0.05
        pr.clip_start = 16.5
        pr.clip_end = 2000.0
        po = bpy.data.objects.new("InteriorProbe", pr)
        po.parent = moon
        lc.objects.link(po)
        K.log("probe attrs:", [a for a in dir(sc.eevee) if "probe" in a or "cubemap" in a])
        for a, v in (("gi_cubemap_resolution", '512'),):
            try:
                setattr(sc.eevee, a, v)
            except Exception as e:
                K.log("  probe res:", e)
    except Exception as e:
        K.log("probe failed:", e)

# ------------------------------------------------------------------ atmosphere (one big box, density shaped in the shader)
fme = bpy.data.meshes.new("Fog")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bm.to_mesh(fme)
bm.free()
fog = bpy.data.objects.new("Fog", fme)
fog.scale = (2600, 2600, 520)
fog.location = (0, 0, 258)
fog.display_type = 'WIRE'
lc.objects.link(fog)
fm = bpy.data.materials.new("FogMat")
nt = clear(fm)
out = N(nt, "ShaderNodeOutputMaterial", (900, 0))
vs = N(nt, "ShaderNodeVolumeScatter", (650, 0))
vs.inputs["Anisotropy"].default_value = P["fog_aniso"]
vs.inputs["Color"].default_value = (*P["fog_color"], 1)
geo = N(nt, "ShaderNodeNewGeometry", (-1300, 0))
sep = N(nt, "ShaderNodeSeparateXYZ", (-1050, 200))
L(nt, geo.outputs["Position"], sep.inputs[0])
# mist layer: exp(-z / h)
mz = N(nt, "ShaderNodeMath", (-800, 250), operation='DIVIDE')
mz.inputs[1].default_value = -P["fog_mist_h"]
L(nt, sep.outputs["Z"], mz.inputs[0])
me_ = N(nt, "ShaderNodeMath", (-600, 250), operation='EXPONENT')
L(nt, mz.outputs[0], me_.inputs[0])
mm_ = N(nt, "ShaderNodeMath", (-400, 250), operation='MULTIPLY')
mm_.inputs[1].default_value = P["fog_mist"]
L(nt, me_.outputs[0], mm_.inputs[0])
# distance from moon centre
dist = N(nt, "ShaderNodeVectorMath", (-1050, -100), operation='DISTANCE')
dist.inputs[1].default_value = MC
L(nt, geo.outputs["Position"], dist.inputs[0])
ins = N(nt, "ShaderNodeMapRange", (-800, -50), interpolation_type='SMOOTHSTEP', inputs={"From Min": 84.0, "From Max": 99.0, "To Min": P["fog_inside"], "To Max": 0.0})
L(nt, dist.outputs["Value"], ins.inputs["Value"])
# the halo only starts at the shell so the mechanism itself stays clear
hgate = N(nt, "ShaderNodeMapRange", (-800, -180), interpolation_type='SMOOTHSTEP', inputs={"From Min": P.get("fog_halo_r0", 66.0), "From Max": P.get("fog_halo_r1", 96.0), "To Min": 0.0, "To Max": 1.0})
L(nt, dist.outputs["Value"], hgate.inputs["Value"])
hl = N(nt, "ShaderNodeMath", (-800, -300), operation='SUBTRACT')
hl.inputs[1].default_value = 96.0
L(nt, dist.outputs["Value"], hl.inputs[0])
hl2 = N(nt, "ShaderNodeMath", (-620, -300), operation='DIVIDE')
hl2.inputs[1].default_value = -P["fog_halo_len"]
L(nt, hl.outputs[0], hl2.inputs[0])
hl3 = N(nt, "ShaderNodeMath", (-440, -300), operation='EXPONENT')
L(nt, hl2.outputs[0], hl3.inputs[0])
hl4 = N(nt, "ShaderNodeMath", (-260, -300), operation='MULTIPLY', use_clamp=False)
hl4.inputs[1].default_value = P["fog_halo"]
L(nt, hl3.outputs[0], hl4.inputs[0])
hl5 = N(nt, "ShaderNodeMath", (-80, -300), operation='MINIMUM')
hl5.inputs[1].default_value = P["fog_halo"]
L(nt, hl4.outputs[0], hl5.inputs[0])
# noise modulation (drifts over time via the mapping node)
mp = N(nt, "ShaderNodeMapping", (-1050, -550))
mp.name = "FogDrift"
L(nt, geo.outputs["Position"], mp.inputs["Vector"])
nz = N(nt, "ShaderNodeTexNoise", (-800, -550), inputs={"Scale": P["fog_noise_scale"], "Detail": 4.0, "Roughness": 0.6})
L(nt, mp.outputs["Vector"], nz.inputs["Vector"])
nm = N(nt, "ShaderNodeMapRange", (-560, -550), inputs={"From Min": 0.25, "From Max": 0.75, "To Min": 1.0 - P["fog_noise"], "To Max": 1.0 + P["fog_noise"]})
L(nt, nz.outputs["Fac"], nm.inputs["Value"])
hl6 = N(nt, "ShaderNodeMath", (80, -420), operation='MULTIPLY')
L(nt, hl5.outputs[0], hl6.inputs[0])
L(nt, hgate.outputs["Result"], hl6.inputs[1])
a1 = N(nt, "ShaderNodeMath", (-150, 150), operation='ADD')
L(nt, mm_.outputs[0], a1.inputs[0])
L(nt, hl6.outputs[0], a1.inputs[1])
a2 = N(nt, "ShaderNodeMath", (50, 150), operation='ADD')
a2.inputs[1].default_value = P["fog_base"]
L(nt, a1.outputs[0], a2.inputs[0])
a3 = N(nt, "ShaderNodeMath", (250, 100), operation='MULTIPLY')
L(nt, a2.outputs[0], a3.inputs[0])
L(nt, nm.outputs["Result"], a3.inputs[1])
a4 = N(nt, "ShaderNodeMath", (450, 50), operation='ADD')
L(nt, a3.outputs[0], a4.inputs[0])
L(nt, ins.outputs["Result"], a4.inputs[1])
L(nt, a4.outputs[0], vs.inputs["Density"])
L(nt, vs.outputs[0], out.inputs["Volume"])
fme.materials.append(fm)

# ------------------------------------------------------------------ render + compositor
K.setup_eevee(sc, samples=SAMPLES, res=RES)
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=P.get("shadow_scale", 0.8))
sc.view_settings.exposure = P["exposure"]
try:
    sc.view_settings.look = P["look"]
except Exception as e:
    K.log("look:", e)
sc.use_nodes = True
ct = sc.node_tree
ct.nodes.clear()
rl = ct.nodes.new("CompositorNodeRLayers")
gl = ct.nodes.new("CompositorNodeGlare")
co = ct.nodes.new("CompositorNodeComposite")
try:
    gl.glare_type = 'BLOOM'
    gl.quality = 'HIGH'
except Exception as e:
    K.log("glare type:", e)
for nm_, val in (("Threshold", P["bloom_threshold"]), ("Strength", P["bloom_strength"]), ("Size", P["bloom_size"]),
                 ("Saturation", P["bloom_sat"]), ("Smoothness", 0.4)):
    if nm_ in gl.inputs:
        gl.inputs[nm_].default_value = val
    else:
        K.log("glare input missing:", nm_, [i.name for i in gl.inputs])
ct.links.new(rl.outputs["Image"], gl.inputs["Image"])
ct.links.new(gl.outputs["Image"], co.inputs["Image"])
try:
    sc.render.compositor_device = 'GPU'
except Exception as e:
    K.log("compositor device:", e)

# ------------------------------------------------------------------ animation
if arg("--anim", flag=True) or arg("--save", flag=True):
    import anim
    anim.apply(sc, moon)
sc.frame_set(FRAME)
K.log("assembled in %.1fs, tris %d" % (time.time() - t0, K.tri_count()))

# ------------------------------------------------------------------ stills
od, orr, ou = Vector(C.OPEN_DIR), Vector(C.OPEN_RIGHT), Vector(C.OPEN_UP)
VIEWS = {
    "hero": (C.SHORE_CAM, (0, 0, 92), 24),
    "wide": ((-150, -420, 14), (10, 0, 118), 24),
    "low": ((30, -250, 4.0), (0, 0, 120), 20),
    "inside": (MC + od * 84 + ou * 6, MC - od * 60, 22),
    "rings": (MC + od * 70 + orr * 46 + ou * 18, MC + orr * 4, 40),
    "rim": (MC + od * 150 + orr * 95 + ou * 60, MC + orr * 62 + ou * 40 + od * 60, 50),
    "close": (MC + (od * 0.35 + orr * 0.9 + ou * 0.25).normalized() * 116, MC + (od * 0.62 + orr * 0.72 + ou * 0.3).normalized() * 100, 35),
    "top": (MC + Vector((60, -210, 240)), MC + Vector((0, 0, -10)), 28),
    "under": ((10, -60, 5), MC + od * 30, 18),
    "side": (MC + Vector((-330, -90, 30)), MC, 35),
    "back": (MC + Vector((120, 330, 80)), MC, 35),
    "ext": (MC + Vector((150, -150, -30)), MC + Vector((60, -40, -10)), 28),
    "s1": ((-60, -345, 14), (0, -10, 88), 24), "s2": ((-60, -345, 22), (0, -10, 88), 24),
    "s3": ((-20, -345, 14), (0, -10, 88), 24), "s4": ((-20, -345, 22), (0, -10, 88), 24),
    "s5": ((15, -340, 16), (0, -10, 88), 24), "s6": ((-95, -340, 18), (0, -10, 88), 24),
    "s7": ((-40, -362, 26), (0, -10, 88), 24), "s8": ((-40, -385, 36), (0, -10, 84), 28),
}
for v in STILLS:
    loc, tgt, lens = VIEWS[v]
    K.quick_render(K.P("renders", "stills", "%s%s.png" % (v, ("_" + TAG) if TAG else "")), loc, tgt, lens=lens, res=RES, samples=SAMPLES)
if arg("--save", flag=True):
    K.save_blend(K.P("blend", arg("--saveas", "moon_scene.blend")))
K.log("ASSEMBLE DONE %.1fs" % (time.time() - t0))
