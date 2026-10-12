# pipeline：趋势 → 复刻 / 动作迁移 → 审查 → 发布 → 回测

基于 Hypit 的 AI 短视频生产管线。**目标**是让 agent 自动跑完整条链路：
- 搜索 TikTok 趋势；
- 用 Hypit 复刻爆款的结构，或用动作迁移重做画面；
- 经证据关卡审查后发布；
- 用发布数据回测，指导下一轮选题。

当前是初始仓库：先把已有的代码、实验和技术文档收进来，按阶段排好，后续逐段补齐。

## 管线与现状

| 阶段 | 做什么 | 现状 | 位置 |
| --- | --- | --- | --- |
| 01 趋势 | 拉取趋势视频与指标，产出候选清单 | 待开发 | [stages/01-trend](stages/01-trend/) |
| 02 读片 | 切点、节奏、景别、字幕系统，产出 ANALYSIS / TIMELINE | **agent 已跑通**（ref-105、lanv-30s）；待补无人值守触发和机器可读的 `shots.json` | [stages/02-analyze](stages/02-analyze/) |
| 03a Hypit 复刻 | BRIEF → TREATMENT → SVML → 预览 → 估价 → 生成 → 拼装 | **agent 已跑通**（S01 样例）；待补无人值守触发 | [stages/03-produce/hypit-remake](stages/03-produce/hypit-remake/) |
| 03b 动作迁移 | 原片动作 + 新角色（Bernini / SCAIL-2 / Wan Animate） | 实验脚本，未接入 Hypit | [stages/03-produce/motion-transfer](stages/03-produce/motion-transfer/) |
| 03c 灰模导演台 | 参考片反推相机 + 多人 3D 动作 → Blender 白膜 → Seedance 参考视频 | 调研完成，待实验 | [stages/03-produce/greybox-director](stages/03-produce/greybox-director/) |
| 04 审查 | 11 道证据关卡；切点、运动量、色调自动对比 | 关卡文档 + 量化脚本 | [stages/04-review](stages/04-review/) |
| 05 发布 | 人工确认后，经官方接口发布 | 待开发 | [stages/05-publish](stages/05-publish/) |
| 06 回测 | 拉取发布数据，回写选题与生产参数 | 待开发 | [stages/06-backtest](stages/06-backtest/) |

## 共用部件

| 目录 | 内容 |
| --- | --- |
| [packages/provider-autodl-market](packages/provider-autodl-market/) | Hypit Provider：AutoDL.Art 市场的 MiniMax H3（参考生 / 首尾帧 / 文生视频），带花费账本和上限闸门，提交失败自动退款，参考图压缩 |
| [packages/provider-comfy-h3](packages/provider-comfy-h3/) | Hypit Provider：自有 ComfyUI 服务器上的 H3，经 SSH 隧道调用，支持参考视频 |
| [tools/](tools/) | 估价、账本、AutoDL 实例开关机、市场 API、方舟素材库上传、ComfyUI 调试脚本 |
| [hypit.runtime.example.json](hypit.runtime.example.json) | Runtime Profile 示例：Endpoint 绑定，不含令牌 |
| [examples/](examples/) | 其它实验工程：讲解员替换、市场 Provider 的离线假服务器测试、早期 remake-kit 工程 |
| [third_party/](third_party/) | Postiz 完整源码与文档（AGPL / MIT）；PromptHMR 子模块引用（非商业，不含源码） |
| [docs/](docs/) | Hypit 研究笔记、自有 Provider 接入、云端 ComfyUI、S01 实测评估、平台与接口调研 |

## 环境

1. **Node 24**；Hypit CLI 用 `npm i -g @hypit/hypit`（实测 0.2.16），也可以用本仓库根目录的源码构建。
2. **编译 Provider**：
   ```bash
   cd pipeline/packages/provider-autodl-market && npm i && npx tsc
   ```
3. **配置**：在自己的 Hypit 工作区放一份 `hypit.runtime.json`（参考示例），在 `package.json` 里以本地路径引用 Provider 包。
4. **令牌**：由使用者自己存到本机文件，例如：
   ```bash
   read -rs T && printf '%s' "$T" > ~/.config/autodl/comfy_token && chmod 600 ~/.config/autodl/comfy_token
   ```
   注意：市场令牌和 AutoDL 实例令牌（`~/.config/autodl/token`）是两套，不要混用。
5. **其它依赖**：ffmpeg、Python 3、numpy；有动作迁移需求时，另需 AutoDL 4090D 上的 ComfyUI 实例（Zealman 镜像）。

## 开发约定（来自实测教训，见 stages/04-review/证据关卡-v2.md）

- **不绕开 Hypit**：生成、计价、固定结果都走 Hypit 的 Provider / plan / build-record，自写脚本只补 Hypit 缺的能力。
- **花钱前先 `hypit plan` 和 `pricing`**：花费账本设上限（默认 ¥30），超限由 Provider 直接拒绝。
- **轮询只查状态**：有的查询接口在任务成功时会自动下载文件。
- **结论标证据等级**：实测 / 推断 / 未知；"完成"类结论要独立核对。
- **凭据**：不进仓库，不调 AutoDL 的 `snapshot` 接口（它会返回 root 密码），SSH 只用密钥。
- **不提交媒体**：参考片、生成片、截帧都由 `.gitignore` 排除。

## 许可证

本目录遵循仓库根目录的 [LICENSE](../LICENSE)（Hypit 修改版 Apache 2.0）：
- 可以 fork、修改、公开发布，以及公司自用、为客户做服务；
- **多租户 / SaaS 服务和收费再分发需要 Hypit.AI 的商业授权**。
