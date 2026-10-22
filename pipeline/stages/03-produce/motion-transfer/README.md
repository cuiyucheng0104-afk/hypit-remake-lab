# 03b · 动作迁移（实验阶段）

> **2026-10-22 第二轮调研**：见 [动作迁移与白膜调研-2026-10-22](../../../docs/research/动作迁移与白膜调研-2026-10-22.md)。和本页相关的变化：
> - H3 打斗路线**不能用于美国区成片**（H3 许可排除美国），只做研发对照；
> - Wan-Animate-2（Apache，Zealman 已有）、SCAIL-2 端到端模式、Bernini v2 都待重测；
> - 深度留不住剑，剑要画在首帧里、写进提示词；
> - 建议和 03c 合并成「几何约束层」（调研文档第 7 节）。

**目标**：保留原片逐帧的动作和运镜，只替换角色和场景。这条路解决的正是 Hypit 复刻里"动作演不出来"的问题。

## 现状

[ref105-experiments/](ref105-experiments/) 是在自有 AutoDL 4090D ComfyUI 服务器上做的对照试验：

| 路线 | 结论（3 个镜头对照） |
| --- | --- |
| Bernini（视频编辑，K08） | **动作 1:1 最稳**，主角换对；群像里敌人和场景常常没换，偶尔偏暗偏糊；6–12 分钟/镜 |
| SCAIL-2（多人追踪替换，P24） | 主角能换但不稳；按追踪遮罩重画，遮罩内的斗笠和原演员脸会留下；约 8–10 分钟/镜 |
| H3 打斗（U20 双 LoRA） | 人物最清晰，但会**重新编排打斗**，不是 1:1；参考视频需 ≥2 秒；15–18 分钟/镜 |
| 首帧精修 + Bernini 传播 | 采用的方案：先用图像编辑（Qwen-Edit）把每镜首帧改对，再交给 Bernini 传播到整镜 |

- 各路线的对照结论见 `docs/cloud-comfyui/云端ComfyUI · ref105 三路线对照试验.md`；
- 批量流程见 `segs/`（pipeline、qa、review、chain.sh）；
- 提交方式见 `trial/comfy.py`：直连 ComfyUI 的 `/prompt` 接口，经 SSH 隧道转发到 `127.0.0.1:16006`。

**工作流 JSON 不含在仓库内**，它们来自 Zealman 镜像，转发授权不明。请在服务器上导出，放回 `trial/workflows/` 和 `comfy/workflows/`。

## 待开发

把动作迁移包装成 Hypit Provider：仿照 `packages/provider-comfy-h3`，让它和 03a 一样走 plan、估价、钉住结果的流程，而不是用脚本直连 ComfyUI。
