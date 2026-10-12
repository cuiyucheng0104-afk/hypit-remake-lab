---
tags: [hypit, 视频复刻, minimax-h3, autodl]
created: 2026-09-30
---

# Hypit · 通用复刻骨架 remake-kit

> [!warning] 已废弃（2026-10-01）
> remake-kit 已按用户要求删除：它用自写脚本替代了 Hypit 的方法，复刻只做了"拆脚本+重新生成"，没有碎片拼装、字幕与版式。本页只作试验记录保留，流程以 Hypit Skill 为准。


> 视频复刻分两条线：**Hypit 线**（反推提示词 → H3 按段重新生成 → 放回原切点，便宜、可批量）与 **Bernini 线**（动作迁移高精度，见 [[云端ComfyUI · 首帧精修与 Bernini 全片重制]]）。这里记录 Hypit 线的通用骨架，所有后续复刻片都套这一套。

代码：`~/hypit-projects/remake-kit/remake.py`（说明 `remake-kit/README.md`）；第一个作品 `productions/ref105-hypit/`。

## 整体链路

参考片 → `cut` 切镜头（`hypit media boundaries` 机械候选 / 导入核对切点）→ 分段落 → `sheets` 每段缩略图 → 人/Claude 反推每镜 camera + action → `compose` 生成 Hypit Source/Recipe/Run 并 `hypit check` → `estimate` 只读估价 → 确认后 `hypit build` → `pin` 固定满意段落 → 只重跑没固定的。

## 关键设计（来自 Hypit Skill 的规定）

- **一段 = 一次 H3 请求（4–15 秒），不是一镜一请求。** Hypit 的视频导演规范写明：请求跨度按要表达的表演选择，一次生成可以包含多个镜头。提示词里按原片切点写 `[Shot n] 景别 (起 - 止)`。
  - 效果：ref105 79 个镜头 → 9 段 91 秒，整片一遍 **高峰 ¥6.37 / 闲时 ¥4.55**；一镜一请求要 323 秒 ≈ ¥22.6。
- 每段在 Script 里是一个**空 Segment**，时长由画面决定，不走 WhisperX；Timeline 用 `at="<帧>f"` 把每段放回原片起始帧，`end` = 复刻区间总帧数 → 原声、音乐卡点天然对齐。
- 时长不符：`trim`（取前 N 帧，可 `offset`）或 `retime`（整段变速，提示词时间同比例拉伸）。
- 声音默认用参考片原声（audio-track 整段），生成画面静音；可切 `generated`。
- 复用：满意段落写 `build-record` + `satisfy`（`pin`）；Bernini 线的成片可以用 `<file>` 候选直接顶替某段（`use-file`）——两条线在同一条时间线上汇合。

## 三份人写的文件

| 文件 | 内容 |
| --- | --- |
| `remake.json` | 参考片路径、复刻区间、帧率画幅、声音策略、整体风格句 |
| `cast.json` | 参考图 + 英文描述；kind = character / group / scene / other |
| `beats.json` | 段落：mode（h3-reference / h3-text / h3-frame / source）、refs、每镜 camera/action（`{hero}` 占位 → `<Subject n>`） |

## 生成的 H3 提示词格式

沿用蓝V实测跑通的 JSON：`subject_definitions`（`<Subject 1> is the person in <Picture 1>: …`）、`summary`、`retention_analysis`、`detailed_description`（风格句 + 各 `[Shot n]`）、`overall_soundscape`、`non_diegetic_music`。

## 自测结论（2026-09-30，未花钱）

- 七种情况都能 compose + check + plan：保留原片、文生、首尾帧（`src:<帧号>` 从原片取帧）、参考图、变速、偏移、现成视频顶替、固定旧构建。
- 市场 Provider 在 plan 阶段就拒绝参考视频（`motion_ref`），提示把绑定切回自有服务器 `h3.autodl`。
- 估价脚本修正：首尾帧请求没有 aspectRatio，据此识别为 736p 计价；被拒请求单列不计价。
- 自动切点对暗色雨戏偏多偏少：阈值 0.13 找到 114 个，只命中核对切点 69/78——**自动切点只是候选，必须看缩略图核对**。

## 待验证（需付费）

- z0903 是否把参考图当成首帧硬贴。
- 多镜头提示词里的切点时间是否被遵守（建议先跑 s07，6 秒 ¥0.42）。

## 首次真实跑通：ref105 S01（2026-10-01）

- 结果：8.3 秒成片，你的主角 / 斗笠刀客 / 雨夜古院，原片 12 镜顺序全对；一次 9 秒 1088p 生成，闲时 **¥0.45**，市场排队+生成约 **13 分钟**。
- 踩坑与修复：
  1. `~/.config/autodl/token` 是**实例管理令牌**，市场要「令牌管理」里 ComfyUI 分组的令牌 → 单独存 `~/.config/autodl/comfy_token`（用 `read -rs` 粘贴，别用 `pbpaste`）。
  2. 市场文档写"图片 URL"，实测 **base64 内嵌也收**；参考图先压到 JPEG ≤1600px。
  3. 提交失败要退回账本预扣（已修）。
  4. H3 演得比原片慢约 8%：按原长裁尾会丢掉最后一镜 → 该段 `fit: retime` 整段变速压回原长。
  5. `pin` 要用 `hypit history <输出>` 核对（`inspect` 只列目标输出）。
- 复用：生成结果 `pin` 后改 fit 重建，**0 付费请求**，只重跑本机步骤。
- 进度查询：Provider 把市场任务号写进构建日志；每 60 秒同时查市场状态与构建步骤。

标准流程：[[Hypit 线 · 视频复刻工作流程 SOP]]；试跑单段 `remake.py pilot <作品> <段>`。

相关：[[Hypit · 自有 H3 Provider 接入]]、[[Hypit · 实测：蓝V教程换讲解员]]、[[云端ComfyUI · ref105 三路线对照试验]]
