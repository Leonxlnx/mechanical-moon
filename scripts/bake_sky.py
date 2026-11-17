"""Bake the procedural ENV_World (clouds + stars) into one equirect EXR so EEVEE only pays a texture fetch per sky pixel.
Cycles CPU, background only (no objects) -> noise free at a few samples."""
import sys, os, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
import common as K

sc = K.reset()
with bpy.data.libraries.load(K.P("blend", "env.blend"), link=False) as (src, dst):
    dst.worlds = ["ENV_World"]
sc.world = dst.worlds[0]
sc.frame_set(400)
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 6
sc.cycles.use_denoising = False
sc.cycles.max_bounces = 0
sc.cycles.use_adaptive_sampling = False
sc.render.threads_mode = 'FIXED'
sc.render.threads = 12
cam = bpy.data.cameras.new("pano")
cam.type = 'PANO'
try:
    cam.panorama_type = 'EQUIRECTANGULAR'
except Exception:
    cam.cycles.panorama_type = 'EQUIRECTANGULAR'
ob = bpy.data.objects.new("pano", cam)
sc.collection.objects.link(ob)
ob.location = (0, 0, 10)
ob.rotation_euler = (math.radians(90), 0, math.radians(-90))
sc.camera = ob
sc.render.resolution_x, sc.render.resolution_y = 8192, 4096
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = 'OPEN_EXR'
sc.render.image_settings.color_depth = '16'
sc.render.image_settings.exr_codec = 'ZIP'
sc.render.filepath = K.P("textures", "sky_bake.exr")
t = time.time()
bpy.ops.render.render(write_still=True)
K.log("SKY BAKE DONE %.1fs" % (time.time() - t))
