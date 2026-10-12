"""合成"要被替换的人"的遮罩：种子（长袍∪斗笠）+ 与种子重叠的人物整体，再在镜头内做时间补帧。

用法：
  uv run --with numpy --with opencv-python-headless python mask_merge.py \
      --robe robe.mp4 --hat hat.mp4 --person person.mp4 --source S01.mp4 \
      --cuts 0.9,1.4,... --out mask.mp4 --preview preview.mp4 --report report.json
"""
import argparse
import json
import subprocess

import cv2
import numpy as np

W, H, FPS = 1280, 624, 30


def read_gray(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return (np.frombuffer(raw, np.uint8).reshape(-1, H, W) > 127)


def read_rgb(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"scale={W}:{H}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)


def write_video(frames, path, pix="gray"):
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix, "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "0" if pix == "gray" else "18",
                             "-pix_fmt", "yuv420p", path], stdin=subprocess.PIPE)
    for f in frames:
        proc.stdin.write(f.tobytes())
    proc.stdin.close()
    proc.wait()


def bbox_width(mask):
    xs = np.where(mask.any(axis=0))[0]
    return (xs[-1] - xs[0] + 1) if len(xs) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--robe", required=True)
    ap.add_argument("--hat", required=True)
    ap.add_argument("--person", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--cuts", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview")
    ap.add_argument("--report")
    ap.add_argument("--fill", type=int, default=30, help="镜头内向前/向后补帧的最大距离")
    ap.add_argument("--hero-shots", default="", help="有主角的镜头序号（1 起，逗号分隔）；其余镜头强制无遮罩。留空则不限制")
    ap.add_argument("--dilate", type=int, default=8)
    args = ap.parse_args()

    robe, hat, person = read_gray(args.robe), read_gray(args.hat), read_gray(args.person)
    src = read_rgb(args.source)
    n = min(len(robe), len(hat), len(person), len(src))
    robe, hat, person, src = robe[:n], hat[:n], person[:n], src[:n]
    min_area = int(W * H * 0.002)

    hero = np.zeros_like(robe)
    source_tag = np.zeros(n, dtype="<U12")
    for t in range(n):
        seed = robe[t] | hat[t]
        if seed.sum() < min_area // 4:
            source_tag[t] = "none"
            continue
        out = seed.copy()
        count, labels = cv2.connectedComponents(person[t].astype(np.uint8))
        seed_w = max(bbox_width(seed), 1)
        for c in range(1, count):
            comp = labels == c
            overlap = (comp & seed).sum()
            if overlap < 0.3 * seed.sum() and overlap < 0.3 * comp.sum():
                continue
            if bbox_width(comp) > 2.5 * seed_w and bbox_width(comp) > W * 0.35:
                continue  # 多人粘连成一块，只保留种子
            out |= comp
        hero[t] = out
        source_tag[t] = "seed+person" if out.sum() > seed.sum() else "seed"

    cuts = sorted(int(round(float(c) * FPS)) for c in args.cuts.split(",") if c.strip())
    bounds = [0] + [c for c in cuts if 0 < c < n] + [n]
    shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]

    hero_shots = {int(x) for x in args.hero_shots.split(",") if x.strip()}
    if hero_shots:
        for i, (a, b) in enumerate(shots, 1):
            if i not in hero_shots:
                hero[a:b] = False
                source_tag[a:b] = "no-hero"
            else:
                for t in range(a, b):
                    if hero[t].sum() < min_area and person[t].sum() >= min_area:
                        count, labels = cv2.connectedComponents(person[t].astype(np.uint8))
                        hsv = cv2.cvtColor(src[t], cv2.COLOR_RGB2HSV)
                        blue = (hsv[..., 0] >= 85) & (hsv[..., 0] <= 125) & (hsv[..., 1] >= 70) & (hsv[..., 2] >= 40)
                        best, best_score = 0, 0.0
                        for c in range(1, count):
                            comp = labels == c
                            area = comp.sum()
                            if area < min_area // 2: continue
                            score = (comp & blue).sum() / area
                            if score > best_score: best, best_score = c, score
                        if best and best_score >= 0.08:  # 原片主角是全片唯一的亮蓝袍
                            hero[t] = labels == best
                            source_tag[t] = "person"

    # 连贯性：兜底选出的人若离上一帧主角太远（跳到别人身上），放弃这一帧，交给补帧
    def centroid(m):
        ys, xs = np.nonzero(m)
        return (xs.mean(), ys.mean()) if len(xs) else None
    for a, b in shots:
        anchors = [(t, centroid(hero[t])) for t in range(a, b)
                   if source_tag[t] in ("seed", "seed+person") and hero[t].sum() >= min_area]
        last = None
        for t in range(a, b):
            if hero[t].sum() < min_area: continue
            c = centroid(hero[t])
            if source_tag[t] == "person":
                ref = min(anchors, key=lambda x: abs(x[0] - t))[1] if anchors else last
                if ref is not None and abs(c[0] - ref[0]) > 0.25 * W:
                    hero[t] = False; source_tag[t] = "jump"
                    continue
            last = c

    filled = hero.copy()
    for a, b in shots:
        have = [t for t in range(a, b) if hero[t].sum() >= min_area]
        if not have:
            continue
        for t in range(a, b):
            if hero[t].sum() >= min_area:
                continue
            prev = [h for h in have if h < t and t - h <= args.fill]
            nxt = [h for h in have if h > t and h - t <= args.fill]
            if prev or nxt:
                m = np.zeros_like(hero[t])
                if prev: m |= hero[prev[-1]]
                if nxt: m |= hero[nxt[0]]
                filled[t] = m
                source_tag[t] = "filled"

    smooth = filled.copy()
    for a, b in shots:
        for t in range(a, b):
            lo, hi = max(a, t - 1), min(b, t + 2)
            smooth[t] = filled[lo:hi].any(axis=0)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * args.dilate + 1, 2 * args.dilate + 1))
    final = np.stack([cv2.dilate(m.astype(np.uint8), kernel) * 255 for m in smooth])
    write_video(final, args.out)

    report = []
    for i, (a, b) in enumerate(shots):
        cover = [bool(final[t].any()) for t in range(a, b)]
        tags = {k: int((source_tag[a:b] == k).sum()) for k in ("seed", "seed+person", "person", "filled", "none", "no-hero", "jump")}
        report.append({"shot": i + 1, "start": round(a / FPS, 3), "end": round(b / FPS, 3),
                       "frames": b - a, "covered": sum(cover), **tags})
    if args.report:
        json.dump(report, open(args.report, "w"), ensure_ascii=False, indent=1)
    for r in report:
        print("镜头%02d %5.2f-%5.2fs 帧%3d 覆盖%3d | 种子%3d 种子+人%3d 人物兜底%3d 补帧%3d 无%3d 无主角%3d 跳错%3d" % (
            r["shot"], r["start"], r["end"], r["frames"], r["covered"], r["seed"], r["seed+person"], r["person"], r["filled"], r["none"], r["no-hero"], r["jump"]))

    if args.preview:
        over = src.copy()
        red = np.zeros_like(src); red[..., 0] = 255
        sel = final > 0
        over[sel] = (0.45 * src[sel] + 0.55 * red[sel]).astype(np.uint8)
        write_video(over, args.preview, pix="rgb24")


if __name__ == "__main__":
    main()
