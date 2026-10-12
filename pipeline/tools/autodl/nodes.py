import json, sys, urllib.request
kw = [k.lower() for k in sys.argv[1:]]
d = json.load(urllib.request.urlopen("http://127.0.0.1:6006/object_info", timeout=120))
for k, n in d.items():
    if not any(x in k.lower() or x in (n.get("display_name") or "").lower() for x in kw): continue
    req = n["input"].get("required", {}); opt = n["input"].get("optional", {})
    f = lambda v: v[0] if isinstance(v[0], str) else "enum" + str(v[0][:5])
    print("-", k, "|", n.get("display_name"), "| out:", n.get("output"))
    print("     req:", {a: f(b) for a, b in req.items()})
    if opt: print("     opt:", {a: f(b) for a, b in opt.items()})
