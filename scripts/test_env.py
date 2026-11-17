"""Test renders of the environment with the standard test rig (never saved into env.blend).
Usage: blender -b --factory-startup -P test_env.py -- [view names ...] [f=<frame>[,<frame>...]] [tag=<suffix>] [glow]
Views: shore wide low high rocks sky under crane zenith   (default: shore low high rocks sky)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, time
import common as K, config as C

VIEWS = {
    #        camera location            target                  lens
    "shore": (C.SHORE_CAM,              C.SHORE_CAM_TARGET,     30),
    "wide":  (C.SHORE_CAM,              (0.0, 0.0, 95.0),       22),
    "low":   ((-22.0, -235.0, 6.5),     (0.0, 0.0, 42.0),       24),
    "high":  ((-150.0, -270.0, 200.0),  (0.0, -50.0, 0.0),      28),
    "rocks": ((-64.0, -339.0, 15.0),    (-28.0, -316.0, 1.0),   30),
    "sky":   ((-40.0, -340.0, 9.0),     (-300.0, 0.0, 330.0),   24),
    "under": ((0.0, -15.0, 14.0),       (-80.0, -330.0, 12.0),  24),
    "crane": ((-10.0, -345.0, 46.0),    (0.0, 0.0, 70.0),       28),
    "zenith": ((-40.0, -340.0, 9.0),    (-60.0, -330.0, 500.0), 20),
    "dolly": ((-95.0, -340.0, 9.0),     (0.0, 0.0, 110.0),      28),
}

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
frames, tag, names, glow = [60], "", [], False
for a in args:
    if a.startswith("f="):
        frames = [int(v) for v in a[2:].split(",")]
    elif a.startswith("tag="):
        tag = a[4:]
    elif a == "glow":
        glow = True          # make the stand-in moon emissive gold (approximates the glowing mechanism in reflections)
    else:
        names.append(a)
names = names or ["shore", "low", "high", "rocks", "sky"]

path = K.P("blend", "env.blend")
if not os.path.exists(path):
    import build_env
    build_env.main()
bpy.ops.wm.open_mainfile(filepath=path)
K.add_test_rig(fog=True, stand_in_moon=True)
# the real moon is cracked open towards the shore; the closed stand-in must not swallow the core light
bpy.data.objects["StandInMoon"].visible_shadow = False
# animation sanity check: the frame drivers must advance the ocean time and the shader clocks
sc = bpy.context.scene
for fr in (frames[0], frames[0] + 15):
    sc.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    oc = bpy.data.objects["ENV_Ocean"].evaluated_get(dg)
    wt = sc.world.evaluated_get(dg).node_tree.nodes["ENV_Time"].outputs[0].default_value
    mt = bpy.data.materials["ENV_Water"].evaluated_get(dg).node_tree.nodes["ENV_Time"].outputs[0].default_value
    print("ENVTEST anim frame %d: swell.time=%.3f chop.time=%.3f world ENV_Time=%.3f water ENV_Time=%.3f zmax=%.2f" % (
        fr, oc.modifiers["ENV_Swell"].time, oc.modifiers["ENV_Chop"].time, wt, mt, max(v.co.z for v in oc.data.vertices)))
t0 = time.time()


def render_all(tag):
    for i, frame in enumerate(frames):
        for n in names:
            loc, tgt, lens = VIEWS[n]
            suffix = tag + ("" if i == 0 else "_f%d" % frame)
            dt = K.quick_render(K.P("renders", "env_%s%s.png" % (n, suffix)), loc, tgt, lens=lens, res=(960, 540), samples=16, frame=frame)
            print("ENVTEST %s%s frame %d: %.1fs" % (n, suffix, frame, dt))


render_all(tag)
if glow:     # second pass: emissive gold stand-in moon, first frame only, sea views only
    bsdf = bpy.data.materials["StandInMoonMat"].node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.62, 0.30, 1)
    bsdf.inputs["Emission Strength"].default_value = 3.0
    frames = frames[:1]
    names = [n for n in names if n in ("low", "crane", "shore", "wide", "high")]
    render_all(tag + "_glow")
print("ENVTEST DONE %.1fs" % (time.time() - t0))
