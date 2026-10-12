import json, sys
p = sys.argv[1]
types = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
w = json.load(open(p, encoding="utf-8"))
nodes = {n["id"]: n for n in w["nodes"]}; links = {l[0]: l for l in w["links"]}
for nid, n in nodes.items():
    if types and n["type"] not in types: continue
    ins = []
    for i in n.get("inputs", []):
        if i.get("link") is not None:
            l = links[i["link"]]; s = nodes.get(l[1])
            extra = " [%s]" % str(s.get("widgets_values"))[:50] if s and s["type"] in ("GetNode", "SetNode") else ""
            ins.append("%s<-%s#%s%s" % (i["name"], s["type"] if s else "?", l[1], extra))
    print(n["id"], n["type"], "| mode", n.get("mode"), "| title:", n.get("title"), "| w:", str(n.get("widgets_values"))[:260])
    if ins: print("     in:", ins)
