---
title: 云端ComfyUI · 工作流全目录解读
date: 2026-09-30
tags:
  - AIGC创意工具设计
  - 云端ComfyUI
  - ComfyUI
  - 工作流
  - Bernini
  - SCAIL-2
  - Wan-Animate
aliases:
  - Zealman 工作流目录
  - 服务器工作流清单
type: 实测记录
source: 2026-09-30 对实例 /root/ComfyUI/user/default/workflows 全部 22 个分类的遍历；逐个解析 K、P、U 系列 JSON 的节点类型、模型文件与作者备注；/object_info 节点定义；模型文件存在性核对
---

# 云端ComfyUI · 工作流全目录解读

> [!abstract] 一句话
> 服务器上约 250 个工作流、22 个分类。和「保留动作、换人换景」直接相关的是四套底层技术：**Wan2.2 Animate**（骨架驱动）、**SCAIL-2**（多人追踪 + 颜色绑定身份）、**Bernini**（视频编辑模型，以原片为底）、**H3 打斗**（按参考重拍）。它们用到的模型文件全部已在服务器上【实测】。

## 1. 全部分类

**图像类**（出定妆照、改关键帧、做分镜）

| 分类 | 做什么 | 值得记住的 |
| --- | --- | --- |
| A 图像-Qwen生成 | Qwen-Image 2512 文生图、洗图、ControlNet | A06 按线稿/姿态出图 |
| B 图像-Qwen编辑 | Qwen-Image-Edit 2509/2511 单图与多图编辑 | B03 单双三图编辑；B05/B08/B13 多角度；B06 极限姿态；B07 换脸；B16 多图出 4/9/25 宫格分镜 |
| C 图像-Zimage | Z-Image 写实文生图、洗图 | C19 人物三视图；C16 短剧场景 + 角色 |
| D 图像-Flux | Flux1、Kontext、Flux2 Klein 9B 多图编辑 | D17/D21 自动换脸（BFS 换脸 LoRA）；D19 一致换装；D04 修手 |
| E / R / S / T | SDXL 二次元、Ideogram（能写字）、Boogu、Krea2 写实 | T10 做剧四视图 |
| F FireRed | 图像编辑 | F02 人物换背景 |
| Q 分镜图 | gptimage / banana2 | 看名字是调云端接口，未核实【空白】 |
| Y 通用制作 | 上面几家编辑模型的精简版 | Y01 千问 2511 单图编辑（本项目首帧精修的底座）；Y06 改为下一个场景图 |

**视频生成类**

| 分类 | 做什么 |
| --- | --- |
| G 视频-Wan图生 | Wan2.2 图生视频、首尾帧、长视频（G09 多分镜、G11/G17 无限续播）；G27 与 K07 同一个 |
| H 视频-LTX | LTX 2.3/2.5（带声音）；「导演台」多分镜控制、首尾帧、多图参考 |
| U 视频-H3 | MiniMax H3 全家：U02 图生、U03 文生、U17 9 图 1 视频 3 音频、U20/U24 打斗 |

**数字人与后期**

| 分类 | 做什么 |
| --- | --- |
| J 对口型数字人 | InfiniteTalk（图或视频驱动，可长视频）、LTX 数字人；J14 Bernini 换商品 |
| L 高斯泼溅 | 单图转 3D 换视角 |
| M 高清放大去水印 | SeedVR2、FlashVSR 视频超分（M05、M15）、ProPainter 去水印（M06）、LTX 去字幕（M09、M19） |
| N 声音 | FishAudio 声音克隆、MMAudio 看画面生成音效（N04）、ACE-Step 音乐（N05）、Qwen3-TTS |

## 2. 换人 / 动作的四套技术

### 2.1 Wan2.2 Animate 系（K01–K07、P02、P07–P20、P29）

- **原理**：从原片抽骨架（DWPose / SDPose）和脸部关键点，按参考图重画人物。替换模式需要人物遮罩（SeC 打点跟踪、SAM3 文字分割），只重画遮罩内；迁移模式整幅重画。
- **在 ref105 S01 的实际问题**（09-29）：骨架里没有剑；快动作拖影时骨架抽不准；多人遮挡分不清谁是谁；跨剪辑点跟丢；遮罩一漏就出现袍子没重画、双脸。
- **适合**：单人、动作清楚、不切镜头的素材（舞蹈、口播）。
- **K01 的「单人换头」分支**：SAM3 以「Head」追踪头部 → 遮罩 → Wan Animate 替换模式只重画头部，表情由 DWPose 脸部裁切驱动。这是本项目后来的**换脸**手段（见 [[云端ComfyUI · 首帧精修与 Bernini 全片重制]]）。

### 2.2 SCAIL-2 系（K10、K11、K13、P24–P28）

