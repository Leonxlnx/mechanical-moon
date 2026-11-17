"""Look development: hero materials (moon rock, mechanism), built in place by name."""
import bpy, json, os, math
import common as K, config as C
from mats import clear, N, L


def _img(path, non_color=True):
    name = os.path.basename(path)
    img = bpy.data.images.get(name)
    if img is None:
        img = bpy.data.images.load(path)
    if non_color:
        img.colorspace_settings.name = 'Non-Color'
    return img


def moon_rock(mat, P):
    meta = json.load(open(K.P("textures", "moon_meta.json")))
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    uv = N(nt, "ShaderNodeUVMap", (-1500, 100))
    tc = N(nt, "ShaderNodeTexCoord", (-1500, -400))
    alb = N(nt, "ShaderNodeTexImage", (-1250, 250), image=_img(K.P("textures", "moon_albedo.png")), interpolation='Cubic')
    det = N(nt, "ShaderNodeTexImage", (-1250, -100), image=_img(K.P("textures", "moon_detail.png")), interpolation='Cubic')
    L(nt, uv.outputs["UV"], alb.inputs["Vector"])
    L(nt, uv.outputs["UV"], det.inputs["Vector"])
    sep = N(nt, "ShaderNodeSeparateColor", (-950, 250))
    L(nt, alb.outputs["Color"], sep.inputs["Color"])
    # albedo -> colour
    am = N(nt, "ShaderNodeMapRange", (-750, 350), inputs={"From Min": P.get("alb_lo", 0.18), "From Max": P.get("alb_hi", 0.80), "To Min": 0.0, "To Max": 1.0})
    L(nt, sep.outputs["Red"], am.inputs["Value"])
    mixc = N(nt, "ShaderNodeMixRGB", (-520, 350))
    mixc.inputs["Color1"].default_value = P.get("rock_dark", (0.060, 0.060, 0.064, 1))
    mixc.inputs["Color2"].default_value = P.get("rock_light", (0.60, 0.61, 0.63, 1))
    L(nt, am.outputs["Result"], mixc.inputs["Fac"])
    # maria: slightly bluish dark basalt
    mar = N(nt, "ShaderNodeMixRGB", (-300, 350), blend_type='MULTIPLY')
    mar.inputs["Color2"].default_value = P.get("maria_tint", (0.80, 0.86, 1.0, 1))
    L(nt, sep.outputs["Green"], mar.inputs["Fac"])
    L(nt, mixc.outputs["Color"], mar.inputs["Color1"])
    # fresh ejecta: brighter, cooler
    fr = N(nt, "ShaderNodeMixRGB", (-80, 350), blend_type='ADD')
    fr.inputs["Color2"].default_value = (0.16, 0.17, 0.19, 1)
    L(nt, sep.outputs["Blue"], fr.inputs["Fac"])
    L(nt, mar.outputs["Color"], fr.inputs["Color1"])
    # speckle
    n1 = N(nt, "ShaderNodeTexNoise", (-950, -420), inputs={"Scale": 1.7, "Detail": 4.0, "Roughness": 0.68})
    L(nt, tc.outputs["Object"], n1.inputs["Vector"])
    sp = N(nt, "ShaderNodeMapRange", (-700, -420), inputs={"From Min": 0.30, "From Max": 0.72, "To Min": 0.78, "To Max": 1.14})
    L(nt, n1.outputs["Fac"], sp.inputs["Value"])
    mul = N(nt, "ShaderNodeMixRGB", (140, 250), blend_type='MULTIPLY')
    mul.inputs["Fac"].default_value = 1.0
    L(nt, fr.outputs["Color"], mul.inputs["Color1"])
    L(nt, sp.outputs["Result"], mul.inputs["Color2"])
    # baked cavity shading from the small-crater map (reads even in shadow / ambient light)
    z0 = -meta["det_min"] / (meta["det_max"] - meta["det_min"])
    cav = N(nt, "ShaderNodeMapRange", (-650, 60), inputs={"From Min": z0 - 0.45, "From Max": z0 + 0.10, "To Min": P.get("cav_dark", 0.35), "To Max": 1.12})
    L(nt, det.outputs["Color"], cav.inputs["Value"])
    mul2 = N(nt, "ShaderNodeMixRGB", (330, 250), blend_type='MULTIPLY')
    mul2.inputs["Fac"].default_value = 1.0
    L(nt, mul.outputs["Color"], mul2.inputs["Color1"])
    L(nt, cav.outputs["Result"], mul2.inputs["Color2"])
    L(nt, mul2.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.93
    bsdf.inputs["Specular IOR Level"].default_value = 0.25
    # bump: small craters from the detail map, then fine regolith noise
    b1 = N(nt, "ShaderNodeBump", (-650, -150), inputs={"Strength": P.get("det_strength", 1.0), "Distance": (meta["det_max"] - meta["det_min"]) * P.get("det_boost", 1.5)})
    L(nt, det.outputs["Color"], b1.inputs["Height"])
    n2 = N(nt, "ShaderNodeTexNoise", (-950, -700), inputs={"Scale": 7.0, "Detail": 3.5, "Roughness": 0.72})
    L(nt, tc.outputs["Object"], n2.inputs["Vector"])
    b2 = N(nt, "ShaderNodeBump", (-350, -300), inputs={"Strength": P.get("fine_strength", 0.45), "Distance": 0.22})
    L(nt, n2.outputs["Fac"], b2.inputs["Height"])
    L(nt, b1.outputs["Normal"], b2.inputs["Normal"])
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
        cd = N(nt, "ShaderNodeCameraData", (340, -1300))
        fadeo = N(nt, "ShaderNodeMapRange", (520, -1300), inputs={"From Min": 45.0, "From Max": 130.0, "To Min": P["micro_strength"], "To Max": 0.0})
        L(nt, cd.outputs["View Distance"], fadeo.inputs["Value"])
        L(nt, fadeo.outputs["Result"], b3.inputs["Strength"])
        L(nt, hm.outputs[0], b3.inputs["Height"])
        L(nt, last_n, b3.inputs["Normal"])
        last_n = b3.outputs["Normal"]
    L(nt, last_n, bsdf.inputs["Normal"])
    # warm light bleeding onto plate edges near the opening
    rim = N(nt, "ShaderNodeAttribute", (-300, -600), attribute_name="rim")
    heat = N(nt, "ShaderNodeAttribute", (-300, -800), attribute_name="openf")
    hm = N(nt, "ShaderNodeMapRange", (-80, -800), inputs={"From Min": 1.9, "From Max": 1.0, "To Min": 0.0, "To Max": 1.0})
    L(nt, heat.outputs["Fac"], hm.inputs["Value"])
    em = N(nt, "ShaderNodeMath", (140, -650), operation='MULTIPLY')
    L(nt, rim.outputs["Fac"], em.inputs[0])
    L(nt, hm.outputs["Result"], em.inputs[1])
    em2 = N(nt, "ShaderNodeMath", (320, -650), operation='MULTIPLY')
    em2.inputs[1].default_value = P.get("rim_glow", 0.6)
    L(nt, em.outputs[0], em2.inputs[0])
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.55, 0.2, 1)
    L(nt, em2.outputs[0], bsdf.inputs["Emission Strength"])
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])


