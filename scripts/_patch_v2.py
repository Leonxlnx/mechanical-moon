"""One-off patcher for the v2 close-up pass (kept for reference)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

p = 'look.py'; s = open(p, encoding='utf-8').read()
old = '''    L(nt, b1.outputs["Normal"], b2.inputs["Normal"])
    L(nt, b2.outputs["Normal"], bsdf.inputs["Normal"])'''
new = '''    L(nt, b1.outputs["Normal"], b2.inputs["Normal"])
    last_n = b2.outputs["Normal"]
    if P.get("micro_strength", 0.0) > 0:
        # dense field of tiny impact pits (voronoi cells -> bowl + raised rim), only matters in close shots
        vor = N(nt, "ShaderNodeTexVoronoi", (-950, -1000), feature='F1', inputs={"Scale": P.get("micro_scale", 2.4)})
        L(nt, tc.outputs["Object"], vor.inputs["Vector"])
        vs = N(nt, "ShaderNodeSeparateColor", (-750, -1100))
        L(nt, vor.outputs["Color"], vs.inputs["Color"])
        r0 = N(nt, "ShaderNodeMapRange", (-560, -1100), inputs={"From Min": 0.0, "From Max": 1.0, "To Min": 0.14, "To Max": 0.40})
        L(nt, vs.outputs["Red"], r0.inputs["Value"])
        q = N(nt, "ShaderNodeMath", (-380, -1000), operation='DIVIDE')
        L(nt, vor.outputs["Distance"], q.inputs[0])
        L(nt, r0.outputs["Result"], q.inputs[1])
        bowl = N(nt, "ShaderNodeMapRange", (-200, -1000), interpolation_type='SMOOTHERSTEP', inputs={"From Min": 0.0, "From Max": 1.0, "To Min": -1.0, "To Max": 0.0})
        L(nt, q.outputs[0], bowl.inputs["Value"])
        rimd = N(nt, "ShaderNodeMath", (-200, -1200), operation='SUBTRACT')
        rimd.inputs[1].default_value = 1.0
        L(nt, q.outputs[0], rimd.inputs[0])
        rimg = N(nt, "ShaderNodeMath", (-20, -1200), operation='ABSOLUTE')
        L(nt, rimd.outputs[0], rimg.inputs[0])
        rimh = N(nt, "ShaderNodeMapRange", (160, -1200), inputs={"From Min": 0.0, "From Max": 0.22, "To Min": 0.28, "To Max": 0.0})
        L(nt, rimg.outputs[0], rimh.inputs["Value"])
        hsum = N(nt, "ShaderNodeMath", (340, -1050), operation='ADD')
        L(nt, bowl.outputs["Result"], hsum.inputs[0])
        L(nt, rimh.outputs["Result"], hsum.inputs[1])
        gate = N(nt, "ShaderNodeMath", (160, -900), operation='GREATER_THAN')
        gate.inputs[1].default_value = 0.42
        L(nt, vs.outputs["Green"], gate.inputs[0])
        hm = N(nt, "ShaderNodeMath", (520, -1000), operation='MULTIPLY')
        L(nt, hsum.outputs[0], hm.inputs[0])
        L(nt, gate.outputs[0], hm.inputs[1])
        b3 = N(nt, "ShaderNodeBump", (700, -900), inputs={"Strength": P["micro_strength"], "Distance": 0.10})
        L(nt, hm.outputs[0], b3.inputs["Height"])
        L(nt, last_n, b3.inputs["Normal"])
        last_n = b3.outputs["Normal"]
    L(nt, last_n, bsdf.inputs["Normal"])'''
assert old in s; s = s.replace(old, new)
old = '''    nt, bsdf, sep, nz = _ring_common(mat, "ring_windows.png", P)'''
new = '''    nt, bsdf, sep, nz = _ring_common(mat, P.get("ring_win_tex", "ring_windows.png"), P)'''
assert old in s; s = s.replace(old, new)
old = '''    bsdf.inputs["Emission Color"].default_value = (1.0, 0.62, 0.26, 1)
    L(nt, em.outputs[0], bsdf.inputs["Emission Strength"])


def core_glow(mat, P):'''
new = '''    bsdf.inputs["Emission Color"].default_value = P.get("ring_win_color", (1.0, 0.62, 0.26, 1))
    L(nt, em.outputs[0], bsdf.inputs["Emission Strength"])


def core_glow(mat, P):'''
assert old in s; s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)

p = 'gen_ring_tex.py'; s = open(p, encoding='utf-8').read()
old = '''K.log("RING TEX DONE")'''
new = '''# ------------------------------------------------------------------ v2 window tile: glazed panes with mullions, softer edges
rng2 = np.random.default_rng(8)
seam2 = seam.copy()
win2 = np.zeros((H, W), np.float32)
for row, (v0, v1) in enumerate(((0.16, 0.41), (0.59, 0.84))):
    n = 80
    for k in range(n):
        if rng2.random() < 0.30:
            continue
        x0 = int((k + 0.18) * W / n)
        x1 = int((k + 0.82) * W / n)
        b = rng2.uniform(0.30, 1.0)
        hh = rng2.choice([1.0, 1.0, 0.6])
        a_ = int(v0 * H)
        b_ = int((v0 + (v1 - v0) * hh) * H)
        yy, xx = np.mgrid[a_:b_, x0:x1]
        u = (xx - x0) / max(x1 - x0 - 1, 1)
        v = (yy - a_) / max(b_ - a_ - 1, 1)
        pane = b * (0.72 + 0.28 * np.sin(np.pi * v)) * (0.85 + 0.15 * np.sin(np.pi * u))
        for m_ in (1 / 3, 2 / 3):
            pane = np.where(np.abs(u - m_) < 0.045, 0.06 * b, pane)
        pane = np.where(np.abs(v - 0.5) < 0.05, 0.06 * b, pane)
        pane = np.where((u < 0.05) | (u > 0.95) | (v < 0.06) | (v > 0.94), 0.0, pane)
        win2[a_:b_, x0:x1] = pane
        seam2[max(a_ - 3 * SS, 0):a_, x0:x1] = 1
        seam2[b_:b_ + 3 * SS, x0:x1] = 1
img = np.stack([down(seam2), down(win2), np.zeros((H // SS, W // SS), np.float32)], -1)
K.write_png(K.P("textures", "ring_windows_v2.png"), np.round(np.clip(img, 0, 1) * 255).astype(np.uint8))
K.log("RING TEX DONE")'''
assert old in s; s = s.replace(old, new); open(p, 'w', encoding='utf-8').write(s)

p = 'assemble.py'; s = open(p, encoding='utf-8').read()
old = '''for name, fn in (("CRUST", "crust.blend"), ("MECH", "mech.blend"), ("ARCH", "arch.blend"), ("ENV", "env.blend")):'''
new = '''for name, fn in (("CRUST", P.get("crust_blend", "crust.blend")), ("MECH", "mech.blend"), ("ARCH", "arch.blend"), ("ENV", "env.blend")):'''
assert old in s; s = s.replace(old, new)
old = '''if arg("--save", flag=True):
    K.save_blend(K.P("blend", "moon_scene.blend"))'''
new = '''if arg("--save", flag=True):
    K.save_blend(K.P("blend", arg("--saveas", "moon_scene.blend")))'''
assert old in s; s = s.replace(old, new)
old = '''from params import P
'''
new = '''from params import P
if os.environ.get("VARIANT"):
    import importlib as _il
    P = dict(P)
    P.update(_il.import_module("params_" + os.environ["VARIANT"]).P)
'''
assert old in s; s = s.replace(old, new, 1)
open(p, 'w', encoding='utf-8').write(s)

p = 'shots.py'; s = open(p, encoding='utf-8').read()
old = '''    sh["grade"] = GRADE[sh["name"]]'''
new = '''    sh["grade"] = GRADE[sh["name"]]
    sh["rim"] = {"04_crust": 1.6, "09_ring": 2.4}.get(sh["name"], 1.0)'''
assert old in s; s = s.replace(old, new); open(p, 'w', encoding='utf-8').write(s)

p = 'anim.py'; s = open(p, encoding='utf-8').read()
old = '''    for idb in (sc, sc.node_tree):
        if idb and idb.animation_data and idb.animation_data.action:'''
new = '''    rim = bpy.data.lights.get("RimLight")
    if rim and os.environ.get("VARIANT"):
        base = rim.energy
        for sh in SHOTS:
            for f in sh["frames"]:
                rim.energy = base * sh.get("rim", 1.0)
                rim.keyframe_insert("energy", frame=f)
        rim.energy = base
        for fc in rim.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    for idb in (sc, sc.node_tree):
        if idb and idb.animation_data and idb.animation_data.action:'''
assert old in s; s = s.replace(old, new)
s = s.replace("import bpy, math\n", "import bpy, math, os\n", 1)
open(p, 'w', encoding='utf-8').write(s)

open('params_v2.py', 'w', encoding='utf-8').write('"""Overrides for the v2 close-up pass (shots 04 and 09)."""\n'
    'P = dict(\n'
    '    crust_blend="crust_v2.blend",\n'
    '    micro_strength=0.55, micro_scale=2.4,\n'
    '    ring_win_tex="ring_windows_v2.png", ring_win=4.6, ring_win_color=(1.0, 0.56, 0.20, 1),\n'
    ')\n')
print("patched ok")
