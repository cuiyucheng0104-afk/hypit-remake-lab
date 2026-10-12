"""成片质检图：每个镜头一行，左原片、右成片，各取两帧（25% / 70%）。"""
import json, subprocess, sys, tempfile, pathlib
from PIL import Image, ImageDraw, ImageFont
HERE = pathlib.Path(__file__).resolve().parent
PLAN = json.load(open(HERE / "plan.json"))
font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 18)
W, H = 240, 120

def grab(src, n):
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"select=eq(n\\,{n}),scale={W}:{H}", "-frames:v", "1", f.name], check=True)
        return Image.open(f.name).convert("RGB").copy()

def page(segs, out):
    rows = []
    for seg in segs:
        for i, ((a, b), kind) in enumerate(zip(PLAN[seg]["shots"], PLAN[seg]["kinds"]), 1):
            sid = f"{seg}-{i}"; res = HERE / seg / "out" / f"{sid}.mp4"
            if not res.exists():
                continue
            n = b - a; picks = [int(n * 0.25), int(n * 0.7)]
            row = Image.new("RGB", (W * 4 + 12, H), "white")
            for k, f in enumerate(picks):
                row.paste(grab(HERE / seg / "clips" / f"{sid}.mp4", f), (k * (2 * W + 12), 0))
                row.paste(grab(res, f), (k * (2 * W + 12) + W, 0))
            d = ImageDraw.Draw(row); d.rectangle((0, 0, 140, 22), fill=(0, 0, 0)); d.text((4, 1), f"{sid} {kind}", font=font, fill=(255, 255, 0))
            rows.append(row)
    cols = 2; w = rows[0].width; nrows = (len(rows) + 1) // 2
    img = Image.new("RGB", (w * cols + 16, (H + 4) * nrows), "white")
    for k, r in enumerate(rows): img.paste(r, ((k % cols) * (w + 16), (k // cols) * (H + 4)))
    img.save(out, quality=85); print(out, len(rows))

if __name__ == "__main__":
    page(sys.argv[2:], HERE / sys.argv[1])
