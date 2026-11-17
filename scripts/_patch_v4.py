"""v4: the core is dimmed for the interior shots (it was blown out) - per-shot keys for light, volume, emission (kept for reference)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def sub(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)


sub('look.py', [
    ('''    pm = N(nt, "ShaderNodeMapRange", (-680, -200), inputs={"From Min": 0.3, "From Max": 0.7, "To Min": 0.45, "To Max": 1.35})
    L(nt, nz.outputs["Fac"], pm.inputs["Value"])
    col = N(nt, "ShaderNodeMixRGB", (-420, 250))''',
     '''    pm = N(nt, "ShaderNodeMapRange", (-680, -200), inputs={"From Min": 0.3, "From Max": 0.7, "To Min": 0.45, "To Max": 1.35})
    pm.name = "CorePlasmaRange"
    L(nt, nz.outputs["Fac"], pm.inputs["Value"])
    col = N(nt, "ShaderNodeMixRGB", (-420, 250))
    col.name = "CoreColor"'''),
    ('''    L(nt, fac.outputs[0], st.inputs["Value"])
    sm = N(nt, "ShaderNodeMath", (-150, 0), operation='MULTIPLY')''',
     '''    st.name = "CoreStrength"
    L(nt, fac.outputs[0], st.inputs["Value"])
    sm = N(nt, "ShaderNodeMath", (-150, 0), operation='MULTIPLY')'''),
])

sub('shots.py', [
    ('''# per-shot grade: exposure (start, end), bloom threshold, bloom strength
GRADE = {
    "01_sea": ((-0.25, -0.25), 2.2, 0.32), "02_reveal": ((-0.4, -0.4), 2.2, 0.32), "03_side": ((-0.4, -0.4), 2.2, 0.30),
    "04_crust": ((-0.4, -0.4), 2.4, 0.30), "05_flyin": ((-0.45, -1.0), 4.5, 0.28), "06_rings": ((-1.25, -1.25), 9.0, 0.24),
    "07_galleries": ((-1.05, -1.05), 8.0, 0.24), "08_below": ((-0.75, -0.75), 4.0, 0.28), "09_ring": ((-0.3, -0.3), 2.4, 0.30),
    "10_aerial": ((-0.2, -0.2), 2.4, 0.30), "11_final": ((-0.4, -0.4), 2.2, 0.32),
}''',
     '''# per-shot grade: exposure (start, end), bloom threshold, bloom strength (scalars or (start, end))
GRADE = {
    "01_sea": ((-0.25, -0.25), 2.2, 0.32), "02_reveal": ((-0.4, -0.4), 2.2, 0.32), "03_side": ((-0.4, -0.4), 2.2, 0.30),
    "04_crust": ((-0.4, -0.4), 2.4, 0.30), "05_flyin": ((-0.45, -0.85), (4.5, 6.0), (0.28, 0.18)), "06_rings": ((-1.10, -1.10), 6.0, 0.18),
    "07_galleries": ((-0.90, -0.90), 8.0, 0.20), "08_below": ((-0.75, -0.75), 4.0, 0.22), "09_ring": ((-0.3, -0.3), 2.4, 0.30),
    "10_aerial": ((-0.2, -0.2), 2.4, 0.30), "11_final": ((-0.4, -0.4), 2.2, 0.32),
}
# per-shot core: (light multiplier, volume-scatter multiplier, centre emission, limb emission) at shot start / end.
# From the sea the core may blaze; seen from inside it is dimmed so the mechanism stays readable (no white veil).
CORE_OUT = (1.0, 1.0, 300.0, 18.0)
CORE_IN = (0.60, 0.29, 45.0, 2.5)
CORE = {
    "05_flyin": ((0.85, 0.60, 120.0, 8.0), CORE_IN),
    "06_rings": (CORE_IN, CORE_IN),
    "07_galleries": (CORE_IN, CORE_IN),
    "08_below": ((0.80, 0.50, 80.0, 10.0), (0.80, 0.50, 80.0, 10.0)),
}
# core surface look: (centre colour, limb colour, plasma noise scale, plasma range)
CORE_LOOK_OUT = ((1.0, 0.86, 0.62), (1.0, 0.36, 0.07), 0.33, (0.45, 1.35))
CORE_LOOK_IN = ((1.0, 0.74, 0.38), (1.0, 0.28, 0.03), 0.90, (0.60, 1.25))
CORE_LOOK_SHOTS = ("05_flyin", "06_rings", "07_galleries")'''),
    ('''    sh["key"] = KEY.get(sh["name"], (C_KEY, 1.0))''',
     '''    sh["key"] = KEY.get(sh["name"], (C_KEY, 1.0))
    sh["core"] = CORE.get(sh["name"], (CORE_OUT, CORE_OUT))
    sh["core_look"] = CORE_LOOK_IN if sh["name"] in CORE_LOOK_SHOTS else CORE_LOOK_OUT'''),
])

sub('anim.py', [
    ('''def _fcurves(ob):
    ad = ob.animation_data
    return ad.action.fcurves if ad and ad.action else []''',
     '''def _fcurves(ob):
    ad = ob.animation_data
    return ad.action.fcurves if ad and ad.action else []


def _all_fcurves(idb):
    """Every f-curve of the ID's action, across all slots (a scene and its compositor tree share one slotted action)."""
    ad = getattr(idb, "animation_data", None)
    if not (ad and ad.action):
        return []
    out = []
    for layer in getattr(ad.action, "layers", []):
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out or list(ad.action.fcurves)'''),
    ('''def grade(sc):
    """Per-shot exposure and bloom (interiors are far brighter than the night exterior)."""
    gl = sc.node_tree.nodes.get("Glare") if sc.node_tree else None
    for sh in SHOTS:
        f0, f1 = sh["frames"]
        (e0, e1), thr, stg = sh["grade"]
        for f, e in ((f0, e0), (f1, e1)):
            sc.view_settings.exposure = e
            sc.view_settings.keyframe_insert("exposure", frame=f)
            if gl:
                for nm, v in (("Threshold", thr), ("Strength", stg)):
                    if nm in gl.inputs:
                        gl.inputs[nm].default_value = v
                        gl.inputs[nm].keyframe_insert("default_value", frame=f)
    key = bpy.data.objects.get("MoonLight")''',
     '''def _pair(v):
    return tuple(v) if isinstance(v, (tuple, list)) else (v, v)


