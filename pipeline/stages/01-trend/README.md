# 01 · 趋势（待开发）

**目标**：按市场、品类、时间窗拉取趋势视频与指标，产出候选清单，交给 02 读片。

## 输出草案：`trends/<date>.json`

```json
[{ "id": "...", "url": "...", "source": "fastmoss",
   "metrics": { "views": 0, "likes": 0, "growth_7d": 0 },
   "category": "...", "region": "US", "fetched_at": "2026-10-12T00:00:00Z" }]
```

## 数据源（调研结论，详见 docs/research/平台与接口调研.json）

- **FastMoss OpenAPI**：55 个接口，有 REST / CLI / MCP 三种形式，共用一个 Key。
  - 单价 $0.01–0.02/次；`pagesize` 大于 10 时，按 `ceil(pagesize/10)` 倍扣费；返回 0 条不扣费；免费试用 500 次。
  - 视频类只有 `/video/v1/search` 一个接口，**没有话题、音乐趋势和视频下载接口**。
- **EchoTik API**：单价低至 $0.001/次，有话题、音乐等实时接口。但它自述数据直接取自 TikTok 公开接口，存在合规风险。
- **TikTok 官方**：
  - Research API 不对商业用户开放；
  - Creative Center 免费，但没有程序化接口。

## 注意

- **用量**：先定每天的调用量和 `pagesize`，它们直接决定费用。
- **条款**：FastMoss 用户协议原文还没拿到，数据能否商用、能否再分发待确认。
