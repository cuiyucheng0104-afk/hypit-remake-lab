import json, glob, os, sys
base = "/root/ComfyUI/user/default/workflows"
pats = sys.argv[1:] or ["K视频-人物替换/K05*", "K视频-人物替换/K03*", "K视频-人物替换/K01*", "**/*P07*"]
seen = set()
for pat in pats:
    for p in glob.glob(os.path.join(base, pat), recursive=True):
        if p in seen: continue
        seen.add(p)
        w = json.load(open(p, encoding="utf-8"))
        nodes = {n["id"]: n for n in w.get("nodes", [])}
        links = {l[0]: l for l in w.get("links", [])}
        print("=====", os.path.relpath(p, base), "nodes", len(nodes))
        for n in nodes.values():
            if n["type"] == "WanVideoAnimateEmbeds":
                conn = []
                for i in n.get("inputs", []):
                    if i.get("link") is not None:
                        l = links.get(i["link"]); src = nodes.get(l[1]) if l else None
                        conn.append("%s<-%s" % (i["name"], src["type"] if src else "?"))
                print("  AnimateEmbeds", n["id"], "mode", n.get("mode"), conn, "| w:", n.get("widgets_values"))
        for n in nodes.values():
            if n["type"] in ("WanVideoModelLoader", "VHS_VideoCombine", "ImageResizeKJv2", "WanVideoSampler", "LoadImage", "VHS_LoadVideo"):
                print("   ", n["type"], n["id"], "mode", n.get("mode"), str(n.get("widgets_values"))[:170])
