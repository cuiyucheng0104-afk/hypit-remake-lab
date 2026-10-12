import json, sys
p, start = sys.argv[1], int(sys.argv[2]); depth = int(sys.argv[3]) if len(sys.argv) > 3 else 6
w = json.load(open(p, encoding="utf-8"))
nodes = {n["id"]: n for n in w["nodes"]}; links = {l[0]: l for l in w["links"]}
setters = {}
for n in nodes.values():
    if n["type"] == "SetNode": setters[str(n.get("widgets_values", [""])[0])] = n["id"]
seen = set()
def walk(nid, d, pad):
    if nid in seen or d > depth: return
    seen.add(nid); n = nodes[nid]
    print(pad + "%s %s mode=%s w=%s" % (nid, n["type"], n.get("mode"), str(n.get("widgets_values"))[:150]))
    if n["type"] == "GetNode":
        key = str(n.get("widgets_values", [""])[0])
        if key in setters: walk(setters[key], d + 1, pad + "  ")
        return
    for i in n.get("inputs", []):
        if i.get("link") is None: continue
        l = links[i["link"]]
        print(pad + "  <%s>" % i["name"])
        walk(l[1], d + 1, pad + "    ")
walk(start, 0, "")
