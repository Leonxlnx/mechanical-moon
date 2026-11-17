"""v3 part 2: assembly, look, per-shot key light (kept for reference)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def sub(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)


sub('look.py', [
    ('''    mar.inputs["Color2"].default_value = (0.80, 0.86, 1.0, 1)''', '''    mar.inputs["Color2"].default_value = P.get("maria_tint", (0.80, 0.86, 1.0, 1))'''),
    ('''    s1 = N(nt, "ShaderNodeMapRange", (-760, 150), inputs={"From Min": 0.0, "From Max": 0.022, "To Min": 1.0, "To Max": 0.0})''',
     '''    s1 = N(nt, "ShaderNodeMapRange", (-760, 150), inputs={"From Min": 0.0, "From Max": P.get("hull_seam", 0.022), "To Min": 1.0, "To Max": 0.0})'''),
    ('''    es.inputs[2].default_value = 0.10
    L(nt, glow.outputs[0], es.inputs[0])
    dark = N(nt, "ShaderNodeMixRGB", (-300, -150))
    dark.inputs["Color1"].default_value = (0.40, 0.25, 0.09, 1)''',
     '''    es.inputs[2].default_value = 0.03
    L(nt, glow.outputs[0], es.inputs[0])
    dark = N(nt, "ShaderNodeMixRGB", (-300, -150))
    dark.inputs["Color1"].default_value = (0.20, 0.12, 0.045, 1)'''),
    ('''"To Min": P.get("core_emit", 220.0), "To Max": P.get("core_emit_limb", 14.0)})''', '''"To Min": P.get("core_emit", 220.0), "To Max": P.get("core_emit_limb", 14.0)})'''),
])

sub('assemble.py', [
    ('''nd = 2600
dp = K.normalize''', '''nd = int(P.get("dust_count", 2600)) // 2 * 2
dp = K.normalize'''),
    ('''# ------------------------------------------------------------------ lights
lc = K.coll("LIGHTS")''',
     '''# ------------------------------------------------------------------ v3 scene edits
if P.get("remove_islands"):
    for o in list(bpy.data.objects):
        if o.name.startswith("ENV_Island"):
            bpy.data.objects.remove(o)
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

# ------------------------------------------------------------------ lights
lc = K.coll("LIGHTS")'''),
])

sub('shots.py', [
    ('''    sh["rim"] = {"04_crust": 1.6, "09_ring": 2.4}.get(sh["name"], 1.0)''',
     '''    sh["rim"] = {"04_crust": 1.3, "09_ring": 1.6}.get(sh["name"], 1.0)
    sh["key"] = KEY.get(sh["name"], (C_KEY, 1.0))'''),
    ('''# per-shot grade: exposure (start, end), bloom threshold, bloom strength''',
     '''# per-shot key-light cheat: (direction TOWARDS the light, strength multiplier). Raking light for every camera position.
C_KEY = (-0.90, -0.18, 0.40)
KEY = {
    "03_side": ((-0.45, 0.78, 0.45), 1.0),
    "04_crust": ((-0.25, 0.35, 0.90), 1.0),
    "09_ring": ((0.30, 0.50, 0.80), 0.9),
    "10_aerial": ((-0.95, 0.10, 0.28), 1.0),
}
# per-shot grade: exposure (start, end), bloom threshold, bloom strength'''),
])

sub('anim.py', [
    ('''    rim = bpy.data.lights.get("RimLight")
    if rim and os.environ.get("VARIANT"):''',
     '''    key = bpy.data.objects.get("MoonLight")
    if key:
        base_e = key.data.energy
        for sh in SHOTS:
            d, mul = sh["key"]
            for f in sh["frames"]:
                key.rotation_euler = Vector(d).normalized().to_track_quat('Z', 'Y').to_euler()
                key.keyframe_insert("rotation_euler", frame=f)
                key.data.energy = base_e * mul
                key.data.keyframe_insert("energy", frame=f)
        key.data.energy = base_e
        for idb in (key, key.data):
            for fc in idb.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    rim = bpy.data.lights.get("RimLight")
    if rim:'''),
])
print("v3b patch ok")