- **模型**：Wan2.1 14B SCAIL-2（fp8 / int8 / nvfp4），配 DPO LoRA、补光 LoRA。
- **多人身份怎么对上**：SAM3.1 在视频里追踪每个人，`SCAIL2ColoredMaskV2` 按从左到右（或面积）给每人一种颜色；参考图要做成「拼贴」（`ManualRefCollage`，每个角色一个抠像），拼贴里的人也按同一顺序上色——颜色一一对应，一次生成就能换多个人。
- **两种模式**：`replacement_mode=true` 保留原场景与其他人，只换被追踪的人；false 为动画模式，可给 `bg_image` 换背景，但背景是静止图，原片机位运动会丢。
- **适合**：1–4 人的镜头；十几人的群战要逐个对位，不现实。

### 2.3 Bernini（K08、K09）

- **模型**：Wan2.2 Bernini（HIGH / LOW 两个 fp8 文件）。节点 `WanAnimatePlus Bernini` 的输入：`source_video`（编辑底）、`reference_video`、`reference_image_1…10`。
- **任务类型**：节点只有 `t2v / v2v / r2v / rv2v` 四项，系统提示词可写成更多任务：

| task / 系统提示 | 作用 |
| --- | --- |
| `rv2v` · video editing with reference | 以原片为底，按参考图改人物/环境（本项目主力） |
| `vi2v` · video editing on content propagation | 第一帧改好，把改动传播到整段 |
| `mv2v` · 全参数编辑 | 风格、光影、材质、姿态都可改 |
| `r2v` / `i2v` / `t2v` | 常规参考生成、图生、文生 |

- **引导方式**（节点描述里的推荐）：rv2v 用 `cfg_chain`，`chain_omega_V=1.25`（跟原片）、`chain_omega_I=4.5`（跟参考图）、`chain_omega_TI=4.0`（跟文字）。源码里 cfg_chain 每步多做 3 次前向，与 cfg 数值无关；K08 默认 cfg=1 + 4 步 lightx2v 加速 LoRA，此时参考引导很弱。
- **为什么最有希望**：它读的是原视频本身而不是骨架，剑、水花、机位、遮挡原则上都保留。它是本地版的 Seedance 2.5 编辑模式，且不经平台审核。实测结论见 [[云端ComfyUI · ref105 三路线对照试验]]。

### 2.4 H3 打斗（U20、U24）

- H3 加战斗 LoRA：`H3_Combat_V2`（出招速度、连击、受击）、`Motion_Repair`（高速动作肢体连续性）、`Bunny_weapon_combat`（兵器）。触发词 `prfight2`、`bunny_crisp_motion`。
- U20 原版没有参考视频输入，可仿 U17 接 `ref_videos.ref_video_0`；参考视频要求 2–15 秒、24fps。
- **定位**：按参考重新拍一遍打斗，不逐帧照搬。

## 3. 模型文件核对（2026-09-30）

| 模型 | 位置 |
| --- | --- |
| Wan22_Bernini_HIGH / LOW fp8 | `models/diffusion_models/Wan/` |
| wan2.1_14B_SCAIL_2（fp8、int8） | 同上；DPO / 补光 LoRA 在 `loras/Wan/` |
| Wan21_Uni3C_controlnet | `models/controlnet/` |
| sam3.1_multiplex（fp16、int8） | `models/checkpoints/` |
| H3_Combat_V2、Motion_Repair（含 V2）、Bunny_weapon_combatV1 | `loras/minimax/` |
| wan_animate_2 int8、SCAIL preview、SteadyDancer、sdpose_wholebody、SeC-4B | 均在 |
| qwen_image_edit_2511_fp8mixed + Lightning 4 步 LoRA + F2P LoRA | `diffusion_models/qwen/`、`loras/Qwen/` |
| F2K-9b dbkleinv2BFS（Klein 换脸） | `diffusion_models/flux/` |
| inswapper_128.onnx | `models/insightface/`（但没装 ReActor 节点，不能直接逐帧换脸） |

## 4. 选型建议（按镜头类型）

| 镜头 | 首选 | 备注 |
| --- | --- | --- |
| 主角近景 / 特写 | Bernini + 首帧精修，再用 K01 换头统一脸 | 实测效果最好 |
| 多人打斗 | Bernini；换不干净时考虑 SCAIL-2 只追主角 | 见 [[云端ComfyUI · 首帧精修与 Bernini 全片重制]] 的质检 |
| 无人空镜、手部 | Bernini | 只需改衣料与场景 |
| 需要重新设计的镜头 | H3 打斗 | 不追求一比一时 |

## 相关

- [[云端ComfyUI · 实例与工作流清单]]（09-29 的 K、P 系列初查）
- [[云端ComfyUI · 工作流转 API 与脚本提交]] · [[云端ComfyUI · ref105 三路线对照试验]] · [[云端ComfyUI · 首帧精修与 Bernini 全片重制]]