def moon_rock_raw(mat, P):
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    tc = N(nt, "ShaderNodeTexCoord", (-1400, 0))
    n1 = N(nt, "ShaderNodeTexNoise", (-1100, 200), inputs={"Scale": 0.33, "Detail": 3.5, "Roughness": 0.66})
    n2 = N(nt, "ShaderNodeTexNoise", (-1100, -150), inputs={"Scale": 2.6, "Detail": 3.5, "Roughness": 0.7})
    L(nt, tc.outputs["Object"], n1.inputs["Vector"])
    L(nt, tc.outputs["Object"], n2.inputs["Vector"])
    dep = N(nt, "ShaderNodeAttribute", (-1400, -450), attribute_name="depth")
    heat = N(nt, "ShaderNodeAttribute", (-1400, -700), attribute_name="openf")
    cm = N(nt, "ShaderNodeMapRange", (-850, 200), inputs={"From Min": 0.28, "From Max": 0.75, "To Min": 0.0, "To Max": 1.0})
    L(nt, n1.outputs["Fac"], cm.inputs["Value"])
    mixc = N(nt, "ShaderNodeMixRGB", (-620, 200))
    mixc.inputs["Color1"].default_value = P.get("raw_dark", (0.030, 0.029, 0.030, 1))
    mixc.inputs["Color2"].default_value = P.get("raw_light", (0.27, 0.265, 0.27, 1))
    L(nt, cm.outputs["Result"], mixc.inputs["Fac"])
    # strata bands
    m1 = N(nt, "ShaderNodeMath", (-1100, -450), operation='MULTIPLY_ADD')
    m1.inputs[1].default_value = 26.0
    L(nt, dep.outputs["Fac"], m1.inputs[0])
    m1b = N(nt, "ShaderNodeMath", (-1100, -620), operation='MULTIPLY')
    m1b.inputs[1].default_value = 7.0
    L(nt, n1.outputs["Fac"], m1b.inputs[0])
    L(nt, m1b.outputs[0], m1.inputs[2])
    s1 = N(nt, "ShaderNodeMath", (-900, -450), operation='SINE')
    L(nt, m1.outputs[0], s1.inputs[0])
    sm = N(nt, "ShaderNodeMapRange", (-700, -450), inputs={"From Min": -1.0, "From Max": 1.0, "To Min": 0.62, "To Max": 1.08})
    L(nt, s1.outputs[0], sm.inputs["Value"])
    mul = N(nt, "ShaderNodeMixRGB", (-380, 200), blend_type='MULTIPLY')
    mul.inputs["Fac"].default_value = 1.0
    L(nt, mixc.outputs["Color"], mul.inputs["Color1"])
    L(nt, sm.outputs["Result"], mul.inputs["Color2"])
    L(nt, mul.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.88
    bsdf.inputs["Specular IOR Level"].default_value = 0.3
    # glow from below (kintsugi seams)
    dm = N(nt, "ShaderNodeMapRange", (-380, -450), interpolation_type='SMOOTHSTEP', inputs={"From Min": P.get("seam_from", 0.30), "From Max": 1.0, "To Min": 0.0, "To Max": 1.0})
    L(nt, dep.outputs["Fac"], dm.inputs["Value"])
    hm = N(nt, "ShaderNodeMapRange", (-380, -700), inputs={"From Min": P.get("seam_far", 2.3), "From Max": 1.05, "To Min": P.get("seam_min", 0.04), "To Max": 1.0})
    L(nt, heat.outputs["Fac"], hm.inputs["Value"])
    # walls that face the open hole are lit by the real core light; only closed cracks get the seam glow
    gate = N(nt, "ShaderNodeMapRange", (-380, -900), inputs={"From Min": 1.05, "From Max": 1.17, "To Min": 0.0, "To Max": 1.0})
    L(nt, heat.outputs["Fac"], gate.inputs["Value"])
    hg = N(nt, "ShaderNodeMath", (-200, -800), operation='MULTIPLY')
    L(nt, hm.outputs["Result"], hg.inputs[0])
    L(nt, gate.outputs["Result"], hg.inputs[1])
    e1 = N(nt, "ShaderNodeMath", (-120, -550), operation='MULTIPLY')
    L(nt, dm.outputs["Result"], e1.inputs[0])
    L(nt, hg.outputs[0], e1.inputs[1])
    e2 = N(nt, "ShaderNodeMath", (80, -550), operation='MULTIPLY')
    e2.inputs[1].default_value = P.get("seam_glow", 9.0)
    L(nt, e1.outputs[0], e2.inputs[0])
    bsdf.inputs["Emission Color"].default_value = P.get("seam_color", (1.0, 0.50, 0.16, 1))
    L(nt, e2.outputs[0], bsdf.inputs["Emission Strength"])
    # bump
    b = N(nt, "ShaderNodeBump", (200, -250), inputs={"Strength": 0.85, "Distance": 0.35})
    L(nt, n2.outputs["Fac"], b.inputs["Height"])
    L(nt, b.outputs["Normal"], bsdf.inputs["Normal"])
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])


