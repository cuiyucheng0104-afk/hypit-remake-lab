#!/usr/bin/env python3
"""AutoDL 应用实例管理（开发者 API）。Token 从 ~/.config/autodl/token 读取，脚本不打印它。

用法：
    python3 autodl.py list                    列出应用实例
    python3 autodl.py status   <实例ID>       运行状态
    python3 autodl.py on       <实例ID>       有卡开机（开始计费）
    python3 autodl.py off      <实例ID>       关机（停止 GPU 计费）
    python3 autodl.py wait     <实例ID> <状态> [超时秒]   轮询直到进入指定状态，如 running / shutdown

不提供创建与释放：新建会产生费用，释放会删除实例数据，这两步请在控制台操作。
不提供详情查询：snapshot 接口会返回实例 root 密码，SSH 与面板地址直接用已知的即可。
"""
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

HOST = "https://www.autodl.art"
# 本机 HTTPS 代理的根证书在系统证书库里，python.org 版 Python 自带的证书库不认识它
CA_FILE = os.environ.get("SSL_CERT_FILE") or ("/etc/ssl/cert.pem" if os.path.exists("/etc/ssl/cert.pem") else None)
SSL_CONTEXT = ssl.create_default_context(cafile=CA_FILE)
TOKEN_FILE = os.path.expanduser("~/.config/autodl/token")


def token():
    try:
        value = open(TOKEN_FILE).read().strip()
    except FileNotFoundError:
        sys.exit(f"没有找到 {TOKEN_FILE}，请先在自己的终端保存 Token")
    if not value:
        sys.exit(f"{TOKEN_FILE} 是空的")
    return value


def call(method, path, body):
    # 文档把 GET 参数写成请求体，实测服务端只认查询字符串
    if method == "GET":
        url, data = f"{HOST}{path}?{urllib.parse.urlencode(body)}", None
    else:
        url, data = HOST + path, json.dumps(body).encode()
    request = urllib.request.Request(
        url, method=method, data=data,
        headers={"Authorization": token(), "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30, context=SSL_CONTEXT) as response:
        data = json.load(response)
    if data.get("code") != "Success":
        sys.exit(f"{path} 失败：{data.get('code')} {data.get('msg')}")
    return data.get("data")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    base = "/api/v1/adl_dev/dev/instance/pro"
    if cmd == "list":
        data = call("POST", f"{base}/list", {"page_index": 1, "page_size": 50})
        for item in data.get("list", []):
            app = (item.get("cg_application_info") or {}).get("application_name", "")
            print(f"{item['uuid']}  {item['status']:<10} {item.get('region_name', ''):<8} "
                  f"{item.get('gpu_spec_uuid', '')} x{item.get('req_gpu_amount', '')}  {app}  {item.get('name', '')}")
    elif cmd == "status" and args:
        print(call("GET", f"{base}/status", {"instance_uuid": args[0]}))
    elif cmd == "on" and args:
        call("POST", f"{base}/power_on", {"instance_uuid": args[0], "payload": "gpu"})
        print("已提交开机")
    elif cmd == "off" and args:
        call("POST", f"{base}/power_off", {"instance_uuid": args[0]})
        print("已提交关机")
    elif cmd == "wait" and len(args) >= 2:
        deadline = time.time() + (int(args[2]) if len(args) > 2 else 600)
        while time.time() < deadline:
            state = call("GET", f"{base}/status", {"instance_uuid": args[0]})
            print(time.strftime("%H:%M:%S"), state, flush=True)
            if state == args[1]:
                return
            time.sleep(10)
        sys.exit(f"超时，仍未进入 {args[1]}")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
