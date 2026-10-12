"""ref105 路线对照试验：经本机 SSH 隧道（127.0.0.1:16006）向服务器 ComfyUI 上传素材、提交、等待、取回成片。"""
import json, time, pathlib, urllib.request, urllib.parse, uuid

BASE = "http://127.0.0.1:16006"
ROOT = pathlib.Path(__file__).resolve().parent
CHARS = ROOT.parent / "export" / "characters"


def call(path, data=None, headers=None, timeout=300):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def upload(path, subfolder="ref105trial"):
    """ComfyUI 的 /upload/image 也收视频和音频，存进 input/<subfolder>/。"""
    path = pathlib.Path(path)
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("type", "input"), ("subfolder", subfolder), ("overwrite", "true")):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{path.name}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    result = json.loads(call("/upload/image", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}))
    return f"{result['subfolder']}/{result['name']}" if result.get("subfolder") else result["name"]


def submit(prompt):
    body = json.dumps({"prompt": prompt, "client_id": "ref105-trial"}).encode()
    try:
        result = json.loads(call("/prompt", body, {"Content-Type": "application/json"}))
    except urllib.error.HTTPError as error:
        raise SystemExit(f"HTTP {error.code}: {error.read().decode()[:3000]}")
    return result["prompt_id"]


def wait(prompt_id, poll=10):
    while True:
        history = json.loads(call(f"/history/{prompt_id}"))
        entry = history.get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                messages = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise SystemExit(f"FAILED {prompt_id}: {json.dumps(messages, ensure_ascii=False)[:2000]}")
            if status.get("completed"):
                return entry
        time.sleep(poll)


def fetch_videos(entry, dest_stem):
    saved = []
    for node_id, output in entry.get("outputs", {}).items():
        for item in output.get("gifs", []) + output.get("images", []) + output.get("videos", []):
            name = item.get("filename", "")
            if not name.endswith((".mp4", ".webm", ".mov")):
                continue
            query = urllib.parse.urlencode({"filename": name, "subfolder": item.get("subfolder", ""), "type": item.get("type", "output")})
            target = ROOT / "out" / f"{dest_stem}_n{node_id}.mp4"
            target.write_bytes(call(f"/view?{query}", timeout=600))
            saved.append(str(target))
    return saved
