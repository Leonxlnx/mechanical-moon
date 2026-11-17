"""Shared helpers: numpy noise, fast mesh creation, collections, cameras, EEVEE setup, test lighting."""
import bpy, os, sys, math, time
import numpy as np
from mathutils import Vector, Matrix, Euler

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def P(*a):
    return os.path.join(PROJ, *a)


def log(*a):
    print("[%s]" % time.strftime("%H:%M:%S"), *a)
    sys.stdout.flush()


# ------------------------------------------------------------------ noise (vectorised, deterministic)
def _hash3(ix, iy, iz, seed):
    h = (ix.astype(np.uint32) * np.uint32(374761393)
         + iy.astype(np.uint32) * np.uint32(668265263)
         + iz.astype(np.uint32) * np.uint32(1440662683)
         + np.uint32((seed * 2654435761) & 0xFFFFFFFF))
    h = (h ^ (h >> np.uint32(13))) * np.uint32(1274126177)
    h = h ^ (h >> np.uint32(16))
    return (h & np.uint32(0xFFFFFF)).astype(np.float32) / np.float32(16777215.0)


def noise3(p, seed=0):
    """Value noise. p: (N,3). Returns float32 (N,) in [-1, 1]."""
    p = np.asarray(p, dtype=np.float64)
    pf = np.floor(p)
    f = (p - pf).astype(np.float32)
    i = pf.astype(np.int64)
    u = f * f * f * (f * (f * 6 - 15) + 10)
    ix, iy, iz = i[:, 0], i[:, 1], i[:, 2]
    ux, uy, uz = u[:, 0], u[:, 1], u[:, 2]

    def h(dx, dy, dz):
        return _hash3(ix + dx, iy + dy, iz + dz, seed)
    x00 = h(0, 0, 0) * (1 - ux) + h(1, 0, 0) * ux
    x10 = h(0, 1, 0) * (1 - ux) + h(1, 1, 0) * ux
    x01 = h(0, 0, 1) * (1 - ux) + h(1, 0, 1) * ux
    x11 = h(0, 1, 1) * (1 - ux) + h(1, 1, 1) * ux
    y0 = x00 * (1 - uy) + x10 * uy
    y1 = x01 * (1 - uy) + x11 * uy
    return (y0 * (1 - uz) + y1 * uz) * 2 - 1


def fbm3(p, octaves=4, lacunarity=2.0, gain=0.5, seed=0, ridged=False):
    """Fractal noise in roughly [-1, 1]. p: (N,3)."""
    p = np.asarray(p, dtype=np.float64)
    out = np.zeros(len(p), dtype=np.float32)
    amp, norm, freq = 1.0, 0.0, 1.0
    for o in range(octaves):
        n = noise3(p * freq + 17.13 * o, seed + o * 31)
        if ridged:
            n = 1.0 - 2.0 * np.abs(n)
        out += amp * n
        norm += amp
        amp *= gain
        freq *= lacunarity
    return out / norm


def normalize(v):
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def write_png(path, arr):
    """Minimal PNG writer. arr: uint16 (H,W) grey or uint8 (H,W,3) RGB; row 0 = BOTTOM (Blender convention)."""
    import zlib, struct
    arr = arr[::-1]
    h, w = arr.shape[:2]
    if arr.dtype == np.uint16:
        ct, bd = 0, 16
        rows = arr.astype('>u2').view(np.uint8).reshape(h, w * 2)
    else:
        ct, bd = 2, 8
        rows = np.ascontiguousarray(arr).reshape(h, w * 3)
    raw = np.zeros((h, rows.shape[1] + 1), dtype=np.uint8)
    raw[:, 1:] = rows

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, bd, ct, 0, 0, 0)))
        f.write(chunk(b"IDAT", zlib.compress(raw.tobytes(), 5)))
        f.write(chunk(b"IEND", b""))


# ------------------------------------------------------------------ scene / collections
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


