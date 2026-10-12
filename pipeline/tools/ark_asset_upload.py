#!/usr/bin/env python3
"""把本地图片录入火山方舟私域素材库（AIGC 虚拟人像），拿到 Seedance 可用的 asset:// 引用。

流程：ListAssetGroups 找同名组（没有就 CreateAssetGroup）→ 临时把图片挂到公网 →
CreateAsset 逐张提交 → GetAsset 轮询到 Active / Failed → 关闭公网入口 → 写清单。

用法：
    python3 ark_asset_upload.py --group "ref105重制·角色" --desc "武侠短片角色" \\
        主角=/path/hero.jpg 反派头目=/path/villain.jpg

    --base-url https://cdn.example.com/dir   图片已在公网时直接用，不开隧道（URL = base-url/文件名）
    --project default                          方舟项目名
    --out <file.json>                          清单路径（默认 ~/hypit-projects/assets-registry/<组名>.json）

依赖：已登录的 `ve` CLI（`arkcli auth login volc-sso` 会顺带登录）；未传 --base-url 时需要 ngrok。
公网入口只暴露一个随机路径下的这几张图，根路径返回空页，素材处理完即关闭并删除临时目录。
"""
import argparse
import functools
import http.server
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time

VERSION = "2024-01-01"
NO_PROXY_ENV = {k: v for k, v in os.environ.items()
                if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}


def ve(action, body):
    """调用方舟 OpenAPI；ve 负责签名与 SSO 凭证续期。"""
    out = subprocess.run(
        ["ve", "ark", action, "--force", "--version", VERSION, "--method", "POST",
         "--body", json.dumps(body, ensure_ascii=False)],
        capture_output=True, text=True,
    )
    text = (out.stdout or "") + (out.stderr or "")
    try:
        data = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"{action} 失败：{text.strip()[:400]}")
    error = data.get("ResponseMetadata", {}).get("Error")
    if error:
        raise RuntimeError(f"{action} 失败：{error.get('Code')} {error.get('Message')}")
    return data.get("Result", {})


def find_or_create_group(name, desc, project):
    found = ve("ListAssetGroups", {"Filter": {"GroupType": "AIGC", "Name": name},
                                   "PageNumber": 1, "PageSize": 50, "ProjectName": project})
    for group in found.get("Items", []):
        if group.get("Name") == name:
            return group["Id"], False
    created = ve("CreateAssetGroup", {"Name": name, "Description": desc,
                                      "GroupType": "AIGC", "ProjectName": project})
    return created.get("Id") or created.get("GroupId"), True


class Tunnel:
    """本地只读 HTTP 服务 + ngrok，只暴露随机路径下的文件。"""

    def __init__(self, files):
        self.root = tempfile.mkdtemp(prefix="ark-asset-")
        self.token = secrets.token_urlsafe(18)
        os.makedirs(os.path.join(self.root, self.token))
        open(os.path.join(self.root, "index.html"), "w").close()
        self.names = {}
        for label, path in files:
            ext = os.path.splitext(path)[1].lower() or ".jpg"
            name = f"{secrets.token_hex(4)}{ext}"
            shutil.copy(path, os.path.join(self.root, self.token, name))
            self.names[label] = name
        handler = functools.partial(QuietHandler, directory=self.root)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        port = self.httpd.server_address[1]
        self.ngrok = subprocess.Popen(
            ["ngrok", "http", f"127.0.0.1:{port}", "--log", "stdout", "--log-format", "logfmt"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=NO_PROXY_ENV,
        )
        self.base = self._wait_url()

    def _wait_url(self, timeout=30):
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.ngrok.stdout.readline()
            if not line:
                if self.ngrok.poll() is not None:
                    break
                continue
            if "lvl=eror" in line or "lvl=crit" in line:
                self.close()
                raise RuntimeError(f"ngrok 启动失败：{line.strip()[:300]}")
            match = re.search(r"url=(https://\S+)", line)
            if match:
                return match.group(1)
        self.close()
        raise RuntimeError("ngrok 没有在 30 秒内给出公网地址")

    def url(self, label):
        return f"{self.base}/{self.token}/{self.names[label]}"

    def close(self):
        if getattr(self, "ngrok", None) and self.ngrok.poll() is None:
            self.ngrok.terminate()
            try:
                self.ngrok.wait(5)
            except subprocess.TimeoutExpired:
                self.ngrok.kill()
        if getattr(self, "httpd", None):
            self.httpd.shutdown()
        shutil.rmtree(self.root, ignore_errors=True)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def list_directory(self, path):
        self.send_error(404)

    def log_message(self, fmt, *args):
        pass


def wait_assets(ids, project, timeout=600, every=4):
    status = {i: {"Status": "Processing"} for i in ids}
    deadline = time.time() + timeout
    while time.time() < deadline:
        pending = [i for i, s in status.items() if s.get("Status") not in ("Active", "Failed")]
        if not pending:
            break
        for asset_id in pending:
            status[asset_id] = ve("GetAsset", {"Id": asset_id, "ProjectName": project})
        time.sleep(every)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", required=True)
    parser.add_argument("--desc", default="")
    parser.add_argument("--project", default="default")
    parser.add_argument("--base-url")
    parser.add_argument("--out")
    parser.add_argument("images", nargs="+", help="名称=本地路径")
    args = parser.parse_args()

    files = []
    for item in args.images:
        label, sep, path = item.partition("=")
        if not sep or not os.path.isfile(os.path.expanduser(path)):
            sys.exit(f"参数应为 名称=存在的文件路径：{item}")
        files.append((label, os.path.expanduser(path)))

    group_id, created = find_or_create_group(args.group, args.desc, args.project)
    print(f"素材组 {args.group} → {group_id}（{'新建' if created else '已存在，复用'}）")

    tunnel = None
    try:
        if args.base_url:
            urls = {label: f"{args.base_url.rstrip('/')}/{os.path.basename(path)}" for label, path in files}
        else:
            tunnel = Tunnel(files)
            urls = {label: tunnel.url(label) for label, _ in files}
            print("临时公网入口已开启（处理完即关闭）")
        submitted = {}
        for label, path in files:
            result = ve("CreateAsset", {"GroupId": group_id, "Name": label, "AssetType": "Image",
                                        "URL": urls[label], "ProjectName": args.project})
            asset_id = result.get("Id") or result.get("AssetId")
            submitted[asset_id] = (label, path)
            print(f"  已提交 {label} → {asset_id}")
        status = wait_assets(list(submitted), args.project)
    finally:
        if tunnel:
            tunnel.close()
            print("临时公网入口已关闭")

    records = []
    for asset_id, (label, path) in submitted.items():
        info = status.get(asset_id, {})
        records.append({"name": label, "file": path, "asset_id": asset_id,
                        "ref": f"asset://{asset_id}", "status": info.get("Status"),
                        "group": args.group, "group_id": group_id, "project": args.project,
                        "detail": {k: v for k, v in info.items() if k not in ("URL",)}})
    out = args.out or os.path.expanduser(f"~/hypit-projects/assets-registry/{args.group}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    previous = json.load(open(out)) if os.path.exists(out) else []
    keep = [r for r in previous if r["asset_id"] not in submitted]
    json.dump(keep + records, open(out, "w"), ensure_ascii=False, indent=1)

    print(f"\n{'名称':<8}{'状态':<11}引用")
    for r in records:
        print(f"{r['name']:<8}{str(r['status']):<11}{r['ref']}")
    print(f"清单：{out}")
    if any(r["status"] != "Active" for r in records):
        sys.exit(1)


if __name__ == "__main__":
    main()
