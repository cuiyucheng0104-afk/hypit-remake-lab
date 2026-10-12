import json, sys, urllib.request, uuid
video, skip = sys.argv[1], int(sys.argv[2])
p = {
 "1": {"class_type": "VHS_LoadVideo", "inputs": {"video": video, "force_rate": 30, "custom_width": 1280, "custom_height": 624, "frame_load_cap": 1, "skip_first_frames": skip, "select_every_nth": 1, "format": "AnimateDiff"}},
 "2": {"class_type": "SDPoseOODLoader", "inputs": {"model_type": "WholeBody", "unet_precision": "bf16", "device": "auto", "unload_on_finish": True}},
 "3": {"class_type": "SDPoseOODProcessor", "inputs": {"sdpose_model": ["2", 0], "images": ["1", 0], "score_threshold": 0.3, "overlay_alpha": 1, "batch_size": 1, "prompt": "person .", "gd_threshold": 0.3, "save_for_editor": False, "filename_prefix_edit": "poses/pose_edit", "keep_face": True, "keep_hands": True, "keep_feet": True, "scale_for_xinsr": False, "pose_scale_factor": 1, "enable_confidence_filter": True}},
 "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": f"ref105/posetest_{skip}"}},
}
req = urllib.request.Request("http://127.0.0.1:6006/prompt", data=json.dumps({"prompt": p, "client_id": "ref105-" + uuid.uuid4().hex[:8]}).encode(), headers={"Content-Type": "application/json"})
try: print(json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"])
except urllib.error.HTTPError as e: print("HTTP", e.code, e.read().decode()[:1500])