def grade_view(sc):
    """Per-shot exposure and bloom (interiors are far brighter than the night exterior)."""
    gl = sc.node_tree.nodes.get("Glare") if sc.node_tree else None
    for sh in SHOTS:
        f0, f1 = sh["frames"]
        (e0, e1), thr, stg = sh["grade"]
        thr, stg = _pair(thr), _pair(stg)
        for i, (f, e) in enumerate(((f0, e0), (f1, e1))):
            sc.view_settings.exposure = e
            sc.view_settings.keyframe_insert("exposure", frame=f)
            if gl:
                for nm, v in (("Threshold", thr[i]), ("Strength", stg[i])):
                    if nm in gl.inputs:
                        gl.inputs[nm].default_value = v
                        gl.inputs[nm].keyframe_insert("default_value", frame=f)
    for idb in (sc, sc.node_tree):
        for fc in _all_fcurves(idb):
            if "exposure" in fc.data_path or "default_value" in fc.data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'


def _core_nodes(nt):
    mr = [n for n in nt.nodes if n.type == 'MAP_RANGE']
    st = nt.nodes.get("CoreStrength") or max(mr, key=lambda n: n.inputs["To Min"].default_value)
    pm = nt.nodes.get("CorePlasmaRange") or next(n for n in mr if n is not st)
    col = nt.nodes.get("CoreColor") or next(n for n in nt.nodes if n.type == 'MIX_RGB')
    return st, pm, col, nt.nodes["CorePlasma"]


