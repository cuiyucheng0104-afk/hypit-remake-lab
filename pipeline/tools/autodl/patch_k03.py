import json, sys
src, dst, video, ref, prefix = sys.argv[1:6]
pos, neg = sys.argv[6], sys.argv[7]
width, height = int(sys.argv[8]), int(sys.argv[9])
p = json.load(open(src))
def summary():
    for k, v in sorted(p.items(), key=lambda x: int(x[0])):
        ins = {a: b for a, b in v["inputs"].items() if not isinstance(b, list)}
        links = {a: b for a, b in v["inputs"].items() if isinstance(b, list)}
        print(k, v["class_type"], str(ins)[:140], "| links:", {a: b[0] for a, b in links.items()})
p["558"]["inputs"]["positive_points"] = pos
p["558"]["inputs"]["negative_points"] = neg
p.pop("559", None)
for k in list(p):
    if any(isinstance(b, list) and b[0] == "559" for b in p[k]["inputs"].values()) and p[k]["class_type"] in ("PreviewImage", "MaskPreview", "PreviewAny"):
        p.pop(k)
for k in list(p):
    for a, b in list(p[k]["inputs"].items()):
        if isinstance(b, list) and b[0] == "559": raise SystemExit("still linked to 559: %s.%s" % (k, a))
assert "391" in p and "401" in p, "mask/bg nodes missing"
p["62"]["inputs"]["bg_images"] = ["391", 0]
p["62"]["inputs"]["mask"] = ["401", 0]
p["57"]["inputs"]["image"] = ref
p["63"]["inputs"]["video"] = video
p["63"]["inputs"]["force_rate"] = 30
p["150"]["inputs"]["value"] = width
p["151"]["inputs"]["value"] = height
if "244" in p: p["244"]["inputs"]["value"] = 30
for k, v in p.items():
    if v["class_type"] == "VHS_VideoCombine": v["inputs"]["filename_prefix"] = prefix
json.dump(p, open(dst, "w"), ensure_ascii=False)
summary()
