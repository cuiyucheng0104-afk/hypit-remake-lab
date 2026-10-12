import json, sys, urllib.request, uuid
# 用法: mask_export.py <video> <prefix> name=prompt:threshold ...   每个 prompt 导出一路黑白遮罩视频
video, prefix = sys.argv[1], sys.argv[2]
p = {
 "1": {"class_type": "VHS_LoadVideo", "inputs": {"video": video, "force_rate": 30, "custom_width": 1280, "custom_height": 624, "frame_load_cap": 0, "skip_first_frames": 0, "select_every_nth": 1, "format": "AnimateDiff"}},
 "2": {"class_type": "easy sam3ModelLoader", "inputs": {"model": "sam3-fp16.safetensors", "segmentor": "image", "device": "cuda", "precision": "fp16"}},
}
for i, spec in enumerate(sys.argv[3:]):
    name, rest = spec.split("=", 1); prompt, thr = rest.rsplit(":", 1)
    b = 10 + i * 3
    p[str(b)] = {"class_type": "easy sam3ImageSegmentation", "inputs": {"sam3_model": ["2", 0], "images": ["1", 0], "prompt": prompt, "threshold": float(thr), "keep_model_loaded": True, "add_background": "none", "detection_limit": -1}}
    p[str(b + 1)] = {"class_type": "MaskToImage", "inputs": {"mask": [str(b), 0]}}
    p[str(b + 2)] = {"class_type": "VHS_VideoCombine", "inputs": {"images": [str(b + 1), 0], "frame_rate": 30, "loop_count": 0, "filename_prefix": f"{prefix}_{name}", "format": "video/h264-mp4", "pix_fmt": "yuv420p", "crf": 0, "save_metadata": False, "trim_to_audio": False, "pingpong": False, "save_output": True}}
body = json.dumps({"prompt": p, "client_id": "ref105-" + uuid.uuid4().hex[:8]}).encode()
req = urllib.request.Request("http://127.0.0.1:6006/prompt", data=body, headers={"Content-Type": "application/json"})
try: print(json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"])
except urllib.error.HTTPError as e: print("HTTP", e.code, e.read().decode()[:2000])
