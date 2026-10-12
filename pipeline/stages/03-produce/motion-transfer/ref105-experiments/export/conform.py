#!/usr/bin/env python3
"""把外部平台生成的分段按原片时间线装回去。

用法：把生成结果命名为 generated/S01.mp4 … S09.mp4，然后运行
    python3 conform.py
输出在 out/：
    conformed.mp4      1280×620，30 fps，与原片正片逐帧对齐（85.767 s）
    conformed_720.mp4  底部补 100 px 黑条的 1280×720 版，留给字幕
    compare.mp4        上：去水印原片参考；下：装回后的新片，逐段对照检查
缺失的段用灰度原片参考占位，方便边生成边预览。
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
W, H, FPS = 1280, 620, 30
TOLERANCE = 0.04  # 秒；时长差超过这个值就按比例变速对齐


def duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out)


def run(args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def main():
    segs = json.load(open("segments.json"))
    os.makedirs("out/parts", exist_ok=True)
    fill = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}"
    rows, parts, refs = [], [], []
    for s in segs:
        sid, want = s["id"], s["duration"]
        ref = f"refclips/{sid}.mp4"
        gen = f"generated/{sid}.mp4"
        part = f"out/parts/{sid}.mp4"
        if os.path.exists(gen):
            got = duration(gen)
            if abs(got - want) > TOLERANCE:
                factor = want / got
                vf = f"setpts=PTS*{factor:.6f},{fill}"
                note = f"时长 {got:.3f}s ≠ {want:.3f}s，已变速 ×{1/factor:.3f}"
            else:
                vf = fill
                note = "时长一致"
            status = "已生成"
        else:
            gen, vf = ref, f"hue=s=0,{fill}"
            status, note = "缺失", "用灰度原片占位"
        run(["-i", gen, "-vf", vf, "-t", f"{want:.3f}", "-an",
             "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", part])
        parts.append(part)
        refs.append(ref)
        rows.append((sid, status, want, note))

    with open("out/parts.txt", "w") as f:
        f.writelines(f"file '{os.path.abspath(p)}'\n" for p in parts)
    run(["-f", "concat", "-safe", "0", "-i", "out/parts.txt", "-c", "copy", "out/conformed.mp4"])
    run(["-i", "out/conformed.mp4", "-vf", f"pad={W}:720:0:0:black", "-c:v", "libx264", "-crf", "16",
         "-pix_fmt", "yuv420p", "out/conformed_720.mp4"])

    with open("out/refs.txt", "w") as f:
        f.writelines(f"file '{os.path.abspath(r)}'\n" for r in refs)
    run(["-f", "concat", "-safe", "0", "-i", "out/refs.txt", "-i", "out/conformed.mp4",
         "-filter_complex", f"[0:v]fps={FPS},scale=640:310[a];[1:v]scale=640:310[b];[a][b]vstack",
         "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "out/compare.mp4"])

    total = sum(r[2] for r in rows)
    print(f"{'段':<5}{'状态':<6}{'时长':>8}  说明")
    for sid, status, want, note in rows:
        print(f"{sid:<5}{status:<6}{want:>8.3f}  {note}")
    print(f"合计 {total:.3f} s（原片正片 85.767 s）→ out/conformed.mp4, out/conformed_720.mp4, out/compare.mp4")
    if any(r[1] == "缺失" for r in rows):
        sys.exit(0)


if __name__ == "__main__":
    main()
