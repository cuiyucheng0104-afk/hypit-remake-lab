---
title: 云端ComfyUI · 实例与工作流清单
date: 2026-09-29
tags:
  - AIGC创意工具设计
  - 云端ComfyUI
  - AutoDL
  - Zealman
  - Wan-Animate
  - 影视二创
aliases:
  - Zealman 实例
  - <INSTANCE_ID>
  - K05 影视二创
type: 实测记录
source: 2026-09-29 经 SSH 对实例 <INSTANCE_ID> 的只读勘探（nvidia-smi、df、ps、find、工作流 JSON 解析）；服务器上的 /root/zealman镜像说明.md、/root/工作流说明/*.md
---

# 云端ComfyUI · 实例与工作流清单

> [!abstract] 一句话
> 用户租的这台 AutoDL 实例装的是 **Zealman ComfyUI** 镜像：一张 4090D、模型挂在只读共享盘上，开箱就有 Wan 2.2 Animate、VACE 等换人/动作迁移模型和现成工作流。其中 **K05 影视二创·多人版**只要一张角色图加一段原视频，可以全自动跑，是批量换人的首选。

## 1. 实例

| 项 | 值 | 证据 |
| --- | --- | --- |
| 实例 ID | `<INSTANCE_ID>`，北京 B 区，应用 `zealman-ComfyUI` | 【实测】autodl.py list |
| 显卡 | NVIDIA GeForce RTX 4090 D，24564 MiB，驱动 580.105.08 | 【实测】nvidia-smi |
| CPU / 内存 | 128 核 / 503 GB | 【实测】nproc、free |
| 系统 | Ubuntu 22.04.5 LTS | 【实测】 |
| 系统盘 | overlay 30G，勘探时已用 14G、剩 16G；`/root/autodl-tmp` 在同一块盘上 | 【实测】df |
| 模型存储 | 只读共享盘 `/.autodl-model`（xfs + `AutoFS:cgpublic2`），ComfyUI 的 models 目录链到这里，所以系统盘小也不影响 | 【实测】mount、find -L |
| ComfyUI | `/root/miniconda3/bin/python main.py --port 6006 --listen 127.0.0.1`，由 `/root/zealman-app/start-comfyui.sh` 拉起 | 【实测】ps |
| 控制面板 | 6008 端口，公网地址见 `/root/面板地址.txt` | 【实测】 |
| 网络加速 | `/etc/network_turbo` 存在（AutoDL 学术加速） | 【实测】 |

### 1.1 SSH 登录（密钥，不用密码）

```bash
ssh -i ~/.ssh/autodl_ed25519 -p <SSH_PORT> root@<AUTODL_SSH_HOST>
```

- 密钥 `~/.ssh/autodl_ed25519` 专为这台机器生成，公钥由用户自己用 `ssh-copy-id` 装上（输入一次密码）【实测】。
- 主机指纹 `SHA256:6zkijTPdPT6WfS5rwH9cKmrjcUOEAXfeneFegE8bUbw`。
- root 密码曾在对话中出现过，已建议用户登录后 `passwd` 改掉；本分区任何地方都不记录密码。

## 2. 镜像：Zealman ComfyUI v9.31

镜像自述（【文档】`/root/zealman镜像说明.md`）：

- 运行环境：ComfyUI v0.34.0 + Python 3.12 + PyTorch 2.12.1+cu130 + CUDA 13.0 + cuDNN 9.2，对齐 50 系新卡。
- MiniMax-H3 加速全家桶（Light2V / LightX2V、Kitchen INT8、加速 LoRA、BlockCache / Turbo 等），约 30 套 U 系列工作流开箱即跑；30 多个 `int8_convrot` 加速权重。
- 快捷生成创作台、工作流 API、并发批量生成、ComfyUI 版本自动升降。
- 工作流全部不加密、免费。
- ==禁止基于本镜像二次开发后发布==。自用没问题；如果以后要把我们的流程打包成镜像对外发布，要先看这条。

`/root` 下的其他文件：`zealman-api接口说明.html`（API 文档，即 [[云端ComfyUI · Zealman 工作流 API]] 等三篇的来源）、`工作流说明/`（24 篇）、`Codex镜像功能指引.md`、`开始.html`、`并发/`（并发素材目录）。

## 3. 工作流目录

`/root/工作流说明/` 按字母分类，对应面板里的工作流系列（插件档位按这个字母精简）：

| 系列 | 内容 | 系列 | 内容 |
| --- | --- | --- | --- |
| A / B | 图像-Qwen 生成 / 编辑 | K | ==视频-人物替换== |
| C / D / E | Zimage / Flux / SDXL-IL | L | 视角-高斯泼溅 |
| F | FireRed 图像编辑 | M | 高清放大去水印 |
| G | 视频-Wan 图生 | N | 声音生成、音乐、声音克隆 |
| H | 视频-LTX / LTX2.5 | P | ==视频-动作迁移== |
| J | 视频-对口型数字人 | Q / R / S / T | 分镜图、Ideogram、Boogu、Krea |
| U | 视频-MiniMax-H3 | Y / Z | 通用制作 / 工具设置 |

界面格式的工作流 JSON 在 `/root/ComfyUI/user/default/workflows/<系列目录>/`。

### 3.1 K 系列：人物替换（12 个工作流里与重制相关的）

| 工作流 | 做什么 | 核心模型 |
| --- | --- | --- |
| K01 换装 · Wan 换头换服装换背景娱乐流 | 四个分支：只换头、换服装、**换背景**、整人替换；SAM3 分离人物与背景 | Wan 2.2 Animate 14B FP8、SAM3、DWPose |
| K03 影视二创 · Wan 影视二创 | 单角色影视替换：在某一帧**手动打点**选人，SeC 视频分割跟踪整段，保留原片动作、镜头、时序，合成原音频 | Wan 2.2 Animate 14B FP8、SDPose、ViTPose、YOLOv10、SeC-4B |
| K04 影视二创 · WorkFisher 单人版 | 单人替换，YOLO + ViTPose 定位，RIFE 插帧 | Wan 2.2 Animate 14B FP8 |
| K05 影视二创 · WorkFisher 多人版 | 多人场景：检测多人姿态并保持位置关系，对目标角色做参考图替换，分段窗口处理长序列，RIFE 插帧 | Wan 2.2 Animate 14B FP8 |

以上描述来自 `工作流说明/K视频-人物替换.md`【文档】。

### K05

解析工作流 JSON 的结果【实测】：

| 项 | 值 |
| --- | --- |
| 文件 | `/root/ComfyUI/user/default/workflows/K视频-人物替换/K05-影视二创-WorkFisher多人版.json`，91 个节点 |
| 输入 ① | 节点 **57** `LoadImage` → 字段 `image`：新角色参考图 |
| 输入 ② | 节点 **63** `VHS_LoadVideo` → 字段 `video`：原视频；默认 `force_rate: 16`、`frame_load_cap: 0`（不限帧数） |
| 主干 | `WanVideoModelLoader` → `WanVideoAnimateEmbeds` → `WanVideoSampler` → `WanVideoDecode` → `VHS_VideoCombine` ×2 |
| 姿态 | `YOLOModelLoader`、`OnnxDetectionModelLoader`、`PoseAndFaceDetection`、`SDPoseOOD`、`DrawViTPose` |
| 其他 | `WanVideoClipVisionEncode`、`WanVideoBlockSwap`（显存不够时换块）、`WanVideoLoraSelectMulti`、`WanVideoTorchCompileSettings` |

- **能全自动**：只有这两个输入，不需要手动点选人物。API 调用时写 `"57:image"` 和 `"63:video"`。
- **帧率会变**：`force_rate: 16` 表示原片先重采样到每秒 16 帧再生成，帧数和原片的 30 帧不同。回装脚本 `conform.py` 会把任意帧率统一成 30 帧，并按原段时长变速对齐【源码】；K05 出片的时长是否与原段一致，要实跑确认【空白】。
- **多人时换的是谁**、**背景是否保留原片**：从 JSON 看不出来，要实跑一段才知道【空白】。

### K03

- 86 个节点；比 K05 多了 `PointsEditor`（节点 559，在某一帧上点正负样本点）、`SeCVideoSegmentation`（558）、`SeCModelLoader`（557，`SeC-4B-bf16`）、`GrowMask`、`BlockifyMask`【实测】。
- 视频节点 63 默认 `force_rate: 30`。
- 点选需要看画面，适合在 ComfyUI 界面里操作；用 API 自动跑要先算好点的坐标。

### 3.2 P 系列：动作迁移（节选）

| 工作流 | 做什么 |
| --- | --- |
| P01 Wan 多人姿态迁移最强版（高配 24G） | Wan 2.2 Animate + SAM3 按对象 ID 分割单人或多人，可接 Uni3C 增强原视频运镜 |
| P02 Wan2.2 Animate 角色迁移 | 单张角色图 + 动作视频，重建表演主体 |
| P03 Wan2.2 Animate 循环长视频 V2 | 分批循环处理长视频，上下文窗口保持连续 |
| P04 SCAIL + SDPose + Uni3C 最强全场景 | Wan 2.1 14B SCAIL，支持多人与非人角色，可选运镜控制；示例提示词是「小丑和蝙蝠侠正在对打」 |
| P05 SCAIL 单双人自由切换 | 单人/双人模式切换 |

来源：`工作流说明/P视频-动作迁移.md`【文档】。「动作迁移」与「影视二创」的区别，按 Wan 2.2 Animate 的两种模式理解：前者用角色图**重建整个画面**（背景来自参考），后者在原片里**替换人物**、保留原片画面。这是对照两篇说明得出的读法，还没有实跑验证【空白】。

## 4. 与换人相关的模型文件

`/root/ComfyUI/models/` 下找到的（链接到共享盘）【实测】：

| 目录 | 文件 |
| --- | --- |
| `diffusion_models/Wan/` | `Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ`、`…_fp8_scaled_e4m3fn_KJ_v2`、`Wan2.2-Animate-14B-fp8_v2`、`wan2.2_animate_14B_bf16`、`wan2.2_animate_14B_int8_convrot` |
| `diffusion_models/Wan/` | `wan2.1_vace_14B_fp16`、`Wan2_1-VACE_module_14B_fp8_e4m3fn`、`wan2.1_vace_1.3B_fp16` |
| `diffusion_models/wan-animate2/` | `wan_animate_2_bf16`、`wan_animate_2_int8_convrot`、`wan_animate_2_distill_bf16`、`wan_animate_2_distill_int8_convrot` |
| `loras/` | `Wan/WanAnimate_relight_lora_fp16`、`Lightx2v/lightx2v_elite_it2v_animate_face`、`minimax/viggle_animate_dmd_lora`（及 r64 版） |
| `vae/` | `wan2.2_vae`、`hunyuanvideo15_vae_fp16`、LTX 2.x 与 MiniMax H3 的若干 VAE |

## 原始资料

从服务器 `/root` 复制的原文（2026-09-29）：

- [[zealman镜像说明]]：镜像自述，含版本、功能与「禁止二次开发后发布」
- [[K视频-人物替换]]：K 系列 12 个工作流的说明
- [[P视频-动作迁移]]：P 系列工作流的说明
- [[K05-影视二创-WorkFisher多人版.json]]、[[K03-影视二创-Wan影视二创.json]]：工作流原件（界面格式），可直接拖进 ComfyUI 打开

## 相关

- [[云端ComfyUI · 总览]]
- [[云端ComfyUI · 批量换人方案]]：K05 怎么接 ref105 的九段
- [[灰模管线 · 同类产品与开源方案]]：开源侧的动作控制方案
