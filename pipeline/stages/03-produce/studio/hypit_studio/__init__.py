"""Hypit Studio：给不会用节点的同事用的画布网页，挂在 ComfyUI 自己的端口上（/studio）。

- 网页只调用这里的 /studio/api/*；任务照常进 ComfyUI 队列，和节点界面的人共用一张显卡、按先后排队。
- 素材上传、结果预览直接用 ComfyUI 自带的 /upload/image 和 /view。
- 画布存在 ComfyUI/user/studio/canvases/<名字>.json，谁打开都是同一份。
- 测试阶段不做登录（用户要求，之后自己加）；每次提交记一行到 ComfyUI/user/studio/jobs.jsonl。
"""
import json
import logging
import os
import re
import shutil
import time

import aiohttp
from aiohttp import web

import folder_paths
from comfy.cli_args import args
from server import PromptServer

from . import graphs

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
DATA_DIR = os.path.join(folder_paths.get_user_directory(), "studio")
CANVAS_DIR = os.path.join(DATA_DIR, "canvases")
JOB_LOG = os.path.join(DATA_DIR, "jobs.jsonl")
os.makedirs(CANVAS_DIR, exist_ok=True)

LORA_GROUPS = [("minimax/", "action", "动作·打斗·文戏"), ("research_nsfw/", "research", "研究用（成人内容）")]

routes = PromptServer.instance.routes


def _base():
    return f"http://127.0.0.1:{args.port}"


def _loras():
    out = []
    for name in folder_paths.get_filename_list("loras"):
        if name in graphs.TURBO_FILES:
            continue
        norm = name.replace("\\", "/")
        gid, glabel = next(((g, l) for prefix, g, l in LORA_GROUPS if norm.startswith(prefix)), ("other", "其他"))
        family = "qwen" if "qwen" in norm.lower() else "h3"
        out.append({"name": name, "label": os.path.splitext(os.path.basename(norm))[0],
                    "group": gid, "group_label": glabel, "family": family})
    return out


def _canvas_path(name):
    safe = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "默认画布"
    return os.path.join(CANVAS_DIR, safe[:80] + ".json")


@routes.get("/studio")
async def studio_page(request):
    return web.FileResponse(os.path.join(WEB_DIR, "index.html"), headers={"Cache-Control": "no-cache"})


@routes.get("/studio/api/options")
async def studio_options(request):
    import nodes
    return web.json_response({"loras": _loras(), "aspects": list(graphs.ASPECTS),
                              "rtx_sr": "RTXVideoSuperResolution" in nodes.NODE_CLASS_MAPPINGS,
                              "fast_omni": graphs.FAST_OMNI_UNET in folder_paths.get_filename_list("diffusion_models")})


FILE_KEYS = ("first_frame", "last_frame", "source_video", "ref_images", "ref_videos", "ref_audios")


def _to_input(ref):
    """画布上的生成结果以 "output/<子目录>/<文件名>" 引用；ComfyUI 的加载节点只读 input 目录，所以先复制过去。"""
    if not isinstance(ref, str) or not ref.startswith("output/"):
        return ref
    rel = os.path.normpath(ref[len("output/"):])
    src = os.path.join(folder_paths.get_output_directory(), rel)
    if rel.startswith("..") or not os.path.isfile(src):
        raise ValueError(f"找不到生成结果：{ref}")
    name = "studio_" + rel.replace(os.sep, "_")
    dst = os.path.join(folder_paths.get_input_directory(), name)
    if not os.path.exists(dst):
        shutil.copyfile(src, dst)
    return name


def _resolve_files(p):
    for k in FILE_KEYS:
        if isinstance(p.get(k), list):
            p[k] = [_to_input(x) for x in p[k]]
        elif p.get(k):
            p[k] = _to_input(p[k])
    for kf in p.get("keyframes") or []:
        kf["image"] = _to_input(kf.get("image"))


@routes.post("/studio/api/submit")
async def studio_submit(request):
    p = await request.json()
    try:
        _resolve_files(p)
        prompt, meta = graphs.build(p, set(folder_paths.get_filename_list("loras")))
    except ValueError as e:
        return web.json_response({"error": str(e)}, status=400)
    async with aiohttp.ClientSession() as s:
        async with s.post(_base() + "/prompt", json={"prompt": prompt, "client_id": p.get("client_id") or "hypit-studio"}) as r:
            body = await r.json(content_type=None)
            if r.status != 200:
                logging.warning("studio submit rejected: %s", json.dumps(body, ensure_ascii=False)[:2000])
                return web.json_response({"error": "ComfyUI 拒绝了这个任务", "detail": body}, status=400)
    pid = body["prompt_id"]
    rec = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "ip": request.remote, "prompt_id": pid,
           "mode": p.get("mode"), "params": {k: v for k, v in p.items() if k not in ("mode", "client_id")}, **meta}
    with open(JOB_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return web.json_response({"prompt_id": pid, **meta})


def _outputs(hist):
    files = []
    for out in (hist.get("outputs") or {}).values():
        for key in ("images", "gifs", "3d", "video"):
            for f in out.get(key) or []:
                if isinstance(f, dict) and f.get("filename") and f.get("type") == "output":
                    files.append({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": "output"})
    return files


@routes.get("/studio/api/job/{pid}")
async def studio_job(request):
    pid = request.match_info["pid"]
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{_base()}/history/{pid}") as r:
            hist = (await r.json()).get(pid)
        if hist:
            st = hist.get("status") or {}
            err = next((m[1].get("exception_message") for m in st.get("messages", []) if m[0] == "execution_error"), None)
            return web.json_response({"state": "error" if err else "done", "error": err, "files": _outputs(hist)})
        async with s.get(f"{_base()}/queue") as r:
            q = await r.json()
    running = q.get("queue_running", [])
    if any(item[1] == pid for item in running):
        return web.json_response({"state": "running"})
    pending = sorted(q.get("queue_pending", []), key=lambda item: item[0])
    for i, item in enumerate(pending):
        if item[1] == pid:
            return web.json_response({"state": "queued", "ahead": i + len(running)})
    return web.json_response({"state": "unknown"})


@routes.get("/studio/api/canvases")
async def studio_canvases(request):
    names = sorted((os.path.splitext(f)[0] for f in os.listdir(CANVAS_DIR) if f.endswith(".json")),
                   key=lambda n: -os.path.getmtime(_canvas_path(n)))
    return web.json_response(names)


@routes.get("/studio/api/canvas/{name}")
async def studio_canvas_get(request):
    path = _canvas_path(request.match_info["name"])
    if not os.path.exists(path):
        return web.json_response(None)
    with open(path, encoding="utf-8") as f:
        return web.json_response(json.load(f))


@routes.put("/studio/api/canvas/{name}")
async def studio_canvas_put(request):
    data = await request.json()
    path = _canvas_path(request.match_info["name"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)
    return web.json_response({"ok": True})


@routes.get("/studio/api/jobs")
async def studio_jobs(request):
    rows = []
    if os.path.exists(JOB_LOG):
        with open(JOB_LOG, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()][-100:]
    return web.json_response(list(reversed(rows)))


NODE_CLASS_MAPPINGS = {}
