"""Quick EEVEE headless benchmark: dense mesh + volumetrics + raytracing at 1080p."""
import bpy, time, sys, math

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[0] if argv else "//bench.png"
samples = int(argv[1]) if len(argv) > 1 else 32

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
try:
    sc.render.engine = 'BLENDER_EEVEE_NEXT'
except Exception:
    sc.render.engine = 'BLENDER_EEVEE'
print("ENGINE", sc.render.engine, "BLENDER", bpy.app.version_string)
try:
    print("GPU BACKEND", bpy.context.preferences.system.gpu_backend)
except Exception as e:
    print("no gpu_backend attr", e)

ee = sc.eevee
ee.taa_render_samples = samples
ee.use_raytracing = True
ee.use_volumetric_shadows = True
ee.volumetric_tile_size = '4'
ee.volumetric_samples = 96
sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
sc.render.filepath = out
sc.render.image_settings.file_format = 'PNG'

# dense spheres
for i in range(6):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=7, radius=1.0, location=(math.cos(i) * 3, math.sin(i) * 3, 0))
    o = bpy.context.object
    m = bpy.data.materials.new("m%d" % i)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = 0.25
    bsdf.inputs["Base Color"].default_value = (0.9, 0.6, 0.25, 1)
    o.data.materials.append(m)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, -1))

# light + world volume
bpy.ops.object.light_add(type='POINT', location=(0, 0, 0.0))
L = bpy.context.object
L.data.energy = 20000
L.data.color = (1.0, 0.75, 0.45)
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
nt = w.node_tree
vol = nt.nodes.new("ShaderNodeVolumeScatter")
vol.inputs["Density"].default_value = 0.03
nt.links.new(vol.outputs[0], nt.nodes["World Output"].inputs["Volume"])
nt.nodes["Background"].inputs[0].default_value = (0.01, 0.015, 0.03, 1)

bpy.ops.object.camera_add(location=(0, -12, 3), rotation=(math.radians(78), 0, 0))
sc.camera = bpy.context.object

t = time.time()
bpy.ops.render.render(write_still=True)
t1 = time.time() - t
t = time.time()
sc.render.filepath = out.replace(".png", "_2.png")
bpy.ops.render.render(write_still=True)
t2 = time.time() - t
print("BENCH first=%.1fs second=%.1fs samples=%d" % (t1, t2, samples))
