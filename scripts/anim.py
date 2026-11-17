"""Animation: gimbal rings, spinning parts, drifting crust fragments, fog drift, light pulse, cameras + shot markers."""
import bpy, math, os
import numpy as np
from mathutils import Vector, Quaternion, Matrix
import common as K, config as C
from shots import SHOTS

FPS = C.FPS
NF = C.FRAMES


def _lin(fc):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
    fc.extrapolation = 'LINEAR'


def _fcurves(ob):
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
    return out or list(ad.action.fcurves)


def gimbals():
    for ob in bpy.data.objects:
        if "gim_dps" not in ob:
            continue
        ax = int(ob["gim_axis"])
        for f in (1, NF + 1):
            t = (f - 1) / FPS
            e = list(ob.rotation_euler)
            e[ax] = math.radians(ob["gim_phase"] + ob["gim_dps"] * t)
            ob.rotation_euler = e
            ob.keyframe_insert("rotation_euler", index=ax, frame=f)
        for fc in _fcurves(ob):
            _lin(fc)


def spins():
    n = 0
    for ob in bpy.data.objects:
        if "spin_dps" not in ob:
            continue
        dps = float(ob["spin_dps"])
        q0 = ob.matrix_basis.to_quaternion()
        ob.rotation_mode = 'QUATERNION'
        step = 15
        for f in range(1, NF + 2 + step, step):
            t = (f - 1) / FPS
            ob.rotation_quaternion = q0 @ Quaternion((0, 0, 1), math.radians(dps * t))
            ob.keyframe_insert("rotation_quaternion", frame=f)
        for fc in _fcurves(ob):
            _lin(fc)
        n += 1
    K.log("spin objects:", n)


def fragments():
    rng = np.random.default_rng(99)
    n = 0
    for ob in bpy.data.objects:
        if "kind" not in ob or not ob.name.startswith("CRUST_"):
            continue
        kind = float(ob["kind"])
        n += 1
        if kind == 3.0:      # gravel cloud: slow swirl about a random axis through the moon centre
            ax = Vector(K.normalize(rng.standard_normal(3)))
            ob.rotation_mode = 'QUATERNION'
            for f in (1, NF + 1):
                ob.rotation_quaternion = Quaternion(ax, math.radians(0.5 * (f - 1) / FPS))
                ob.keyframe_insert("rotation_quaternion", frame=f)
            for fc in _fcurves(ob):
                _lin(fc)
            continue
        loc0 = ob.location.copy()
        nrm = Vector(ob["nrm"])
        bob = float(ob["bob"])
        per = float(ob["period"])
        ph = float(ob["phase"])
        side = Vector(K.normalize(np.cross(np.array(nrm), rng.standard_normal(3))))
        step = 20
        for f in range(1, NF + 1 + step, step):
            t = (f - 1) / FPS
            ob.location = loc0 + nrm * (bob * math.sin(2 * math.pi * t / per + ph)) + side * (0.4 * bob * math.sin(2 * math.pi * t / (per * 1.7) + ph * 2))
            ob.keyframe_insert("location", frame=f)
        if kind >= 1.0:      # free pieces tumble slowly
            q0 = ob.rotation_quaternion.copy()
            ax = Vector(K.normalize(rng.standard_normal(3)))
            rate = rng.uniform(0.8, 3.5) * (1 if rng.random() < 0.5 else -1) * (1.0 if kind == 1.0 else 2.2)
            for f in range(1, NF + 31, 30):
                ob.rotation_quaternion = Quaternion(ax, math.radians(rate * (f - 1) / FPS)) @ q0
                ob.keyframe_insert("rotation_quaternion", frame=f)
    K.log("fragments animated:", n)


def fog_and_light(sc):
    m = bpy.data.materials.get("FogMat")
    if m:
        mp = m.node_tree.nodes.get("FogDrift")
        if mp:
            for f, v in ((1, (0, 0, 0)), (NF + 1, (60.0, 25.0, 8.0))):
                mp.inputs["Location"].default_value = v
                mp.inputs["Location"].keyframe_insert("default_value", frame=f)
            for fc in m.node_tree.animation_data.action.fcurves:
                _lin(fc)
    cgm = bpy.data.materials.get("CoreGlow")
    if cgm and cgm.node_tree.nodes.get("CorePlasma"):
        nzp = cgm.node_tree.nodes["CorePlasma"]
        for f, v in ((1, 0.0), (NF + 1, 7.0)):
            nzp.inputs["W"].default_value = v
            nzp.inputs["W"].keyframe_insert("default_value", frame=f)
        for fc in cgm.node_tree.animation_data.action.fcurves:
            _lin(fc)
    L_ = bpy.data.objects.get("CoreLight")
    if L_:
        base = L_.data.energy
        for f in range(1, NF + 9, 8):
            t = (f - 1) / FPS
            surge = 1.0 + 0.30 * max(0.0, 1 - abs(t - 30.2) / 1.6) + 0.18 * max(0.0, 1 - abs(t - 5.6) / 0.9)
            L_.data.energy = base * (1.0 + 0.05 * math.sin(t * 2.1) + 0.03 * math.sin(t * 5.3 + 1.0)) * surge
            L_.data.keyframe_insert("energy", frame=f)
        L_.data.energy = base


