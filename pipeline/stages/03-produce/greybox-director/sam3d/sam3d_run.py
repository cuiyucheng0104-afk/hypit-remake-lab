"""Submit SAM 3D Body white-model renders to the ROG ComfyUI (via local tunnel 18188).

usage: python3 sam3d_run.py <clip.mp4> <frames> <max_objects>
"""
import json, sys, time, urllib.request

BASE = "http://127.0.0.1:18188"
GRAY = 0xC7C7C7  # 0.78 gray, matches the Jimeng white-model spec

def get(path):
    return json.load(urllib.request.urlopen(BASE + path))

INFO = {}
def info(node):
    if node not in INFO:
        INFO[node] = get("/object_info/" + node.replace(" ", "%20"))[node]
    return INFO[node]

def fill_dynamic(spec, prefix, choice, out):
    """Expand a COMFY_DYNAMICCOMBO_V3 input: pick option keys from `choice` (dotted path -> key), defaults elsewhere."""
    key = choice.get(prefix, spec[1]["options"][0]["key"])
    out[prefix] = key
    opt = next(o for o in spec[1]["options"] if o["key"] == key)
    for name, sub in opt["inputs"].get("required", {}).items():
        path = f"{prefix}.{name}"
        if sub[0] == "COMFY_DYNAMICCOMBO_V3":
            fill_dynamic(sub, path, choice, out)
        elif path in choice:
            out[path] = choice[path]
        elif "default" in sub[1]:
            out[path] = sub[1]["default"]
        elif isinstance(sub[0], list):
            out[path] = sub[0][0]

def node(cls, inputs, choice=None):
    choice = choice or {}
    for name, spec in info(cls)["input"].get("required", {}).items():
        if spec[0] == "COMFY_DYNAMICCOMBO_V3" and name not in inputs:
            fill_dynamic(spec, name, choice, inputs)
    return {"class_type": cls, "inputs": inputs}

def build(clip, frames, max_objects, tag):
    W, H = 1280, 620
    p = {
        "load": node("LoadVideo", {"file": clip}),
        "comp": node("GetVideoComponents", {"video": ["load", 0]}),
        "ck": node("CheckpointLoaderSimple", {"ckpt_name": "sam3.1_multiplex_fp16.safetensors"}),
        "txt": node("CLIPTextEncode", {"clip": ["ck", 1], "text": "person"}),
        "track": node("SAM3_VideoTrack", {"images": ["comp", 0], "model": ["ck", 0], "conditioning": ["txt", 0],
                                          "detection_threshold": 0.5, "max_objects": max_objects, "detect_interval": 1}),
        "mogeL": node("LoadMoGeModel", {"model_name": "moge_2_vitl_normal_fp16.safetensors"}),
        "moge": node("MoGeInference", {"moge_model": ["mogeL", 0], "image": ["comp", 0], "resolution_level": 9,
                                       "fov_x_degrees": 0.0, "batch_size": 4, "force_projection": True,
                                       "apply_mask": True, "refine_steps": 3}),
        "fov": node("MoGeGeometryToFOV", {"moge_geometry": ["moge", 0], "axis": "vertical", "unit": "degrees"}),
        "body": node("SAM3DBody_Loader", {"model_file": "sam_3d_body_dinov3_bf16.safetensors"}),
        "pred": node("SAM3DBody_Predict", {"sam3d_body_model": ["body", 0], "image": ["comp", 0], "track_data": ["track", 0],
                                           "run_hand_refinement": True, "fov": ["fov", 0], "batch_size": 64}),
        "smooth": node("SAM3DBody_Smooth", {"mhr_pose_data": ["pred", 0], "strength": 1.0, "method": "gaussian",
                                            "window": 7, "rotation_threshold_degrees": 30.0}),
        "gray": node("EmptyImage", {"width": W, "height": H, "batch_size": frames, "color": GRAY}),
        # A: mesh on flat gray (white-model candidate); B: mesh over source (alignment check); C: depth shader on gray
        "rA": node("SAM3DBody_Render", {"pose_data": ["smooth", 0], "background": ["gray", 0], "width": 0, "height": 0},
                   {"render_style": "mesh", "render_style.shader": "default", "render_style.person_palette_falloff": 1.0}),
        "rB": node("SAM3DBody_Render", {"pose_data": ["smooth", 0], "background": ["comp", 0], "width": 0, "height": 0},
                   {"render_style": "mesh", "render_style.shader": "default", "render_style.opacity": 0.7}),
        "rC": node("SAM3DBody_Render", {"pose_data": ["smooth", 0], "background": ["gray", 0], "width": 0, "height": 0},
                   {"render_style": "mesh", "render_style.shader": "normals"}),
        "glb": node("BuildPoseFile", {"pose_data": ["smooth", 0], "sam3d_body_model": ["body", 0], "fps": 30.0,
                                      "camera_translation": "absolute", "track_index": -1},
                    {"format": "glb", "format.mesh_style": "body_mesh"}),
        "save3d": node("Save3DAdvanced", {"model_3d": ["glb", 0], "filename_prefix": f"3d/{tag}",
                                          "viewport_state": None, "width": 1024, "height": 1024}),
    }
    if "--det" in sys.argv:  # per-frame RT-DETR person boxes instead of SAM3 tracking
        p["detL"] = node("UNETLoader", {"unet_name": "rt_detr_v4-x-hgnet_fp32.safetensors", "weight_dtype": "default"})
        p["det"] = node("RTDETR_detect", {"model": ["detL", 0], "image": ["comp", 0], "threshold": 0.4,
                                          "class_name": "person", "max_detections": 30})
        del p["pred"]["inputs"]["track_data"]; p["pred"]["inputs"]["bboxes"] = ["det", 1 if False else 0]
        for k in ("ck", "txt", "track"): del p[k]
    p["save3d"]["inputs"]["viewport_state"] = {}
    for k in ("rA", "rB", "rC"):
        p["v" + k] = node("CreateVideo", {"images": [k, 0], "fps": ["comp", 2]})
        p["s" + k] = node("SaveVideo", {"video": ["v" + k, 0], "filename_prefix": f"sam3d/{tag}_{k}"},
                          {"format": "mp4", "format.codec": "h264"})
    return p

def submit(prompt):
    req = urllib.request.Request(BASE + "/prompt", data=json.dumps({"prompt": prompt}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req))["prompt_id"]
    except urllib.error.HTTPError as e:
        print(e.read().decode()[:3000]); raise

if __name__ == "__main__":
    clip, frames, maxo = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    tag = clip.rsplit(".", 1)[0] + ("_det" if "--det" in sys.argv else "")
    p = build(clip, frames, maxo, tag)
    if "--dump" in sys.argv:
        print(json.dumps(p, indent=1)); sys.exit()
    pid = submit(p)
    t0 = time.time()
    print("submitted", pid, flush=True)
    while True:
        h = get("/history/" + pid)
        if pid in h:
            st = h[pid]["status"]
            print(tag, st.get("status_str"), f"{time.time()-t0:.0f}s")
            for m in st.get("messages", []):
                if m[0] in ("execution_error",):
                    print(json.dumps(m[1])[:2000])
            for nid, out in h[pid]["outputs"].items():
                print(nid, json.dumps(out)[:300])
            break
        time.sleep(5)