def _ring_common(mat, tex, P):
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    uv = N(nt, "ShaderNodeUVMap", (-1500, 100))
    mp = N(nt, "ShaderNodeMapping", (-1300, 100))
    mp.inputs["Scale"].default_value = (1.0 / 20.0, 1.0, 1.0)
    L(nt, uv.outputs["UV"], mp.inputs["Vector"])
    img = N(nt, "ShaderNodeTexImage", (-1080, 100), image=_img(K.P("textures", tex)), interpolation='Linear')
    L(nt, mp.outputs["Vector"], img.inputs["Vector"])
    sep = N(nt, "ShaderNodeSeparateColor", (-800, 100))
    L(nt, img.outputs["Color"], sep.inputs["Color"])
    tc = N(nt, "ShaderNodeTexCoord", (-1500, -400))
    nz = N(nt, "ShaderNodeTexNoise", (-1080, -400), inputs={"Scale": 0.45, "Detail": 2.5, "Roughness": 0.65})
    L(nt, tc.outputs["Object"], nz.inputs["Vector"])
    bsdf.inputs["Metallic"].default_value = 1.0
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    return nt, bsdf, sep, nz


def ring_engrave(mat, P):
    nt, bsdf, sep, nz = _ring_common(mat, "ring_engrave.png", P)
    wear = N(nt, "ShaderNodeMapRange", (-800, -400), inputs={"From Min": 0.35, "From Max": 0.7, "To Min": 0.55, "To Max": 1.0})
    L(nt, nz.outputs["Fac"], wear.inputs["Value"])
    gold = N(nt, "ShaderNodeMixRGB", (-520, 300), blend_type='MULTIPLY')
    gold.inputs["Fac"].default_value = 1.0
    gold.inputs["Color1"].default_value = P.get("gold", (1.0, 0.68, 0.25, 1))
    L(nt, wear.outputs["Result"], gold.inputs["Color2"])
    mixc = N(nt, "ShaderNodeMixRGB", (-300, 300))
    mixc.inputs["Color2"].default_value = (0.07, 0.04, 0.015, 1)
    L(nt, gold.outputs["Color"], mixc.inputs["Color1"])
    ef = N(nt, "ShaderNodeMath", (-520, 100), operation='MULTIPLY')
    ef.inputs[1].default_value = 0.92
    L(nt, sep.outputs["Red"], ef.inputs[0])
    L(nt, ef.outputs[0], mixc.inputs["Fac"])
    L(nt, mixc.outputs["Color"], bsdf.inputs["Base Color"])
    rg = N(nt, "ShaderNodeMapRange", (-300, 60), inputs={"From Min": 0.0, "From Max": 1.0, "To Min": 0.24, "To Max": 0.62})
    L(nt, sep.outputs["Red"], rg.inputs["Value"])
    ra = N(nt, "ShaderNodeMath", (-80, 60), operation='MULTIPLY_ADD')
    ra.inputs[1].default_value = 0.25
    L(nt, sep.outputs["Blue"], ra.inputs[0])
    L(nt, rg.outputs["Result"], ra.inputs[2])
    L(nt, ra.outputs[0], bsdf.inputs["Roughness"])
    b = N(nt, "ShaderNodeBump", (200, -200), invert=True, inputs={"Strength": 1.0, "Distance": 0.07})
    L(nt, sep.outputs["Red"], b.inputs["Height"])
    L(nt, b.outputs["Normal"], bsdf.inputs["Normal"])
    em = N(nt, "ShaderNodeMath", (200, -420), operation='MULTIPLY')
    em.inputs[1].default_value = P.get("glyph_glow", 2.5)
    L(nt, sep.outputs["Green"], em.inputs[0])
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.55, 0.20, 1)
    L(nt, em.outputs[0], bsdf.inputs["Emission Strength"])


