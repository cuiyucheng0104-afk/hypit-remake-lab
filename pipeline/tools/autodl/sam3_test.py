import json, sys, urllib.request, uuid
# 用法: sam3_test.py <video> <prefix> <threshold> <detection_limit> <prompt1> [prompt2 ...]   多个 prompt 的遮罩取并集
video, prefix, thr, limit = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
prompts = sys.argv[5:]
p = {
 "1": {"class_type": "VHS_LoadVideo", "inputs": {"video": video, "force_rate": 30, "custom_width": 1280, "custom_height": 624, "frame_load_cap": 0, "skip_first_frames": 0, "select_every_nth": 1, "format": "AnimateDiff"}},
 "2": {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3-fp16.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}},
}
last = None
for i, pr in enumerate(prompts):
    sid = str(10 + i)
    p[sid] = {"class_type": "easy sam3ImageSegmentation", "inputs": {"sam3_model": ["2", 0], "images": ["1", 0], "prompt": pr, "threshold": thr, "keep_model_loaded": True, "add_background": "none", "detection_limit": limit}}
    if last is None: last = [sid, 0]
    else:
        aid = str(30 + i); p[aid] = {"class_type": "AddMask", "inputs": {"mask1": last, "mask2": [sid, 0]}}; last = [aid, 0]
p["4"] = {"class_type": "GrowMask", "inputs": {"mask": last, "expand": 10, "tapered_corners": True}}
p["5"] = {"class_type": "DrawMaskOnImage", "inputs": {"image": ["1", 0], "mask": ["4", 0], "color": "255, 0, 0", "device": "gpu"}}
p["6"] = {"class_type": "VHS_VideoCombine", "inputs": {"images": ["5", 0], "frame_rate": 30, "loop_count": 0, "filename_prefix": prefix, "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 20, "save_metadata": False, "trim_to_audio": False, "pingpong": False, "save_output": True}}
body = json.dumps({"prompt": p, "client_id": "ref105-" + uuid.uuid4().hex[:8]}).encode()
req = urllib.request.Request("http://127.0.0.1:6006/prompt", data=body, headers={"Content-Type": "application/json"})
try: print(json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"])
except urllib.error.HTTPError as e: print("HTTP", e.code, e.read().decode()[:2000])