# lightning: (time s, bolt top xyz, bolt bottom xyz, seed)
FLASHES = [
    (8.15, (-180, 960, 420), (-150, 990, 0), 1),       # left of the moon in the reveal shot
    (12.10, (400, 860, 420), (440, 820, 0), 2),        # left of the moon in the side shot
    (41.62, (740, 760, 430), (690, 800, 0), 3),        # right of the moon in the final shot
]
FLASH_PATTERN = [1.0, 0.85, 0.12, 0.65, 0.30, 0.10, 0.0]


def _bolt_points(a, b, rng, depth=6, sway=0.16):
    pts = [np.array(a, float), np.array(b, float)]
    for d in range(depth):
        new = [pts[0]]
        for i in range(len(pts) - 1):
            p, q = pts[i], pts[i + 1]
            mid = (p + q) / 2
            off = rng.standard_normal(3) * np.linalg.norm(q - p) * sway
            off[2] *= 0.3
            new += [mid + off, q]
        pts = new
    return np.array(pts)


def lightning(sc):
    from mats import clear, N, L
    col = K.coll("FX")
    m = bpy.data.materials.new("Lightning")
    nt = clear(m)
    out = N(nt, "ShaderNodeOutputMaterial", (300, 0))
    em = N(nt, "ShaderNodeEmission", (0, 0))
    em.inputs["Color"].default_value = (0.75, 0.82, 1.0, 1)
    em.inputs["Strength"].default_value = 420.0
    L(nt, em.outputs[0], out.inputs["Surface"])
    sd = bpy.data.lights.new("FlashSun", 'SUN')
    sd.color = (0.72, 0.80, 1.0)
    sd.energy = 0.0
    sd.angle = math.radians(8)
    K._set(sd, use_shadow=False, volume_factor=0.0)
    so = bpy.data.objects.new("FlashSun", sd)
    col.objects.link(so)
    rc = bpy.data.collections.get("EXTERIOR_RECEIVERS")
    if rc:
        try:
            so.light_linking.receiver_collection = rc
        except Exception as e:
            K.log("flash light linking:", e)
    gains = []
    if sc.world and sc.world.node_tree:
        gains = [n for n in sc.world.node_tree.nodes if n.name.startswith("WorldGain")]
    base_gain = [g.inputs[1].default_value for g in gains]

    def key_all(f, amt, direction=None):
        sd.energy = 5.0 * amt
        sd.keyframe_insert("energy", frame=f)
        for g, b in zip(gains, base_gain):
            g.inputs[1].default_value = b * (1.0 + 1.1 * amt)
            g.inputs[1].keyframe_insert("default_value", frame=f)

    key_all(1, 0.0)
    for (t, top, bot, seed) in FLASHES:
        rng = np.random.default_rng(700 + seed)
        f0 = int(round(t * FPS)) + 1
        pts = _bolt_points(top, bot, rng, depth=7, sway=0.15)
        parts = []
        segs = [(pts, 0.55)]
        for _ in range(3):                      # branches
            i = int(rng.integers(len(pts) // 5, len(pts) * 3 // 4))
            end = pts[i] + np.array([rng.uniform(-170, 170), rng.uniform(-60, 60), -rng.uniform(70, 190)])
            segs.append((_bolt_points(pts[i], end, rng, depth=5, sway=0.2), 0.24))
        vs, fs, off = [], [], 0
        for p, rad in segs:
            ref = np.tile(np.array([[0.3, 1.0, 0.1]]), (len(p), 1))
            tan = K.normalize(np.gradient(p, axis=0))
            n1 = K.normalize(np.cross(tan, ref))
            n2 = np.cross(tan, n1)
            ring = [p + rad * (math.cos(a_) * n1 + math.sin(a_) * n2) for a_ in (0, 2.094, 4.189)]
            v = np.stack(ring, 1).reshape(-1, 3)
            i_ = np.arange(len(p) - 1)[:, None] * 3
            j_ = np.arange(3)[None, :]
            q = np.stack([i_ + j_, i_ + 3 + j_, i_ + 3 + (j_ + 1) % 3, i_ + (j_ + 1) % 3], -1).reshape(-1, 4)
            vs.append(v)
            fs.append(q + off)
            off += len(v)
        ob = K.obj_np("Bolt_%d" % seed, col, np.concatenate(vs), np.concatenate(fs), mats=[m], smooth=False)
        ob.visible_shadow = False
        ob.scale = (0, 0, 0)
        ob.keyframe_insert("scale", frame=1)
        ob.keyframe_insert("scale", frame=f0 - 1)
        mid = (np.array(top) + np.array(bot)) / 2
        so.rotation_euler = Vector((mid[0], mid[1], 600.0)).normalized().to_track_quat('Z', 'Y').to_euler()
        so.keyframe_insert("rotation_euler", frame=f0 - 1)
        key_all(f0 - 1, 0.0)
        for k, amt in enumerate(FLASH_PATTERN):
            key_all(f0 + k, amt)
            s = 1.0 if amt > 0.5 else 0.0
            ob.scale = (s, s, s)
            ob.keyframe_insert("scale", frame=f0 + k)
        for fc in _fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    for idb in [sd, so] + ([sc.world.node_tree] if gains else []):
        for fc in _fcurves(idb):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT' if idb is so else 'LINEAR'
    K.log("lightning flashes:", len(FLASHES))


def cameras(sc, moon):
    col = K.coll("CAMERAS")
    for m in list(sc.timeline_markers):
        sc.timeline_markers.remove(m)
    for sh in SHOTS:
        f0, f1 = sh["frames"]
        cam = bpy.data.cameras.new("Cam_" + sh["name"])
        cam.sensor_width = 36.0
        cam.clip_start = sh.get("clip", 0.4)
        cam.clip_end = 30000.0
        co = bpy.data.objects.new("Cam_" + sh["name"], cam)
        tg = bpy.data.objects.new("Tgt_" + sh["name"], None)
        col.objects.link(co)
        col.objects.link(tg)
        con = co.constraints.new('TRACK_TO')
        con.target = tg
        con.track_axis = 'TRACK_NEGATIVE_Z'
        con.up_axis = 'UP_Y'
        keys = sh["keys"]
        for (u, pos, tgt, lens) in keys:
            f = f0 + u * (f1 - f0)
            co.location = pos
            tg.location = tgt
            cam.lens = lens
            co.keyframe_insert("location", frame=f)
            tg.keyframe_insert("location", frame=f)
            cam.keyframe_insert("lens", frame=f)
        linear = len(keys) <= 2 or sh.get("linear", False)
        for idb in (co, tg, cam):
            for fc in _fcurves(idb):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR' if linear else 'BEZIER'
                    kp.handle_left_type = 'AUTO_CLAMPED'
                    kp.handle_right_type = 'AUTO_CLAMPED'
                fc.extrapolation = 'LINEAR'
                fc.update()
        if sh.get("roll"):
            co["roll"] = sh["roll"]
        if sh.get("dof"):
            cam.dof.use_dof = True
            cam.dof.focus_object = tg
            cam.dof.aperture_fstop = sh["dof"]
        mk = sc.timeline_markers.new("M_" + sh["name"], frame=f0)
        mk.camera = co
    sc.frame_start = 1
    sc.frame_end = NF
    K.log("cameras:", len(SHOTS))


def _pair(v):
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
    key = bpy.data.objects.get("MoonLight")
    if key:
        base_e = key.data.energy
        for sh in SHOTS:
            d, mul = sh["key"]
            for f in sh["frames"]:
                key.rotation_euler = Vector(d).normalized().to_track_quat('Z', 'Y').to_euler()
                key.keyframe_insert("rotation_euler", frame=f)
                key.data.energy = base_e * mul
                key.data.keyframe_insert("energy", frame=f)
        key.data.energy = base_e
        for idb in (key, key.data):
            for fc in idb.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    rim = bpy.data.lights.get("RimLight")
    if rim:
        base = rim.energy
        for sh in SHOTS:
            for f in sh["frames"]:
                rim.energy = base * sh.get("rim", 1.0)
                rim.keyframe_insert("energy", frame=f)
        rim.energy = base
        for fc in rim.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


def apply(sc, moon):
    sc.render.fps = FPS
    gimbals()
    spins()
    fragments()
    fog_and_light(sc)
    lightning(sc)
    cameras(sc, moon)
    grade(sc)
