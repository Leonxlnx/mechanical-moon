"""v3 part 4: rim glow gate, shot 9 light, final camera, lightning positions (kept for reference)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def sub(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)


sub('look.py', [
    ('''    e1 = N(nt, "ShaderNodeMath", (-120, -550), operation='MULTIPLY')
    L(nt, dm.outputs["Result"], e1.inputs[0])
    L(nt, hm.outputs["Result"], e1.inputs[1])''',
     '''    # walls that face the open hole are lit by the real core light; only closed cracks get the seam glow
    gate = N(nt, "ShaderNodeMapRange", (-380, -900), inputs={"From Min": 1.05, "From Max": 1.17, "To Min": 0.0, "To Max": 1.0})
    L(nt, heat.outputs["Fac"], gate.inputs["Value"])
    hg = N(nt, "ShaderNodeMath", (-200, -800), operation='MULTIPLY')
    L(nt, hm.outputs["Result"], hg.inputs[0])
    L(nt, gate.outputs["Result"], hg.inputs[1])
    e1 = N(nt, "ShaderNodeMath", (-120, -550), operation='MULTIPLY')
    L(nt, dm.outputs["Result"], e1.inputs[0])
    L(nt, hg.outputs[0], e1.inputs[1])'''),
])
sub('mats.py', [
    ('"Window":    lambda m: _emit(m, (1.0, 0.55, 0.20), 3.2, attr="rnd", dark_below=0.44),',
     '"Window":    lambda m: _emit(m, (1.0, 0.52, 0.17), 2.3, attr="rnd", dark_below=0.44),'),
])
sub('shots.py', [
    ('''    "09_ring": ((0.30, 0.50, 0.80), 0.9),''', '''    "09_ring": ((0.60, -0.50, 0.62), 1.0),'''),
    ('''    sh["rim"] = {"04_crust": 1.3, "09_ring": 1.6}.get(sh["name"], 1.0)''', '''    sh["rim"] = {"04_crust": 1.0, "09_ring": 0.6}.get(sh["name"], 1.0)'''),
    ('''dict(name="11_final", keys=[(0, (-30, -350, 10.6), (0, -8, 86), 23), (1, (-36, -362, 13.4), (0, -8, 82), 20)]),''',
     '''dict(name="11_final", keys=[(0, (-30, -350, 17.0), (22, -8, 76), 23), (1, (-38, -374, 24.0), (26, -8, 70), 20)]),'''),
])
sub('anim.py', [
    ('''    (8.15, (-520, 980, 420), (-470, 1010, 0), 1),
    (12.10, (760, 620, 400), (800, 560, 0), 2),
    (41.62, (560, 900, 430), (500, 940, 0), 3),''',
     '''    (8.15, (-180, 960, 420), (-150, 990, 0), 1),       # left of the moon in the reveal shot
    (12.10, (400, 860, 420), (440, 820, 0), 2),        # left of the moon in the side shot
    (41.62, (740, 760, 430), (690, 800, 0), 3),        # right of the moon in the final shot'''),
])
print("v3d patch ok")
