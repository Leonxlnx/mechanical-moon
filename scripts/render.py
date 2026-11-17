"""Render frames from blend/moon_scene.blend.

  blender -b blend/moon_scene.blend -P render.py -- --frames 1,200,400 | --range 1 1350 [--step 1]
        [--res 1920x1080] [--samples 12] [--out frames] [--prefix f_] [--bench] [--overwrite]
        [--nojitter] [--nogi] [--volsamples 64] [--tile 4] [--rtscale 2] [--jpg]
Existing files are skipped (safe to restart).
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K, config as C
from params import P

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None, flag=False):
    if name in argv:
        return True if flag else argv[argv.index(name) + 1]
    return default


sc = bpy.context.scene
bpy.context.preferences.system.anisotropic_filter = 'FILTER_16'
RES = tuple(int(v) for v in arg("--res", "1920x1080").split("x"))
SAMPLES = int(arg("--samples", 12))
OUT = arg("--out", K.P("frames"))
PREFIX = arg("--prefix", "f_")
os.makedirs(OUT, exist_ok=True)
K.setup_eevee(sc, samples=SAMPLES, res=RES)
K._set(sc.eevee, shadow_pool_size='512', shadow_resolution_scale=P.get("shadow_scale", 0.8))
if arg("--nogi", flag=True):
    sc.eevee.use_fast_gi = False
if arg("--volsamples"):
    sc.eevee.volumetric_samples = int(arg("--volsamples"))
if arg("--volend"):
    sc.eevee.volumetric_end = float(arg("--volend"))
if arg("--tile"):
    sc.eevee.volumetric_tile_size = arg("--tile")
if arg("--rtscale"):
    sc.eevee.ray_tracing_options.resolution_scale = arg("--rtscale")
if arg("--nojitter", flag=True):
    for l in bpy.data.lights:
        K._set(l, use_shadow_jitter=False)
if arg("--jpg", flag=True):
    sc.render.image_settings.file_format = 'JPEG'
    sc.render.image_settings.quality = 92
    EXT = ".jpg"
else:
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.compression = 15
    EXT = ".png"

marks = sorted([(m.frame, m.camera) for m in sc.timeline_markers if m.camera], key=lambda x: x[0])


def cam_for(f):
    c = marks[0][1]
    for mf, mc in marks:
        if mf <= f:
            c = mc
    return c


def render_frame(f, path):
    sc.frame_set(f)
    sc.camera = cam_for(f)
    sc.render.filepath = path
    t = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t


if arg("--bench", flag=True):
    f = int(arg("--frames", "200").split(",")[0])
    ee = sc.eevee
    render_frame(f, os.path.join(OUT, "bench_warm" + EXT))
    base = dict(jit=True, gi=True, vol=96, rt='2', rtq=0.5)
    variants = [("base", {}), ("nojitter", dict(jit=False)), ("nogi", dict(gi=False)), ("vol64", dict(vol=64)),
                ("rt4", dict(rt='4')), ("all", dict(jit=False, gi=False, vol=64)), ("nort", dict(rtoff=True))]
    for name, v in variants:
        cfg = dict(base)
        cfg.update(v)
        for l in bpy.data.lights:
            K._set(l, use_shadow_jitter=cfg["jit"])
        ee.use_fast_gi = cfg["gi"]
        ee.volumetric_samples = cfg["vol"]
        ee.ray_tracing_options.resolution_scale = cfg["rt"]
        ee.use_raytracing = not cfg.get("rtoff", False)
        dt = render_frame(f, os.path.join(OUT, "bench_%s%s" % (name, EXT)))
        K.log("BENCH %-9s %.1fs  (samples %d, %dx%d)" % (name, dt, SAMPLES, RES[0], RES[1]))
    sys.exit(0)

if arg("--anim", flag=True):
    # animation render: the render depsgraph persists between frames (much less per-frame overhead)
    a, b = argv[argv.index("--range") + 1: argv.index("--range") + 3]
    sc.frame_start, sc.frame_end = int(a), int(b)
    sc.frame_step = int(arg("--step", 1))
    sc.render.filepath = os.path.join(OUT, PREFIX)
    sc.render.use_overwrite = bool(arg("--overwrite", flag=True))
    sc.render.use_placeholder = False
    sc.render.use_file_extension = True
    st = {"t": time.time(), "n": 0, "t0": time.time()}

    def _post(scene, *a_):
        now = time.time()
        st["n"] += 1
        if st["n"] <= 5 or st["n"] % 10 == 0:
            K.log("ANIM frame %d  %.1fs  avg %.1fs  n=%d" % (scene.frame_current, now - st["t"], (now - st["t0"]) / st["n"], st["n"]))
        st["t"] = now
    bpy.app.handlers.render_post.append(_post)
    bpy.ops.render.render(animation=True)
    K.log("RENDER DONE (anim) %d frames in %.1f min" % (st["n"], (time.time() - st["t0"]) / 60))
    sys.exit(0)

if arg("--frames"):
    frames = [int(x) for x in arg("--frames").split(",")]
else:
    a, b = argv[argv.index("--range") + 1: argv.index("--range") + 3]
    frames = list(range(int(a), int(b) + 1, int(arg("--step", 1))))
t0 = time.time()
done = 0
for f in frames:
    path = os.path.join(OUT, "%s%04d%s" % (PREFIX, f, EXT))
    if os.path.exists(path) and not arg("--overwrite", flag=True):
        continue
    dt = render_frame(f, path)
    done += 1
    if done <= 3 or done % 10 == 0 or arg("--verbose", flag=True):
        el = time.time() - t0
        K.log("frame %d  %.1fs  avg %.1fs  done %d/%d  eta %.0f min" % (f, dt, el / done, done, len(frames), (len(frames) - done) * el / done / 60))
K.log("RENDER DONE %d frames in %.1f min" % (done, (time.time() - t0) / 60))
