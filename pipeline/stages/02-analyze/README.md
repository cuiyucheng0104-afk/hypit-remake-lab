# 02 · 读片

**目标**：把一条参考片读成时间码级的结构，作为 03 生产的依据。方法见根目录 `skills/hypit/references/creation/reference-video.md`。

## 工具（Hypit CLI，全部本机运行、免费）

```bash
hypit media boundaries ref.mp4 --rate 30 --json      # 切点候选（机械检测，要逐帧核对）
hypit media tiles ref.mp4 --every-frame --ranges ...  # 逐原帧网格
hypit media frames ref.mp4 --at 1.2,3.4 --label-time
hypit transcribe ref.mp4 --language zh               # 有人声时
```

## 产出

- `ANALYSIS.md`：整片为什么抓人。
- `TIMELINE.md`：每镜的内容、景别、机位，以及**运动路径与速度（量化）**和转场手段。
- `evidence/`：切点、音频起点等证据数据。

样例见 [references/](references/)：ref-105 武侠戏、lanv-30s 教程片，原片与转写稿不含在内。

## 现状与待补

**agent 已跑通**：由 agent 调用上面的 `hypit media` 命令完成读片，ref-105 与 lanv-30s 是实际产物。

待补：
- **无人值守触发**：用非交互模式启动 agent（如 `claude -p` 加 Hypit Skill），由趋势清单驱动；
- **机器可读产物**：`shots.json`，写明每镜的帧区间、景别、运动强度和作用，供 03 直接读取；
- **自动核对图**：在切点候选上自动出逐帧核对图。运动量量化可以复用 `04-review/scripts/review_metrics.py` 的算法。
