import bpy, sys, math, json
from mathutils import Vector
glb = sys.argv[sys.argv.index("--")+1]; out = sys.argv[sys.argv.index("--")+2]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
sc = bpy.context.scene
objs = bpy.data.objects
arms = [o for o in objs if o.type == "ARMATURE"]; meshes = [o for o in objs if o.type == "MESH"]
acts = bpy.data.actions
rng = [a.frame_range[:] for a in acts]
info = {"objects": len(objs), "armatures": len(arms), "meshes": len(meshes), "cameras": len([o for o in objs if o.type=="CAMERA"]),
        "actions": len(acts), "frame_ranges": sorted(set(tuple(map(int, r)) for r in rng))[:5]}
# Camera at origin looking down -Z? SAM3D uses camera-space; place a camera at origin facing the people's centroid
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
cen = sum(pts, Vector()) / len(pts)
info["centroid"] = [round(x, 2) for x in cen]
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam)
cam.location = (0, 0, 0)
d = cen - cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
cam.data.lens = 24; sc.camera = cam
sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "SINGLE"
sc.display.shading.single_color = (0.78, 0.78, 0.78)
sc.render.resolution_x, sc.render.resolution_y = 1280, 620
for i, f in enumerate([int(rng[0][0]) if rng else 1, 30, 60]):
    sc.frame_set(f); sc.render.filepath = f"{out}_{i}.png"; bpy.ops.render.render(write_still=True)
print("INFO", json.dumps(info))
