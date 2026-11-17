"""Canonical material library. Every module gets materials through mats.get(name) so the final
assembly can rebuild all of them in one place (materials are matched by NAME when modules are appended).

Canonical names: Gold, Brass, Bronze, DarkMetal, Silver, Window, Lamp, CoreGlow, Enamel, HullSkin
Module-specific materials may be added by a module with its own unique prefix (e.g. ARCH_*, ENV_*).
"""
import bpy


def clear(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    return nt


def N(nt, typ, loc=(0, 0), **props):
    n = nt.nodes.new(typ)
    n.location = loc
    for k, v in props.items():
        if k == "inputs":
            for ik, iv in v.items():
                n.inputs[ik].default_value = iv
        else:
            setattr(n, k, v)
    return n


def L(nt, a, b):
    return nt.links.new(a, b)


def _metal(mat, color, rough_lo, rough_hi, wear_dark=0.35, scale=0.6, bump=0.15, metallic=1.0, coord='Object'):
    """Worn metal: noise-broken roughness, darker patina patches, fine bump."""
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (600, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (300, 0))
    tc = N(nt, "ShaderNodeTexCoord", (-900, 0))
    n1 = N(nt, "ShaderNodeTexNoise", (-650, 150), inputs={"Scale": scale, "Detail": 2.0, "Roughness": 0.62})
    n2 = N(nt, "ShaderNodeTexNoise", (-650, -150), inputs={"Scale": scale * 3.0, "Detail": 1.5, "Roughness": 0.7})
    L(nt, tc.outputs[coord], n1.inputs["Vector"])
    L(nt, tc.outputs[coord], n2.inputs["Vector"])
    # roughness
    mr = N(nt, "ShaderNodeMapRange", (-380, 150), inputs={"From Min": 0.32, "From Max": 0.72, "To Min": rough_lo, "To Max": rough_hi})
    L(nt, n1.outputs["Fac"], mr.inputs["Value"])
    L(nt, mr.outputs["Result"], bsdf.inputs["Roughness"])
    # colour with patina
    cr = N(nt, "ShaderNodeMapRange", (-380, -50), inputs={"From Min": 0.38, "From Max": 0.66, "To Min": 0.0, "To Max": 1.0})
    L(nt, n2.outputs["Fac"], cr.inputs["Value"])
    mix = N(nt, "ShaderNodeMixRGB", (-120, 60), blend_type='MIX')
    mix.inputs["Color1"].default_value = (color[0] * wear_dark, color[1] * wear_dark * 0.85, color[2] * wear_dark * 0.7, 1)
    mix.inputs["Color2"].default_value = (color[0], color[1], color[2], 1)
    L(nt, cr.outputs["Result"], mix.inputs["Fac"])
    L(nt, mix.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = metallic
    # bump
    bp = N(nt, "ShaderNodeBump", (40, -220), inputs={"Strength": bump, "Distance": 0.05})
    L(nt, n2.outputs["Fac"], bp.inputs["Height"])
    L(nt, bp.outputs["Normal"], bsdf.inputs["Normal"])
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _emit(mat, color, strength, attr=None, base=(0.02, 0.012, 0.005), dark_below=0.12):
    """Emissive surface; optional per-vertex float attribute (0..1) varies brightness/on-off."""
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (500, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (200, 0))
    bsdf.inputs["Base Color"].default_value = (base[0], base[1], base[2], 1)
    bsdf.inputs["Roughness"].default_value = 0.4
    bsdf.inputs["Emission Color"].default_value = (color[0], color[1], color[2], 1)
    bsdf.inputs["Emission Strength"].default_value = strength
    if attr:
        a = N(nt, "ShaderNodeAttribute", (-500, -100), attribute_name=attr)
        mr = N(nt, "ShaderNodeMapRange", (-250, -100), inputs={"From Min": dark_below, "From Max": 1.0, "To Min": 0.0, "To Max": strength * 1.6})
        L(nt, a.outputs["Fac"], mr.inputs["Value"])
        L(nt, mr.outputs["Result"], bsdf.inputs["Emission Strength"])
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _hull_skin(mat):
    """Outer skin of the hull seen through crust cracks: dark bronze plates with glowing gold seams."""
    nt = clear(mat)
    out = N(nt, "ShaderNodeOutputMaterial", (700, 0))
    bsdf = N(nt, "ShaderNodeBsdfPrincipled", (400, 0))
    tc = N(nt, "ShaderNodeTexCoord", (-900, 0))
    vor = N(nt, "ShaderNodeTexVoronoi", (-650, 0), feature='DISTANCE_TO_EDGE', inputs={"Scale": 0.42})
    L(nt, tc.outputs["Object"], vor.inputs["Vector"])
    seam = N(nt, "ShaderNodeMapRange", (-380, 0), inputs={"From Min": 0.0, "From Max": 0.035, "To Min": 1.0, "To Max": 0.0})
    L(nt, vor.outputs["Distance"], seam.inputs["Value"])
    bsdf.inputs["Base Color"].default_value = (0.42, 0.26, 0.09, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.42
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.56, 0.18, 1)
    em = N(nt, "ShaderNodeMath", (-100, -200), operation='MULTIPLY')
    em.inputs[1].default_value = 16.0
    add = N(nt, "ShaderNodeMath", (100, -200), operation='ADD')
    add.inputs[1].default_value = 0.35
    L(nt, seam.outputs["Result"], em.inputs[0])
    L(nt, em.outputs[0], add.inputs[0])
    L(nt, add.outputs[0], bsdf.inputs["Emission Strength"])
    L(nt, bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


BUILDERS = {
    "Gold":      lambda m: _metal(m, (1.00, 0.66, 0.22), 0.13, 0.30, wear_dark=0.66, scale=1.0, bump=0.04),
    "Brass":     lambda m: _metal(m, (0.50, 0.30, 0.11), 0.22, 0.42, wear_dark=0.68, scale=1.1, bump=0.04),
    "Bronze":    lambda m: _metal(m, (0.16, 0.095, 0.045), 0.30, 0.52, wear_dark=0.68, scale=1.2, bump=0.05),
    "DarkMetal": lambda m: _metal(m, (0.085, 0.060, 0.040), 0.26, 0.48, wear_dark=0.65, scale=1.0, bump=0.05),
    "Silver":    lambda m: _metal(m, (0.80, 0.81, 0.84), 0.30, 0.55, wear_dark=0.6, scale=1.5, bump=0.12, metallic=0.75),
    "Window":    lambda m: _emit(m, (1.0, 0.52, 0.17), 2.3, attr="rnd", dark_below=0.44),
    "Lamp":      lambda m: _emit(m, (1.0, 0.66, 0.32), 9.0),
    "CoreGlow":  lambda m: _emit(m, (1.0, 0.80, 0.52), 400.0, base=(1, 0.8, 0.5)),
    "Enamel":    lambda m: _metal(m, (0.012, 0.03, 0.10), 0.12, 0.3, wear_dark=0.6, scale=0.4, bump=0.05, metallic=0.3),
    "HullSkin":  _hull_skin,
}


def get(name):
    """Return the canonical material (created on first use)."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        if name in BUILDERS:
            BUILDERS[name](m)
        else:
            m.use_nodes = True
    return m


def rebuild_all():
    """Rebuild every canonical material in place (used by the final assembly after appending modules)."""
    for name, fn in BUILDERS.items():
        m = bpy.data.materials.get(name)
        if m is not None:
            fn(m)