def ring_windows(mat, P):
    nt, bsdf, sep, nz = _ring_common(mat, P.get("ring_win_tex", "ring_windows.png"), P)
    wear = N(nt, "ShaderNodeMapRange", (-800, -400), inputs={"From Min": 0.35, "From Max": 0.7, "To Min": 0.6, "To Max": 1.0})
    L(nt, nz.outputs["Fac"], wear.inputs["Value"])
    base = N(nt, "ShaderNodeMixRGB", (-520, 300), blend_type='MULTIPLY')
    base.inputs["Fac"].default_value = 1.0
    base.inputs["Color1"].default_value = P.get("ring_panel", (0.62, 0.40, 0.15, 1))
    L(nt, wear.outputs["Result"], base.inputs["Color2"])
    mixc = N(nt, "ShaderNodeMixRGB", (-300, 300))
    mixc.inputs["Color2"].default_value = (0.04, 0.025, 0.01, 1)
    L(nt, base.outputs["Color"], mixc.inputs["Color1"])
    L(nt, sep.outputs["Red"], mixc.inputs["Fac"])
    L(nt, mixc.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.40
    b = N(nt, "ShaderNodeBump", (200, -200), invert=True, inputs={"Strength": 1.0, "Distance": 0.06})
    L(nt, sep.outputs["Red"], b.inputs["Height"])
    L(nt, b.outputs["Normal"], bsdf.inputs["Normal"])
    em = N(nt, "ShaderNodeMath", (200, -420), operation='MULTIPLY')
    em.inputs[1].default_value = P.get("ring_win", 16.0)
    L(nt, sep.outputs["Green"], em.inputs[0])
    bsdf.inputs["Emission Color"].default_value = P.get("ring_win_color", (1.0, 0.62, 0.26, 1))
    L(nt, em.outputs[0], bsdf.inputs["Emission Strength"])


def core_glow(mat, P):
    """White-hot centre falling to deep orange at the limb, with slowly crawling plasma cells."""
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (900, 0))
    em = N(nt, "ShaderNodeEmission", (650, 0))
    lw = N(nt, "ShaderNodeLayerWeight", (-900, 200), inputs={"Blend": 0.5})
    fac = N(nt, "ShaderNodeMath", (-680, 200), operation='POWER')
    fac.inputs[1].default_value = P.get("core_limb_pow", 0.75)
    L(nt, lw.outputs["Facing"], fac.inputs[0])
    tc = N(nt, "ShaderNodeTexCoord", (-1200, -200))
    nz = N(nt, "ShaderNodeTexNoise", (-900, -200), noise_dimensions='4D', inputs={"Scale": 0.33, "Detail": 3.0, "Roughness": 0.6})
    nz.name = "CorePlasma"
    L(nt, tc.outputs["Object"], nz.inputs["Vector"])
    pm = N(nt, "ShaderNodeMapRange", (-680, -200), inputs={"From Min": 0.3, "From Max": 0.7, "To Min": 0.45, "To Max": 1.35})
    pm.name = "CorePlasmaRange"
    L(nt, nz.outputs["Fac"], pm.inputs["Value"])
    col = N(nt, "ShaderNodeMixRGB", (-420, 250))
    col.name = "CoreColor"
    col.inputs["Color1"].default_value = (1.0, 0.86, 0.62, 1)
    col.inputs["Color2"].default_value = (1.0, 0.36, 0.07, 1)
    L(nt, fac.outputs[0], col.inputs["Fac"])
    st = N(nt, "ShaderNodeMapRange", (-420, 0), inputs={"From Min": 0.0, "From Max": 1.0, "To Min": P.get("core_emit", 220.0), "To Max": P.get("core_emit_limb", 14.0)})
    st.name = "CoreStrength"
    L(nt, fac.outputs[0], st.inputs["Value"])
    sm = N(nt, "ShaderNodeMath", (-150, 0), operation='MULTIPLY')
    L(nt, st.outputs["Result"], sm.inputs[0])
    L(nt, pm.outputs["Result"], sm.inputs[1])
    L(nt, col.outputs["Color"], em.inputs["Color"])
    L(nt, sm.outputs[0], em.inputs["Strength"])
    L(nt, em.outputs[0], out.inputs["Surface"])


