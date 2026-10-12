# 04 · 审查

- [证据关卡-v2.md](证据关卡-v2.md)：11 道关卡，每关写明"拿出什么证据才放行"，另有 8 条元认知守则。来源是对 71 条判断失误的复盘，独立核对后 69 条成立。
- [scripts/review_metrics.py](scripts/review_metrics.py)：参考片和复刻片逐镜量化对比，包括运动量、亮度、RGB 色调、边缘强度，并对比两者的切点候选，找出多出来的跳切。

```bash
python3 scripts/review_metrics.py --src ref.mp4 --clone out.mp4 \
  --cuts 0,27,42,66,88,104,114,128,135,147,161,171,191,249 --crop 1280:640:0:0 --duration 8.3 --json report.json
```

在 S01 上实测：脚本标出了 A、F、I、J、L 五个镜头运动不足，以及 K 镜里 5.4 秒、5.467 秒两个多出的切点，和人工复盘结论一致。

## 待开发

- 把关卡变成可执行的检查清单，自动出逐帧核对图；
- "按作用比对"仍需 agent 判断，要接入 Hypit 的 snapshot 和 Studio。
