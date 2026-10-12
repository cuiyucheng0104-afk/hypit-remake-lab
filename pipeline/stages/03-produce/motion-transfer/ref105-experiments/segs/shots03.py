"""用 0.3 阈值切点给 S02–S09 切镜头（<3 帧的碎片并入前一镜头），出首帧总览图 segs/all_first.jpg 和草稿 segs/shots.json。"""
import json, subprocess, pathlib
from PIL import Image, ImageDraw, ImageFont
HERE = pathlib.Path(__file__).resolve().parent
EXPORT = HERE.parent / "export"
font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 18)
cuts_all = [float(l.split()[0]) for l in open(HERE.parent.parent.parent / "references/ref-105/evidence/cuts-frame-0.3.txt")]
segs = [s for s in json.load(open(EXPORT / "segments.json")) if s["id"] != "S01"]

def nframes(path):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)

plan, cells = {}, []
for s in segs:
    src = EXPORT / "refclips_sil" / f"{s['id']}.mp4"
    total = nframes(src)
    cuts = sorted({round((c - s["src_in"]) * 30) for c in cuts_all if s["src_in"] + 0.01 < c < s["src_out"] - 0.01})
    bounds = [0] + [c for c in cuts if 0 < c < total] + [total]
    shots = []
    for a, b in zip(bounds, bounds[1:]):
        if shots and b - a < 3:
            shots[-1][1] = b          # 碎片并入前一镜头
        else:
            shots.append([a, b])
    plan[s["id"]] = {"frames": total, "shots": shots}
    for i, (a, b) in enumerate(shots, 1):
        out = HERE / "_f.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"select=eq(n\\,{a + min(3, (b - a) // 2)}),scale=240:-2",
                        "-frames:v", "1", str(out)], check=True)
        im = Image.open(out).convert("RGB"); d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 170, 22), fill=(0, 0, 0)); d.text((4, 1), f"{s['id']}-{i} ({b - a}f)", font=font, fill=(255, 255, 0))
        cells.append(im)
    print(s["id"], total, len(shots))
(HERE / "shots.json").write_text(json.dumps(plan, indent=1))
cols = 8; w, h = cells[0].size; rows = (len(cells) + cols - 1) // cols
sheet = Image.new("RGB", (w * cols, h * rows))
for k, c in enumerate(cells): sheet.paste(c, ((k % cols) * w, (k // cols) * h))
sheet.save(HERE / "all_first.jpg", quality=85)
print("total shots", len(cells))
