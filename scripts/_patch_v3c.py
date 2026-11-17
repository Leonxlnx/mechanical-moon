"""v3 part 3: shard shapes, horizon fade, speckle, cameras (kept for reference)."""
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def sub(path, pairs):
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        assert old in s, (path, old[:70])
        s = s.replace(old, new, 1)
    open(path, 'w', encoding='utf-8').write(s)


sub('build_crust.py', [
    # fewer tiny rim shards (they read as a row of bread rolls)
    ('''s2 = cand2[rng.random(len(cand2)) < 0.9 * np.exp(-((fc2 - 1.0) / 0.07) ** 2)]''',
     '''s2 = cand2[rng.random(len(cand2)) < 0.22 * np.exp(-((fc2 - 1.0) / 0.07) ** 2)]'''),
    ('''gap[c12] = 0.3
amp[c12] = 1.0''', '''gap[c12] = 0.3
amp[c12] = 0.45'''),
    ('''    for _ in range(3):
        pos_top[bsel] = 0.5 * pos_top[bsel] + 0.25 * (pos_top[nxt[bsel]] + pos_top[prv[bsel]])''',
     '''    for _ in range(1):
        pos_top[bsel] = 0.5 * pos_top[bsel] + 0.25 * (pos_top[nxt[bsel]] + pos_top[prv[bsel]])'''),
    # crack width varies along its length
    ('''    gp = gap[lv_plate[bidx]]
    am = amp[lv_plate[bidx]]''',
     '''    gp = gap[lv_plate[bidx]] * np.clip(0.75 + 1.3 * K.fbm3(d_top[bidx] * 21.0, 2, seed=207), 0.25, 2.2)
    am = amp[lv_plate[bidx]]'''),
    # angular debris instead of smooth potatoes
    ('''    rad = 1.0 + 0.42 * K.fbm3(d * 1.3 + o, 3, seed=300 + seed) + 0.16 * K.fbm3(d * 4.5 + o, 2, seed=400 + seed, ridged=True)''',
     '''    cell = np.round(K.fbm3(d * 1.1 + o, 2, seed=300 + seed) * 3.2) / 3.2            # terraced lobes -> flat facets, hard edges
    rad = 1.0 + 0.55 * cell + 0.20 * K.fbm3(d * 4.5 + o, 2, seed=400 + seed, ridged=True)'''),
    ('''    ob = K.obj_np("CRUST_Rock%02d" % i, col, v, rtri, mats=[mat_raw],''', '''    ob = K.obj_np("CRUST_Rock%02d" % i, col, v, rtri, mats=[mat_raw], smooth=False,'''),
    ('''    ob = K.obj_np("CRUST_Gravel%d" % ci, col, v, f, mats=[mat_raw],''', '''    ob = K.obj_np("CRUST_Gravel%d" % ci, col, v, f, mats=[mat_raw], smooth=False,'''),
])

sub('mats.py', [
    ('"Brass":     lambda m: _metal(m, (0.50, 0.30, 0.11), 0.22, 0.42, wear_dark=0.5, scale=1.9, bump=0.14),',
     '"Brass":     lambda m: _metal(m, (0.50, 0.30, 0.11), 0.22, 0.42, wear_dark=0.68, scale=1.1, bump=0.04),'),
    ('"Bronze":    lambda m: _metal(m, (0.16, 0.095, 0.045), 0.30, 0.52, wear_dark=0.55, scale=2.1, bump=0.18),',
     '"Bronze":    lambda m: _metal(m, (0.16, 0.095, 0.045), 0.30, 0.52, wear_dark=0.68, scale=1.2, bump=0.05),'),
    ('"Gold":      lambda m: _metal(m, (1.00, 0.66, 0.22), 0.13, 0.30, wear_dark=0.55, scale=1.7, bump=0.08),',
     '"Gold":      lambda m: _metal(m, (1.00, 0.66, 0.22), 0.13, 0.30, wear_dark=0.66, scale=1.0, bump=0.04),'),
    ('"DarkMetal": lambda m: _metal(m, (0.085, 0.060, 0.040), 0.26, 0.48, wear_dark=0.5, scale=1.6, bump=0.16),',
     '"DarkMetal": lambda m: _metal(m, (0.085, 0.060, 0.040), 0.26, 0.48, wear_dark=0.65, scale=1.0, bump=0.05),'),
    # the fine noise drove both colour and bump: keep it for roughness breakup only
    ('''    n2 = N(nt, "ShaderNodeTexNoise", (-650, -150), inputs={"Scale": scale * 9.0, "Detail": 1.5, "Roughness": 0.7})''',
     '''    n2 = N(nt, "ShaderNodeTexNoise", (-650, -150), inputs={"Scale": scale * 3.0, "Detail": 1.5, "Roughness": 0.7})'''),
])

sub('assemble.py', [
    ('''# ------------------------------------------------------------------ lights
lc = K.coll("LIGHTS")''',
     '''# soft horizon: far water dissolves into the sky colour (the fog volume cannot reach that far)
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
lc = K.coll("LIGHTS")'''),
])

sub('shots.py', [
    ('''dict(name="01_sea", keys=[(0, (66, -300, 6.4), (44, -150, -6), 28), (1, (58, -262, 7.0), (20, -30, 36), 28)]),''',
     '''dict(name="01_sea", keys=[(0, (66, -300, 3.2), (44, -150, 4), 28), (1, (58, -262, 3.7), (20, -30, 64), 28)]),'''),
    ('''dict(name="02_reveal", keys=[(0, (-43, -334, 10.0), (0, -10, 86), 24), (1, (-36, -324, 15.5), (0, -10, 93), 24)]),''',
     '''dict(name="02_reveal", keys=[(0, (-86, -338, 12.6), (-10, -30, 44), 40), (1, (-80, -333, 17.5), (-6, -20, 86), 40)]),'''),
    ('''dict(name="11_final", keys=[(0, (-52, -338, 15.5), (0, -8, 90), 26), (1, (-61, -352, 12.5), (0, -8, 86), 23)]),''',
     '''dict(name="11_final", keys=[(0, (-30, -350, 10.6), (0, -8, 86), 23), (1, (-36, -362, 13.4), (0, -8, 82), 20)]),'''),
    ('''    "04_crust": ((-0.25, 0.35, 0.90), 1.0),''', '''    "04_crust": ((-0.55, 0.25, 0.80), 1.15),'''),
])
s = open('params.py', encoding='utf-8').read()
s = s.replace("moon_spec=0.45", "moon_spec=0.30").replace("raw_light=(0.15, 0.148, 0.15, 1)", "raw_light=(0.10, 0.098, 0.10, 1)")
open('params.py', 'w', encoding='utf-8').write(s)
print("v3c patch ok")
