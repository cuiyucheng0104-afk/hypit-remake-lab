"""按 0.12 阈值切点把 S02–S09 切成候选镜头，生成首尾帧检查图与草稿清单（segs/<段>_draft.json）。"""
import json, subprocess, sys, pathlib
from PIL import Image, ImageDraw, ImageFont
HERE = pathlib.Path(__file__).resolve().parent
EXPORT = HERE.parent / "export"
SEGS = {s["id"]: (s["src_in"], s["src_out"]) for s in json.load(open(EXPORT / "segments.json"))}
font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 18)
cands = [c["at"] for c in json.load(open(HERE.parent.parent.parent / "references/ref-105/evidence/boundaries-0.12.json"))["candidates"]]

def frames_of(path):
    return int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                               "stream=nb_read_frames", "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout)

def grab(src, n, w=240):
    out = HERE / "_tmp.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"select=eq(n\\,{n}),scale={w}:-2", "-frames:v", "1", str(out)], check=True)
    return Image.open(out).convert("RGB").copy()

for seg in sys.argv[1:]:
    a, b = SEGS[seg]
    src = EXPORT / "refclips_sil" / f"{seg}.mp4"
    total = frames_of(src)
    cuts = sorted({round((c - a) * 30) for c in cands if a + 0.01 < c < b - 0.01})
    bounds = [0] + [c for c in cuts if 0 < c < total] + [total]
    shots = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    cells = []
    for i, (s, e) in enumerate(shots, 1):
        for tag, n in (("首", s), ("尾", e - 1)):
            im = grab(src, n); d = ImageDraw.Draw(im)
            d.rectangle((0, 0, 150, 22), fill=(0, 0, 0)); d.text((4, 1), f"#{i} {tag} f{n} ({e - s})", font=font, fill=(255, 255, 0))
            cells.append(im)
    cols = 8; w, h = cells[0].size; rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows))
    for k, c in enumerate(cells): sheet.paste(c, ((k % cols) * w, (k // cols) * h))
    sheet.save(HERE / f"{seg}_shots.jpg", quality=85)
    (HERE / f"{seg}_draft.json").write_text(json.dumps({"segment": seg, "frames": total, "shots": shots}))
    print(seg, "frames", total, "candidate shots", len(shots))
