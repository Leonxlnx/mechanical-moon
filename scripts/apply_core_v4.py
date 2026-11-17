"""Apply the v4 core grade (dimmed core for the interior shots) to an already assembled scene and save it.

  blender -b blend/moon_scene.blend -P apply_core_v4.py -- [--saveas moon_scene.blend]
A fresh assemble.py run does the same through anim.grade(); this only avoids rebuilding the whole scene.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
import anim

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
name = argv[argv.index("--saveas") + 1] if "--saveas" in argv else "moon_scene.blend"
sc = bpy.context.scene
anim.grade_view(sc)
anim.core_grade(sc)
core = bpy.data.lights["CoreLight"]
gl = sc.node_tree.nodes["Glare"]
st, pm, col, nz = anim._core_nodes(bpy.data.materials["CoreGlow"].node_tree)
for f in (300, 524, 525, 560, 600, 659, 660, 749, 750, 885, 886, 1020, 1021, 1350):
    sc.frame_set(f)
    K.log("CHECK f%4d energy %6.0f vol %5.2f emit %5.1f/%4.1f col %.2f noise %.2f exp %.2f bloom %.2f/%.1f" % (
        f, core.energy, core.volume_factor, st.inputs["To Min"].default_value, st.inputs["To Max"].default_value,
        col.inputs["Color1"].default_value[2], nz.inputs["Scale"].default_value, sc.view_settings.exposure,
        gl.inputs["Strength"].default_value, gl.inputs["Threshold"].default_value))
sc.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=K.P("blend", name), compress=True)
K.log("SAVED", name)
