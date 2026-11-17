"""What does a FRAME CHANGE cost? Remove animation categories one by one."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K
from params import P

sc = bpy.context.scene
K.setup_eevee(sc, samples=16, res=(1920, 1080))
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=0.8)
ee = sc.eevee
for l in bpy.data.lights:
    K._set(l, use_shadow_jitter=False)
ee.use_fast_gi = False
marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])
out = K.P("renders", "bench")
sc.render.image_settings.file_format = 'JPEG'
state = {"f": 400}


def cam_for(f):
    c = marks[0][1]
    for mf, mc in marks:
        if mf <= f:
            c = mc
    return c


def render(f):
    t = time.time()
    sc.frame_set(f)
    t1 = time.time() - t
    sc.camera = cam_for(f)
    sc.render.filepath = os.path.join(out, "p7.jpg")
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return t1, time.time() - t


def step(name, discard=0):
    for i in range(discard):
        state["f"] += 1
        render(state["f"])
    rs = []
    for i in range(3):
        state["f"] += 1
        rs.append(render(state["f"]))
    same = render(state["f"])
    K.log("PROF7 %-28s new-frame: %s | frame_set %.1fs | same-frame again: %.1fs" % (
        name, " ".join("%.1f" % r[1] for r in rs), sum(r[0] for r in rs) / 3, same[1]))


render(400)
step("baseline")
for o in bpy.data.objects:
    if o.name.startswith("CRUST_") and o.animation_data:
        o.animation_data_clear()
step("no crust anim")
for o in bpy.data.objects:
    if o.name.startswith(("ARCH_", "MECH_", "DUST", "Bolt")) and o.animation_data:
        o.animation_data_clear()
step("no mech/arch anim")
for m in bpy.data.materials:
    if m.node_tree and m.node_tree.animation_data:
        m.node_tree.animation_data_clear()
for w in bpy.data.worlds:
    if w.node_tree and w.node_tree.animation_data:
        w.node_tree.animation_data_clear()
for l in bpy.data.lights:
    if l.animation_data:
        l.animation_data_clear()
for o in bpy.data.objects:
    if o.type == 'LIGHT' and o.animation_data:
        o.animation_data_clear()
step("no material/world/light anim", discard=1)
oc = bpy.data.objects.get("ENV_Ocean")
if oc:
    for m in oc.modifiers:
        if m.type == 'OCEAN':
            if m.animation_data if hasattr(m, "animation_data") else False:
                pass
    if oc.animation_data:
        oc.animation_data_clear()
step("no ocean time anim", discard=1)
for o in bpy.data.objects:
    if o.name.startswith("ENV_Spray"):
        o.hide_render = True
step("no spray", discard=1)
