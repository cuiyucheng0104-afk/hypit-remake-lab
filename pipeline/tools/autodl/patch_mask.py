import json, sys
# 用法: patch_mask.py <基础 prompt.json> <输出.json> <mask 视频名> <输出前缀>
src, dst, mask_video, prefix = sys.argv[1:5]
p = json.load(open(src))
for k in ("557", "558", "383", "384", "400"):
    p.pop(k, None)
p["900"] = {"class_type": "VHS_LoadVideo", "inputs": {"video": mask_video, "force_rate": 30, "custom_width": ["150", 0], "custom_height": ["151", 0], "frame_load_cap": 0, "skip_first_frames": 0, "select_every_nth": 1, "format": "AnimateDiff"}}
p["901"] = {"class_type": "ImageToMask", "inputs": {"image": ["900", 0], "channel": "red"}}
p["390"]["inputs"]["mask"] = ["901", 0]
for k, v in p.items():
    if v["class_type"] == "VHS_VideoCombine": v["inputs"]["filename_prefix"] = prefix
    for a, b in v["inputs"].items():
        if isinstance(b, list) and b[0] in ("557", "558", "383", "384", "400"):
            raise SystemExit(f"dangling link {k}.{a} -> {b[0]}")
json.dump(p, open(dst, "w"), ensure_ascii=False)
print("nodes", len(p), "| mask chain:", p["390"]["inputs"]["mask"], "->", p["401"]["inputs"], "| embeds mask/bg:", p["62"]["inputs"]["mask"], p["62"]["inputs"]["bg_images"])
