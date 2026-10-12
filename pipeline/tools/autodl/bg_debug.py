import json, sys, urllib.request, uuid
video, mask, skip, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
L = lambda v: {"class_type": "VHS_LoadVideo", "inputs": {"video": v, "force_rate": 30, "custom_width": 1280, "custom_height": 624, "frame_load_cap": n, "skip_first_frames": skip, "select_every_nth": 1, "format": "AnimateDiff"}}
p = {"1": L(video), "2": L(mask),
     "3": {"class_type": "ImageToMask", "inputs": {"image": ["2", 0], "channel": "red"}},
     "4": {"class_type": "GrowMask", "inputs": {"mask": ["3", 0], "expand": 10, "tapered_corners": True}},
     "5": {"class_type": "BlockifyMask", "inputs": {"masks": ["4", 0], "block_size": 32, "device": "cpu"}},
     "6": {"class_type": "DrawMaskOnImage", "inputs": {"image": ["1", 0], "mask": ["5", 0], "color": "0", "device": "gpu"}},
     "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": f"ref105/bgdebug_{skip}"}}}
req = urllib.request.Request("http://127.0.0.1:6006/prompt", data=json.dumps({"prompt": p, "client_id": "ref105-" + uuid.uuid4().hex[:8]}).encode(), headers={"Content-Type": "application/json"})
try: print(json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"])
except urllib.error.HTTPError as e: print("HTTP", e.code, e.read().decode()[:1500])