def hull_skin(mat, P):
    """Bronze plating under the crust: fine panel grid, thin glowing seams broken up by noise."""
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (900, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (600, 0))
    tc = N(nt, "ShaderNodeTexCoord", (-1300, 0))
    v1 = N(nt, "ShaderNodeTexVoronoi", (-1000, 150), feature='DISTANCE_TO_EDGE', inputs={"Scale": 0.30})
    v2 = N(nt, "ShaderNodeTexVoronoi", (-1000, -150), feature='DISTANCE_TO_EDGE', inputs={"Scale": 1.3})
    nz = N(nt, "ShaderNodeTexNoise", (-1000, -450), inputs={"Scale": 0.09, "Detail": 3.0})
    for n_ in (v1, v2, nz):
        L(nt, tc.outputs["Object"], n_.inputs["Vector"])
    s1 = N(nt, "ShaderNodeMapRange", (-760, 150), inputs={"From Min": 0.0, "From Max": P.get("hull_seam", 0.022), "To Min": 1.0, "To Max": 0.0})
    L(nt, v1.outputs["Distance"], s1.inputs["Value"])
    s2 = N(nt, "ShaderNodeMapRange", (-760, -150), inputs={"From Min": 0.0, "From Max": 0.03, "To Min": 1.0, "To Max": 0.0})
    L(nt, v2.outputs["Distance"], s2.inputs["Value"])
    gate = N(nt, "ShaderNodeMapRange", (-760, -450), inputs={"From Min": 0.42, "From Max": 0.60, "To Min": 0.15, "To Max": 1.0})
    L(nt, nz.outputs["Fac"], gate.inputs["Value"])
    glow = N(nt, "ShaderNodeMath", (-520, 150), operation='MULTIPLY')
    L(nt, s1.outputs["Result"], glow.inputs[0])
    L(nt, gate.outputs["Result"], glow.inputs[1])
    es = N(nt, "ShaderNodeMath", (-300, 150), operation='MULTIPLY_ADD')
    es.inputs[1].default_value = P.get("hull_glow", 11.0)
    es.inputs[2].default_value = 0.03
    L(nt, glow.outputs[0], es.inputs[0])
    dark = N(nt, "ShaderNodeMixRGB", (-300, -150))
    dark.inputs["Color1"].default_value = (0.20, 0.12, 0.045, 1)
    dark.inputs["Color2"].default_value = (0.05, 0.03, 0.012, 1)
    L(nt, s2.outputs["Result"], dark.inputs["Fac"])
    L(nt, dark.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.52, 0.16, 1)
    L(nt, es.outputs[0], bsdf.inputs["Emission Strength"])
    b = N(nt, "ShaderNodeBump", (200, -300), invert=True, inputs={"Strength": 0.8, "Distance": 0.08})
    L(nt, s2.outputs["Result"], b.inputs["Height"])
    L(nt, b.outputs["Normal"], bsdf.inputs["Normal"])
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])


def apply(P=None):
    """Build all hero materials that exist in the file."""
    P = P or {}
    for name, fn in (("CoreGlow", core_glow), ("HullSkin", hull_skin)):
        m = bpy.data.materials.get(name)
        if m is not None:
            fn(m, P)
    for name, fn in (("MoonRock", moon_rock), ("MoonRockRaw", moon_rock_raw), ("RingEngrave", ring_engrave), ("RingWindows", ring_windows)):
        m = bpy.data.materials.get(name)
        if m is not None:
            fn(m, P)
