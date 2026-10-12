import json, sys, urllib.request, uuid
path = sys.argv[1]
p = json.load(open(path))
for k in list(p):
    if p[k]["class_type"] == "ImageBlend" and "image1" not in p[k]["inputs"]:
        p.pop(k)
body = json.dumps({"prompt": p, "client_id": "ref105-" + uuid.uuid4().hex[:8]}).encode()
req = urllib.request.Request("http://127.0.0.1:6006/prompt", data=body, headers={"Content-Type": "application/json"})
try:
    r = json.load(urllib.request.urlopen(req))
    print(json.dumps(r, ensure_ascii=False))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:3000])
