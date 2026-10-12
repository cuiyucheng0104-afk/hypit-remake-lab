"""假 AutoDL 市场：模拟 查价格 / 提交 / 查结果 / 下载成片 四个接口，记录收到的提交体（不含 base64 正文）。"""
import json, sys, pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = pathlib.Path(__file__).resolve().parent
SAMPLE = pathlib.Path(sys.argv[1])          # 用作「生成结果」的样片（6 秒，用来测截时长）
BILLING = [{"resolution": "480p", "price": 40, "off_peak_price": 30}, {"resolution": "768p", "price": 70, "off_peak_price": 50},
           {"resolution": "1088p", "price": 70, "off_peak_price": 50}, {"resolution": "1440p", "price": 80, "off_peak_price": 60}]
polls = {}

class H(BaseHTTPRequestHandler):
    def reply(self, data, code=200, raw=None, ctype="application/json"):
        body = raw if raw is not None else json.dumps({"code": "Success", "data": data}).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def log_message(self, *a): pass
    def do_GET(self):
        p = self.path
        if p.startswith("/api/v1/comfyui/workflows/"):
            return self.reply({"billing_config": {"minimax_h3": BILLING}})
        if p.startswith("/api/v1/comfyui/comfyui_workflow/result/"):
            t = p.rsplit("/", 1)[1]; polls[t] = polls.get(t, 0) + 1
            if polls[t] < 2: return self.reply({"status": "running", "task_id": t})
            return self.reply({"status": "completed", "task_id": t, "results": [{"url": f"http://127.0.0.1:18777/out/{t}.mp4", "type": "video"}]})
        if p.startswith("/out/"):
            return self.reply(None, raw=SAMPLE.read_bytes(), ctype="video/mp4")
        self.reply({}, 404)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        summary = {k: (f"<{v.split(';')[0]} {len(v)} chars>" if isinstance(v, str) and v.startswith("data:") else v) for k, v in body.items()}
        summary["_workflow"] = self.path.rsplit("/", 1)[1]
        summary["_auth_is_fake_token"] = self.headers.get("Authorization") == "FAKE-TOKEN"
        with open(HERE / "received.jsonl", "a") as f: f.write(json.dumps(summary, ensure_ascii=False) + "\n")
        self.reply({"task_id": f"fake-{len(open(HERE / 'received.jsonl').readlines())}"})

ThreadingHTTPServer(("127.0.0.1", 18777), H).serve_forever()