def core_grade(sc):
    """Per-shot core: light power, volume scatter, surface emission and colour (dimmed inside the moon)."""
    if sc.get("core_grade_applied"):
        K.log("core grade already applied - skipped")
        return
    lo = bpy.data.objects.get("CoreLight")
    cgm = bpy.data.materials.get("CoreGlow")
    if not (lo and cgm):
        return
    ld = lo.data

    def shot_keys(sh):
        """Frames + geometrically interpolated (light, volume, emit, limb) for one shot."""
        f0, f1 = sh["frames"]
        a, b = sh["core"]
        fs = [f0, f1] if a == b else sorted(set(list(range(f0, f1, 10)) + [f1]))
        out = []
        for f in fs:
            t = (f - f0) / max(f1 - f0, 1)
            out.append((f, tuple(a[i] * (b[i] / a[i]) ** t for i in range(4))))
        return out

    def mul_at(f):
        for sh in SHOTS:
            f0, f1 = sh["frames"]
            if f0 <= f <= f1 or (sh is SHOTS[-1] and f > f1):
                a, b = sh["core"]
                t = min(max((f - f0) / max(f1 - f0, 1), 0.0), 1.0)
                return a[0] * (b[0] / a[0]) ** t
        return 1.0

    # light power: scale the existing pulse / surge keys and add keys on both sides of every cut
    fc = next(c for c in _all_fcurves(ld) if c.data_path == "energy")
    frames = sorted(set([int(round(kp.co.x)) for kp in fc.keyframe_points] + [f for sh in SHOTS for f, _ in shot_keys(sh)]))
    orig = {f: fc.evaluate(f) for f in frames}
    for f in frames:
        ld.energy = orig[f] * mul_at(f)
        ld.keyframe_insert("energy", frame=f)
    vol0 = ld.volume_factor
    st, pm, col, nz = _core_nodes(cgm.node_tree)
    for sh in SHOTS:
        for f, (_, vol, emit, limb) in shot_keys(sh):
            ld.volume_factor = vol0 * vol
            ld.keyframe_insert("volume_factor", frame=f)
            st.inputs["To Min"].default_value = emit
            st.inputs["To Max"].default_value = limb
            st.inputs["To Min"].keyframe_insert("default_value", frame=f)
            st.inputs["To Max"].keyframe_insert("default_value", frame=f)
        cc, cl, nscale, prange = sh["core_look"]
        for f in sh["frames"]:
            col.inputs["Color1"].default_value = (*cc, 1)
            col.inputs["Color2"].default_value = (*cl, 1)
            nz.inputs["Scale"].default_value = nscale
            pm.inputs["To Min"].default_value, pm.inputs["To Max"].default_value = prange
            for sock in (col.inputs["Color1"], col.inputs["Color2"], nz.inputs["Scale"], pm.inputs["To Min"], pm.inputs["To Max"]):
                sock.keyframe_insert("default_value", frame=f)
    ld.volume_factor = vol0
    for c in _all_fcurves(ld):
        for kp in c.keyframe_points:
            kp.interpolation = 'LINEAR'
    for c in _all_fcurves(cgm.node_tree):
        if 'CorePlasma"].inputs[1]' in c.data_path or c.data_path.endswith('inputs["W"].default_value'):
            continue                                   # the plasma drift keeps its own linear extrapolation
        for kp in c.keyframe_points:
            kp.interpolation = 'LINEAR'
    sc["core_grade_applied"] = 1
    K.log("core grade keyed")


def grade(sc):
    grade_view(sc)
    core_grade(sc)
    key = bpy.data.objects.get("MoonLight")'''),
    ('''        for fc in rim.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    for idb in (sc, sc.node_tree):
        if idb and idb.animation_data and idb.animation_data.action:
            for fc in idb.animation_data.action.fcurves:
                if "exposure" in fc.data_path or "default_value" in fc.data_path:
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR\'''',
     '''        for fc in rim.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR\''''),
])
print("v4 patch ok")