def save_blend(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    log("saved", path)


def append_collection(blend_path, name):
    """Append a collection from another .blend and link it into the current scene."""
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        if name not in src.collections:
            raise RuntimeError("collection %s not in %s" % (name, blend_path))
        dst.collections = [name]
    c = dst.collections[0]
    bpy.context.scene.collection.children.link(c)
    return c


# ------------------------------------------------------------------ meshes
def mesh_np(name, verts, faces, uv=None, smooth=True, attrs=None, mats=None, mat_idx=None, sharp_angle=None):
    """Fast mesh creation from numpy.
    verts: (N,3). faces: (M,k) int array or a list of such arrays (mix tris/quads/ngons of fixed k each).
    uv: per-loop (L,2) in the same order as the concatenated faces. attrs: {name: (domain, array)}.
    mats: list of materials; mat_idx: per-face material index (M_total,)."""
    verts = np.ascontiguousarray(verts, dtype=np.float32)
    if isinstance(faces, np.ndarray):
        faces = [faces]
    faces = [np.ascontiguousarray(f, dtype=np.int32) for f in faces if len(f)]
    me = bpy.data.meshes.new(name)
    loops = np.concatenate([f.ravel() for f in faces]) if faces else np.zeros(0, np.int32)
    counts = np.concatenate([np.full(len(f), f.shape[1], dtype=np.int32) for f in faces]) if faces else np.zeros(0, np.int32)
    starts = np.zeros(len(counts), dtype=np.int32)
    if len(counts) > 1:
        starts[1:] = np.cumsum(counts)[:-1]
    me.vertices.add(len(verts))
    me.loops.add(len(loops))
    me.polygons.add(len(counts))
    me.vertices.foreach_set("co", verts.ravel())
    me.polygons.foreach_set("loop_start", starts)
    me.polygons.foreach_set("vertices", loops)
    if mat_idx is not None:
        me.polygons.foreach_set("material_index", np.ascontiguousarray(mat_idx, dtype=np.int32))
    me.update(calc_edges=True)
    if uv is not None:
        uvl = me.uv_layers.new(name="UVMap")
        uvl.data.foreach_set("uv", np.ascontiguousarray(uv, dtype=np.float32).ravel())
    if attrs:
        for an, (domain, arr) in attrs.items():
            arr = np.ascontiguousarray(arr, dtype=np.float32)
            if arr.ndim == 1:
                a = me.attributes.new(an, 'FLOAT', domain)
                a.data.foreach_set("value", arr)
            elif arr.shape[1] == 3:
                a = me.attributes.new(an, 'FLOAT_VECTOR', domain)
                a.data.foreach_set("vector", arr.ravel())
            else:
                a = me.attributes.new(an, 'FLOAT_COLOR', domain)
                a.data.foreach_set("color", arr.ravel())
    if mats:
        for m in mats:
            me.materials.append(m)
    if smooth:
        me.shade_smooth()
    else:
        me.shade_flat()
    if sharp_angle is not None:
        me.set_sharp_from_angle(angle=math.radians(sharp_angle))
    return me


def obj_np(name, collection, verts, faces, **kw):
    me = mesh_np(name, verts, faces, **kw)
    ob = bpy.data.objects.new(name, me)
    collection.objects.link(ob)
    return ob


def mesh_arrays(me):
    """Return (verts (N,3) float32, loop vertex indices, loop_starts, loop_totals) of a mesh."""
    nv = len(me.vertices)
    co = np.empty(nv * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    nl = len(me.loops)
    li = np.empty(nl, dtype=np.int32)
    me.loops.foreach_get("vertex_index", li)
    npoly = len(me.polygons)
    ls = np.empty(npoly, dtype=np.int32)
    lt = np.empty(npoly, dtype=np.int32)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    return co.reshape(-1, 3), li, ls, lt


def join_meshes(parts):
    """parts: list of (verts (N,3), faces (M,k)) with the same k. Returns merged (verts, faces)."""
    vs, fs, off = [], [], 0
    for v, f in parts:
        vs.append(np.asarray(v, dtype=np.float32))
        fs.append(np.asarray(f, dtype=np.int32) + off)
        off += len(v)
    return np.concatenate(vs), np.concatenate(fs)


def tri_count(objs=None):
    n = 0
    for o in (objs or bpy.data.objects):
        if o.type == 'MESH':
            me = o.data
            n += sum(p.loop_total - 2 for p in me.polygons) if len(me.polygons) < 20000 else int(len(me.loops) - 2 * len(me.polygons))
    return n


# ------------------------------------------------------------------ camera / render
def look_at(obj, target, roll=0.0):
    d = Vector(target) - Vector(obj.location)
    q = d.to_track_quat('-Z', 'Y')
    obj.rotation_euler = q.to_euler()
    if roll:
        obj.rotation_euler.rotate_axis('Z', roll)


def add_camera(name, loc, target, lens=35.0, clip=(0.5, 30000.0), collection=None):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.clip_start, cam.clip_end = clip
    cam.sensor_width = 36.0
    ob = bpy.data.objects.new(name, cam)
    (collection or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


def _set(o, **kw):
    for k, v in kw.items():
        try:
            setattr(o, k, v)
        except Exception as e:
            print("  (skip %s=%r: %s)" % (k, v, e))


def setup_eevee(sc=None, samples=16, res=(960, 540), volumetrics=True, rt=True):
    sc = sc or bpy.context.scene
    try:
        sc.render.engine = 'BLENDER_EEVEE_NEXT'
    except Exception:
        sc.render.engine = 'BLENDER_EEVEE'
    ee = sc.eevee
    _set(ee, taa_render_samples=samples, taa_samples=samples,
         use_raytracing=rt, ray_tracing_method='SCREEN',
         use_shadows=True, shadow_ray_count=2, shadow_step_count=6,
         use_volumetric_shadows=True, volumetric_tile_size='4', volumetric_samples=96,
         volumetric_start=1.0, volumetric_end=1500.0, volumetric_sample_distribution=0.85,
         volumetric_shadow_samples=24, volumetric_ray_depth=8,
         use_fast_gi=True, fast_gi_method='GLOBAL_ILLUMINATION',
         use_overscan=True, overscan_size=6.0)
    try:
        _set(ee.ray_tracing_options, resolution_scale='2', trace_max_roughness=0.5,
             screen_trace_quality=0.5, screen_trace_thickness=1.0, use_denoise=True)
    except Exception as e:
        print("rt options:", e)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.fps = 30
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_mode = 'RGB'
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except Exception:
        pass
    return sc


def quick_render(path, loc, target, lens=35.0, res=(960, 540), samples=16, frame=None, sc=None):
    """Render one still from a temporary camera. Returns seconds taken."""
    sc = sc or bpy.context.scene
    if frame is not None:
        sc.frame_set(frame)
    setup_eevee(sc, samples=samples, res=res)
    cam = add_camera("_QuickCam", loc, target, lens)
    sc.camera = cam
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    bpy.data.objects.remove(cam)
    log("rendered %s in %.1fs" % (path, dt))
    return dt


# ------------------------------------------------------------------ standard test rig (approximates final lighting)
def add_test_rig(fog=True, stand_in_moon=False, world=True):
    """Core point light at the moon centre, cool moonlight sun, dark world, optional mist volume and
    a stand-in emissive moon. Use it for module test renders so results match the final lighting."""
    import config as C
    sc = bpy.context.scene
    col = coll("TESTRIG")
    # core light
    ld = bpy.data.lights.new("CoreLight", 'POINT')
    ld.energy = C.CORE_POWER
    ld.color = C.CORE_COLOR
    ld.shadow_soft_size = C.CORE_R
    lo = bpy.data.objects.new("CoreLight", ld)
    lo.location = C.MOON_C
    col.objects.link(lo)
    # moonlight
    sd = bpy.data.lights.new("MoonLight", 'SUN')
    sd.energy = C.MOONLIGHT_STRENGTH
    sd.color = C.MOONLIGHT_COLOR
    sd.angle = math.radians(2.0)
    so = bpy.data.objects.new("MoonLight", sd)
    so.location = (0, 0, 400)
    d = Vector(C.MOONLIGHT_DIR).normalized()
    so.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    col.objects.link(so)
    if world and sc.world is None:
        w = bpy.data.worlds.new("TestWorld")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.010, 0.018, 0.045, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
        sc.world = w
    if fog:
        me = bpy.data.meshes.new("TestFog")
        import bmesh
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(me)
        bm.free()
        fo = bpy.data.objects.new("TestFog", me)
        fo.scale = (1600, 1600, 420)
        fo.location = (0, 0, 205)
        col.objects.link(fo)
        m = bpy.data.materials.new("TestFogMat")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        vs = nt.nodes.new("ShaderNodeVolumeScatter")
        vs.inputs["Density"].default_value = 0.0006
        vs.inputs["Anisotropy"].default_value = 0.35
        vs.inputs["Color"].default_value = (0.8, 0.88, 1.0, 1)
        nt.links.new(vs.outputs[0], out.inputs["Volume"])
        me.materials.append(m)
    if stand_in_moon:
        import bmesh
        me = bpy.data.meshes.new("StandInMoon")
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=5, radius=C.R)
        bm.to_mesh(me)
        bm.free()
        me.shade_smooth()
        mo = bpy.data.objects.new("StandInMoon", me)
        mo.location = C.MOON_C
        col.objects.link(mo)
        m = bpy.data.materials.new("StandInMoonMat")
        m.use_nodes = True
        b = m.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.35, 0.36, 0.38, 1)
        b.inputs["Roughness"].default_value = 0.9
        me.materials.append(m)
    return col
