---
tags: [hypit, 视频复刻, SOP, minimax-h3, autodl]
created: 2026-09-30
---

# Hypit 线 · 视频复刻工作流程 SOP

> [!warning] 已废弃（2026-10-01）
> remake-kit 已按用户要求删除：它用自写脚本替代了 Hypit 的方法，复刻只做了"拆脚本+重新生成"，没有碎片拼装、字幕与版式。本页只作试验记录保留，流程以 Hypit Skill 为准，逐关证据见 [[Hypit 复刻管线 v2 · 元认知复盘与证据关卡]]。


> 两条复刻线：**Hypit 线**＝反推提示词 → H3 按段重新生成 → 放回原切点（便宜、可批量、动作是"重新演"）；**Bernini 线**＝自有 GPU 服务器做动作迁移（保留原片逐帧动作，贵、慢，见 [[云端ComfyUI · 首帧精修与 Bernini 全片重制]]）。两条线可以在同一部片里按段混用。
> 工具细节见 [[Hypit · 通用复刻骨架 remake-kit]]。

## 怎么开工

在 Claude Code 里发：

```
/hypit 复刻：<参考片路径或链接>
换：主角 → <图>，反派 → <图>，场景 → <图>（或一句话描述）
保留：切点节奏 / 原声 / 台词（按需）
路线：Hypit 线（或：某几段走 Bernini 线）
预算：单次构建 ≤ ¥__
```

分工：**Hypit 是摄制组和剪辑室**（切点候选、缩略图、校验、计价、调模型、裁剪变速、时间线、混音、渲染、结果存档、固定镜头、Studio）；**AI 代理是导演**（看片、分段、写提示词、判断结果）——这是 Hypit 的设计本意（README：*Clone any viral video with AI agents*）。

## 一次性准备（已完成）

| 项 | 状态 |
| --- | --- |
| Hypit 0.2.16，工作区 `~/hypit-projects` | ✅ |
| Runtime：H3 绑定 `h3.market`（AutoDL.Art 市场 API，Provider `@local/provider-autodl-market`） | ✅ |
| 备用 H3：`h3.autodl`（自有 4090D ComfyUI，需开机 + SSH 隧道；支持参考视频/动作迁移） | ✅ |
| Token `~/.config/autodl/token`；花费账本 `~/.config/autodl/market-ledger.json` 上限 ¥30 | ✅ |
| 本机免费能力：媒体处理、WhisperX 转写、HyperFrames 渲染 | ✅ |
| 复刻骨架 `remake-kit/remake.py` | ✅ |

## 流程（每部片）

### ① 立项 —— 你给素材，不花钱
- 你：参考片（文件或链接）、新角色/场景参考图、一句话"换什么/留什么"、预算。
- 我：参考片放 `references/<参考名>/source.mp4`（链接用 `hypit media fetch`）；`remake.py new <作品> --source … [--range 起:止]` 建 `productions/<作品>/`，写 BRIEF（目标 + 花费约定）。

### ② 读懂参考片 —— 不花钱
- 从头看到尾：钩子、叙事弧、节奏、观众情绪；有台词用 `hypit transcribe`（本机 WhisperX）拿逐字时间。
- 写 `ANALYSIS.md`（整体理解）、`TIMELINE.md`（几秒发生什么、起什么作用）、`TREATMENT.md`（新片的创作回答：保留哪些关系，换掉哪些外观）。
- **检查点**：我汇报读片结论和改编方向，你拍板。

### ③ 切镜头、分段落 —— 不花钱
- `remake.py cut <作品>`：`hypit media boundaries` 找切点候选 → 每段出缩略图。
- ⚠️ 自动切点只是候选（ref105 暗雨戏：找到 114、命中核对切点 69/78），要对着缩略图/逐帧核对，或 `--cuts` 导入人工切点。
- 按**叙事**分段：一个动作回合 / 一次对峙 = 一段 = **一次 H3 请求，4–15 秒**，段内多镜头由提示词分镜；手动调整后 `remake.py sheets` 重出缩略图。

### ④ 定角色与世界 —— 不花钱
- `cast.json`：每张参考图 + 一句英文描述；kind = `character` 单人 / `group` 群体 / `scene` 地点 / `other` 服装全身、道具。
- **只描述新形象，不描述原片外观**（原片的斗笠、亮蓝袍一旦写进去，模型就会照抄）。
- 每段 `refs` 选用哪几张（顺序 = Picture 1…，市场最多 6 张）。

### ⑤ 反推提示词 —— 不花钱
- 每个镜头写 `camera`（景别、机位、运镜）与 `action`（看得见的动作、接触、表情），`{hero}` 等占位自动换成 `<Subject n>`；需要时加 `summary`、`sound`、`dialogue`。
- 原则（Hypit 视频导演规范）：写动作的**原因和态度**再写关键细节；用具体可见的语言，不用比喻；只写这个镜头真正出现的东西。
- 每段选模式：`h3-reference`（默认）/ `h3-text` / `h3-frame`（市场需首尾两帧）/ `source`（保留原片）/ `motion_ref`（原片当动作参考，只能走自有服务器）。

### ⑥ 组装与校验 —— 不花钱
- `remake.py compose <作品>` → `authors/remake.svml`、`recipes/remake.svs`、`runs/remake.svrun`，自动 `hypit check`。
- 结构：每段 H3 生成 → 统一帧率 → 裁到原段长（或整段变速）→ 空 Script Segment → 放回原片起始帧 → 全画幅 → 原声整段铺底 → Film → HyperFrames 渲染。

### ⑦ 估价 —— 不花钱，**你确认**
- `remake.py estimate <作品>`：逐段价格（高峰 8–24 点 / 闲时 0–8 点）、被拒请求及原因、账本余额。
- 参考价：z0903 1088p ¥0.07/秒（闲时 ¥0.05）；85 秒的片一遍约 ¥6.4。

### ⑧ 试跑一段 —— 花小钱，**你确认**
- `remake.py pilot <作品> <段落>` → 只生成这段（ref105 s07：6 秒 ¥0.42）。
- `hypit build productions/<作品>/runs/pilot.svrun --follow`；`hypit get <build> --output g-<段>.video --to …` 看结果。
- 验证：参考图是否被当成首帧硬贴；多镜头切点是否被遵守；角色像不像；有没有照抄原片外观。满意就 `pin` 下来，整片不再重做这段。

### ⑨ 全片构建 —— 花钱，**你确认**
- `hypit build productions/<作品>/runs/remake.svrun --follow`：Provider 并发 4 路提交市场、轮询、下载、裁剪；其余全在本机。
- 提交前 Provider 查账本，超上限直接拒绝（不会超支）。
- `hypit get <build> --output final.video --to …` 导出成片。

### ⑩ 审片与迭代
- 看成片 + 逐段；需要时 `hypit studio --run …` 在时间线上看、留时间码批注。
- 满意的段 `remake.py pin <作品> <build> <段…>`；不满意的改提示词/参考图/`offset`/`fit` → compose → estimate → 再 build（**只重做没固定的段**）。
- H3 演不好的段（精确打斗接触）：改走 Bernini 线后 `use-file` 顶替，或 `source` 保留原片，或切自有服务器用 `motion_ref`。

### ⑪ 交付与记录
- 成片导出到桌面交付包；PROGRESS 写清用到的 Build id 与固定的段落；Obsidian 记录试验结论。

## 你只在四个地方出现

1. 开工时给素材 + 路线 + 预算；
2. 读片后确认改编方向（可选）；
3. 每次花钱前确认估价（试跑、整片、重跑）；
4. 看成片提意见。
