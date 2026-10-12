import json, sys
src, dst, ref, prefix, prompt = sys.argv[1:6]
relight = float(sys.argv[6]) if len(sys.argv) > 6 else 0.5
pose_thr = float(sys.argv[7]) if len(sys.argv) > 7 else 0.2
p = json.load(open(src))
p["57"]["inputs"]["image"] = ref
p["64"]["inputs"]["keep_proportion"] = "pad"
p["64"]["inputs"]["pad_color"] = "255, 255, 255"
p["65"]["inputs"]["positive_prompt"] = prompt
lora = p["467"]["inputs"]
for k, v in list(lora.items()):
    if k.startswith("lora_") and isinstance(v, str) and "relight" in v.lower():
        lora["strength_" + k.split("_")[1]] = relight
p["552"]["inputs"]["score_threshold"] = pose_thr
for v in p.values():
    if v["class_type"] == "VHS_VideoCombine": v["inputs"]["filename_prefix"] = prefix
json.dump(p, open(dst, "w"), ensure_ascii=False)
print({k: v for k, v in lora.items() if k.startswith(("lora_", "strength_"))})
