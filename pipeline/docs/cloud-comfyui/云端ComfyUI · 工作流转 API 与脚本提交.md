---
title: 云端ComfyUI · 工作流转 API 与脚本提交
date: 2026-09-30
tags:
  - AIGC创意工具设计
  - 云端ComfyUI
  - ComfyUI
  - API
  - 自动化
aliases:
  - graphToPrompt
  - ComfyUI 批跑脚本
  - comfy.py
type: 速查
source: 2026-09-29/30 实操：内置浏览器经 SSH 隧道打开服务器 ComfyUI 转换工作流；trial/comfy.py 等脚本约 150 次提交；服务器日志与进程排查
---

# 云端ComfyUI · 工作流转 API 与脚本提交

> [!abstract] 一句话
> 不经面板的「API 卡片」，直接在浏览器里让 ComfyUI 前端把界面工作流转成 API 格式（`graphToPrompt`），拉回本机用 Python 改参数，经 SSH 隧道提交、轮询、下载。一晚上用这套方法跑了约 150 个任务【实测】。

## 1. 整体流程

```mermaid
flowchart LR
    A["服务器工作流 JSON<br>(界面格式)"] -->|"浏览器：loadGraphData + graphToPrompt"| B["API 格式 JSON<br>存 userdata/ref105/…"]
    B -->|scp| C["本机 workflows/*_api.json"]
    C -->|"Python 改参数、删空槽、补连线"| D["单个任务的 prompt"]
    D -->|"POST /upload/image 素材<br>POST /prompt"| E["ComfyUI 队列"]
    E -->|"GET /history 轮询"| F["GET /view 取成片"]
```

## 2. 转换：界面格式 → API 格式

在内置浏览器打开 `http://127.0.0.1:16006`（隧道），执行：

```js
const app = window.comfyAPI.app.app;
const r = await fetch('/api/userdata/' + encodeURIComponent('workflows/K视频-人物替换/K08-….json'));
await app.loadGraphData(await r.json(), true, true, 'K08_bernini');
const p = await app.graphToPrompt();            // p.output 就是 API 格式
await fetch('/api/userdata/' + encodeURIComponent('ref105/trial/K08_bernini_api.json') + '?overwrite=true',
            {method: 'POST', body: JSON.stringify(p.output)});
```

然后 `scp` 拉回本机。旁路（mode 4）与禁用（mode 2）的节点不会进入输出。

### 只启用某一个分支

K01 有换头、换装、换背景、人物迁移四条分支，存档里只开了换装。按分组的坐标范围改节点 mode 再转换：

```js
for (const n of app.graph._nodes) {
  const [x, y] = n.pos;
  if (y >= 4727 && y <= 7222 && x >= 4900) n.mode = 0;   // 单人换头娱乐区
  else if (y >= 7200) n.mode = 2;                          // 其余分支停用
}
```

## 3. 改参数的常见操作

| 操作 | 例子 |
| --- | --- |
| 换输入素材 | `p["268"]["inputs"]["video"] = upload(clip)`；`p["319"]["inputs"]["image"] = upload(png)` |
| 删空槽 | 同时删掉 LoadImage 节点和它在下游节点上的输入键 |
| 加节点 | `p["900"] = {"class_type": "VHS_LoadVideo", "inputs": {...}}`，再把下游输入指向 `["900", 0]` |
| 选对输出节点 | 取 `save_output=true` 的那个：K08 是 136、P24 是 119、U20 是 92、K01 是 110、Qwen 是 35 |
| 插队 | `POST /prompt` 时带 `"front": true` |

## 4. 脚本

`trial/comfy.py`（副本 [[comfy.py]]）四个函数：

| 函数 | 做什么 |
| --- | --- |
| `upload(path, subfolder)` | multipart 发到 `/upload/image`（也收视频、音频），存 `input/<subfolder>/` |
| `submit(prompt)` | `POST /prompt`，返回 prompt_id；配置错误会当场 HTTP 400 |
| `wait(prompt_id)` | 轮询 `/history/{id}`，`status_str=error` 时抛出节点与报错 |
| `fetch_videos(entry, stem)` | 从 outputs 里取 mp4，经 `/view` 下载 |

