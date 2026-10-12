#!/usr/bin/env python3
"""复刻成片 vs 参考片的逐镜量化对比（第 4 阶段 · 证据审查的自动化部分）。

对每个镜头计算：
  motion   镜内运动量：相邻帧平均绝对差（0–255）
  luma     平均亮度；contrast 亮度标准差
  rgb      平均 R/G/B（看色调，如青蓝 vs 中性灰）
  edge     拉普拉斯近似的边缘强度（越低越糊）
另外对两条片子各跑一次 `hypit media boundaries`，比较切点数，找出多出来的跳切。

用法：
  python3 review_metrics.py --src ref.mp4 --clone out.mp4 --cuts 0,27,42,66,88,104,114,128,135,147,161,171,191,249 \
      [--fps 30] [--crop 1280:640:0:0] [--duration 8.3] [--json out.json]
--cuts 是镜头边界帧（含首尾）；--crop 只统计画面区（排除字幕黑条）。
依赖：ffmpeg、numpy；切点对比需要 hypit CLI。
"""
import argparse, json, subprocess, sys
import numpy as np

W, H = 320, 160


def frames(path, fps, crop, duration):
    vf = f"fps={fps}" + (f",crop={crop}" if crop else "") + f",scale={W}:{H}"
    cmd = ["ffmpeg", "-v", "error", "-i", path] + (["-t", str(duration)] if duration else []) + \
          ["-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(np.float32)


def shot_stats(f, cuts):
    out = []
    for i in range(len(cuts) - 1):
        a, b = cuts[i], min(cuts[i + 1], len(f))
        seg = f[a:b]
        if len(seg) == 0:
            out.append(None); continue
        L = 0.299 * seg[..., 0] + 0.587 * seg[..., 1] + 0.114 * seg[..., 2]
        lap = np.abs(L[:, 1:-1, 1:-1] * 4 - L[:, :-2, 1:-1] - L[:, 2:, 1:-1] - L[:, 1:-1, :-2] - L[:, 1:-1, 2:]).mean()
        out.append(dict(
            shot=chr(65 + i) if i < 26 else str(i), frames=b - a,
            motion=round(float(np.abs(np.diff(seg, axis=0)).mean()) if len(seg) > 1 else 0.0, 1),
            luma=round(float(L.mean()), 1), contrast=round(float(L.std()), 1),
            rgb=[round(float(seg[..., k].mean())) for k in range(3)], edge=round(float(lap), 1)))
    return out


def boundaries(path, fps, duration=None):
    import tempfile, os
    tmp = None
    try:
        if duration:  # 只检测前 duration 秒：先裁一份临时文件
            tmp = tempfile.mkdtemp()
            cut = os.path.join(tmp, "cut.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-t", str(duration), "-an", "-c:v", "libx264", "-crf", "12", cut], check=True)
            path = cut
        r = subprocess.run(["hypit", "media", "boundaries", path, "--rate", str(fps), "--json"], capture_output=True, text=True, check=True)
        return [c["at"] for c in json.loads(r.stdout)["candidates"]]
    except Exception as e:  # 没装 hypit 时跳过
        print(f"[warn] boundaries skipped for {path}: {e}", file=sys.stderr)
        return None
    finally:
        if tmp:
            import shutil; shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True); ap.add_argument("--clone", required=True)
    ap.add_argument("--cuts", required=True, help="镜头边界帧，逗号分隔，含首尾")
    ap.add_argument("--fps", type=int, default=30); ap.add_argument("--crop"); ap.add_argument("--duration", type=float)
    ap.add_argument("--json")
    a = ap.parse_args()
    cuts = [int(x) for x in a.cuts.split(",")]
    S = shot_stats(frames(a.src, a.fps, a.crop, a.duration), cuts)
    C = shot_stats(frames(a.clone, a.fps, a.crop, a.duration), cuts)
    print(f"{'镜':<4}{'帧':>4} | {'运动 原/复':>13} | {'亮度 原/复':>12} | {'RGB 原':>15} {'RGB 复':>15}")
    for s, c in zip(S, C):
        if s and c:
            flag = "  ← 运动不足" if s["motion"] > 2 * max(c["motion"], .1) else ""
            print(f"{s['shot']:<4}{s['frames']:>4} | {s['motion']:>5}/{c['motion']:<6} | {s['luma']:>5}/{c['luma']:<5} | {str(s['rgb']):>15} {str(c['rgb']):>15}{flag}")
    bs, bc = boundaries(a.src, a.fps, a.duration), boundaries(a.clone, a.fps, a.duration)
    report = {"src": S, "clone": C, "boundaries": {"src": bs, "clone": bc}}
    if bs is not None and bc is not None:
        # 一对一配对：每个原片切点最多认领一个复刻切点（容差 1.5 帧）
        free, extra = list(bs), []
        for t in bc:
            near = min(free, key=lambda u: abs(t - u), default=None)
            if near is not None and abs(t - near) <= 1.5 / a.fps: free.remove(near)
            else: extra.append(t)
        report["boundaries"]["clone_extra"] = extra
        print(f"\n切点候选：原 {len(bs)} 个，复 {len(bc)} 个；复刻多出：{extra or '无'}（需逐帧核对是否为跳切）")
    if a.json:
        json.dump(report, open(a.json, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
