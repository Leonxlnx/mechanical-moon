"""Re-key only the core SURFACE look (emission, colours, plasma) and the per-shot exposure/bloom from shots.py
on a scene that already has the v4 core grade (light power / volume keys stay untouched).

  blender -b blend/moon_scene.blend -P apply_core_v5.py -- [--saveas moon_scene.blend]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
import anim
from shots import SHOTS

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
name = argv[argv.index("--saveas") + 1] if "--saveas" in argv else "moon_scene.blend"
sc = bpy.context.scene
assert sc.get("core_grade_applied"), "run apply_core_v4.py / assemble.py first"
anim.grade_view(sc)
cgm = bpy.data.materials["CoreGlow"]
st, pm, col, nz = anim._core_nodes(cgm.node_tree)
for sh in SHOTS:
    f0, f1 = sh["frames"]
    a, b = sh["core"]
    fs = [f0, f1] if a == b else sorted(set(list(range(f0, f1, 10)) + [f1]))
    for f in fs:
        t = (f - f0) / max(f1 - f0, 1)
        emit, limb = (a[i] * (b[i] / a[i]) ** t for i in (2, 3))
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
for c in anim._all_fcurves(cgm.node_tree):
    if 'CorePlasma"].inputs[1]' in c.data_path or c.data_path.endswith('inputs["W"].default_value'):
        continue
    for kp in c.keyframe_points:
        kp.interpolation = 'LINEAR'
core = bpy.data.lights["CoreLight"]
gl = sc.node_tree.nodes["Glare"]
for f in (300, 524, 525, 600, 659, 660, 749, 750, 885, 886, 1020, 1021, 1350):
    sc.frame_set(f)
    K.log("CHECK f%4d energy %6.0f vol %5.2f emit %5.1f/%4.1f colG %.2f/%.2f plasma %.2f-%.2f exp %.2f bloom %.2f/%.1f" % (
        f, core.energy, core.volume_factor, st.inputs["To Min"].default_value, st.inputs["To Max"].default_value,
        col.inputs["Color1"].default_value[1], col.inputs["Color2"].default_value[1],
        pm.inputs["To Min"].default_value, pm.inputs["To Max"].default_value, sc.view_settings.exposure,
        gl.inputs["Strength"].default_value, gl.inputs["Threshold"].default_value))
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=K.P("blend", name), compress=True)
K.log("SAVED", name)