批量流水线见 [[pipeline.py]]（`prepare / frames / videos / faceswap / assemble`）、[[chain.sh]]（视频跑完自动换脸、拼接）。

## 5. 踩过的坑

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `FastGroupsBypassSwitch：请在 input1 接口接上相关节点` | 界面里的「二选一」开关靠分组旁路切换，转 API 后另一路没接 | 删掉开关节点，下游直接连到选中的那一路 |
| VHS_LoadVideo 报错 | 视频没有音轨 | 切片时补一条静音音轨（`anullsrc`） |
| 取回的是绿色遮罩预览 | 工作流有多个 VideoCombine，第一个是预览 | 按输出节点 id 取成片 |
| Bernini 帧数报错 / 对不齐 | 帧数要 4n+1；H3 要 17k+5 | 切片时末帧重复补齐，生成后截回原长 |
| 注释用的 CLIPTextEncode 没有 clip 输入 | 只是作者写的提示词说明 | 不在输出路径上无妨；保险起见删掉 |
| 提示音节点 `PlaySound` | 界面用 | 删掉 |
| **任务卡死 30 分钟，GPU 0%，中断无效** | Wan Animate 加载时的 `torch.compile`（inductor）在新帧数下重新编译死锁 | 只能重启 ComfyUI；之后换脸工作流去掉 `compile_args` 和编译设置节点，12 个换脸再没卡过【实测】 |
| 服务器上没有 `python3` | 只有 conda | 用 `/root/miniconda3/bin/python3` |
| 本机 ffmpeg 不能写字 | 编译时没带 drawtext | 对照图用 PIL 贴标签 |

## 6. 重启 ComfyUI

启动脚本 `/root/zealman-app/start-comfyui.sh` 由 init 拉起，没有自动重启；脚本自己会杀掉占 6006 端口的旧进程。脚本是只读符号链接、没有执行权限，要用 bash 调：

```bash
ssh -i ~/.ssh/autodl_ed25519 -p <SSH_PORT> root@<AUTODL_SSH_HOST> \
  'setsid nohup bash /root/zealman-app/start-comfyui.sh > /root/comfy-restart.log 2>&1 < /dev/null &'
```

约 1–2 分钟后 `/queue` 能访问即就绪；正在跑的任务会断开（客户端收到 `Connection reset by peer`）。

## 7. 观察运行状态

- 日志：`/root/ComfyUI/user/comfyui_6006.log`（`Sampling start`、`N frames at WxH`、`Bernini: attached N context streams`）
- 显卡：`nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader`
- 队列：`GET /queue` 的 `queue_running` / `queue_pending`

## 8. 实测耗时（4090D，960×480）

| 任务 | 耗时 |
| --- | --- |
| Qwen-Image-Edit 2511 首帧精修（4 步） | 约 17 秒/张 |
| Bernini rv2v（4+4 步，17–61 帧） | 约 2.5–4 分钟/镜头（含首次加载模型约 2 分钟） |
| Bernini + cfg_chain | 约 3.4 倍 |
| K01 换头（关编译后） | 1–2 分钟/镜头；带编译的首个 4 分钟 |
| SCAIL-2 替换 | 约 8–10 分钟/镜头 |
| H3 打斗（双采 + LoRA） | 15–18 分钟/镜头 |

## 相关

- [[云端ComfyUI · Zealman 工作流 API]]（面板的另一条路：API 卡片）
- [[云端ComfyUI · 工作流全目录解读]] · [[云端ComfyUI · ref105 三路线对照试验]] · [[云端ComfyUI · 首帧精修与 Bernini 全片重制]]
- [[Hypit · 自有 H3 Provider 接入]]（同样的 ComfyUI 接口，包成 Hypit provider）
