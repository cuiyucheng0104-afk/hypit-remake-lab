"""AutoDL.Art ComfyUI 工作流市场 API（托管运行，按次/按秒计费）。

Token 读 ~/.config/autodl/comfy_token（令牌管理里 ComfyUI 分组的令牌）；脚本不打印 Token。
usage:
  autodl_comfy.py info <workflow_id>                 只读：工作流详情与输入规则（不计费）
  autodl_comfy.py submit <workflow_id> <body.json>   提交（计费）；body 里的本地文件路径写成 "@/path/to/file"，自动转 base64
  autodl_comfy.py result <task_id> [--wait] [--out 目录]  查询/等待结果并下载
"""
import base64, json, mimetypes, os, ssl, sys, time, urllib.error, urllib.request

BASE = "https://www.autodl.art/api/v1/comfyui"
CA_FILE = os.environ.get("SSL_CERT_FILE") or ("/etc/ssl/cert.pem" if os.path.exists("/etc/ssl/cert.pem") else None)
SSL_CONTEXT = ssl.create_default_context(cafile=CA_FILE)
TOKEN_FILES = [os.path.expanduser("~/.config/autodl/comfy_token")]  # 市场令牌；~/.config/autodl/token 是实例管理令牌，不能混用


def token():
    for path in TOKEN_FILES:
        if os.path.exists(path) and open(path).read().strip():
            return open(path).read().strip()
    sys.exit("没有找到 Token 文件，请先在自己的终端保存到 ~/.config/autodl/comfy_token")


def call(method, path, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CONTEXT) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as error:
        return {"http_status": error.code, "body": error.read().decode()[:2000]}


def inline(value):
    """"@/本地路径" → data URL（base64）。"""
    if isinstance(value, str) and value.startswith("@"):
        path = value[1:]
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()
    return value


def download(url, out_dir, name):
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, name)
    with urllib.request.urlopen(url, timeout=600, context=SSL_CONTEXT) as r, open(target, "wb") as f:
        f.write(r.read())
    return target


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "info":
        print(json.dumps(call("GET", f"/workflows/{sys.argv[2]}"), ensure_ascii=False, indent=1)[:12000])
    elif cmd == "submit":
        body = {k: inline(v) for k, v in json.load(open(sys.argv[3])).items()}
        print(json.dumps(call("POST", f"/comfyui_workflow/{sys.argv[2]}", body), ensure_ascii=False))
    elif cmd == "result":
        task = sys.argv[2]
        out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
        while True:
            r = call("GET", f"/comfyui_workflow/result/{task}")
            state = str((r.get("data") or {}).get("status", "")).lower()
            if "--wait" not in sys.argv or "http_status" in r or state in ("completed", "success", "failed", "error", "cancelled"):
                break
            time.sleep(5)
        print(json.dumps(r, ensure_ascii=False)[:3000])
        if state in ("completed", "success"):
            results = (r.get("data") or {}).get("results") or []
            for i, url in enumerate(results):
                url = url if isinstance(url, str) else url.get("url")
                print("downloaded", download(url, out, f"{task}_{i}{os.path.splitext(url.split('?')[0])[1] or '.mp4'}"))
