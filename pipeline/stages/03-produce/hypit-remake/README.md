# 03a · Hypit 复刻（已跑通）

样例：[example-ref105-s01/](example-ref105-s01/)，8.3 秒、13 个镜头的武侠戏。

| 文件 | 作用 |
| --- | --- |
| `BRIEF.md` | 用户目标、替换项、花费约定 |
| `TREATMENT.md` | 改编方案：每个元素的"作用"怎么继承或换形式 |
| `authors/s01.svml` | 4 个 `h3:ReferenceVideo` 生成节点；13 个空 Segment 经 Transform 裁剪后，按原片帧号放到 Timeline 上；字幕条（typo）和原声 |
| `recipes/s01.svs` | 外观：画面区、字幕样式 |
| `runs/preview.svrun` | 原片占位的免费预览 |
| `runs/generate.svrun` | 只生成 4 段素材（付费） |
| `runs/assemble.svrun` | 用 `build-record` + `satisfy` 钉住已生成的素材，再拼装（零付费） |
| `drafts/review/` | 复盘统计、元认知审计数据 |

## 流程

```bash
hypit check runs/preview.svrun && hypit build runs/preview.svrun --follow       # 免费预览
hypit plan runs/generate.svrun && hypit pricing runs/generate.svrun             # 估价
hypit build runs/generate.svrun --follow                                        # 付费生成
hypit build runs/assemble.svrun --follow && hypit get <build> --output final.video --to out.mp4
```

## 已知短板（S01 复盘）

- 市场 Provider 不收参考视频，动作只能靠文字描述，所以镜内运动量明显不足；
- 倒握这种精确的手部动作没演出来；
- 色调偏灰；
- 选段跨过了 H3 自己在生成片里切的镜头，形成跳切。

对应的改法见 `04-review/证据关卡-v2.md`。
