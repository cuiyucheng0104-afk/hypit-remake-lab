"""原镜头 vs 各路线成片：按原片时间等距取帧，上下对齐拼成对照图（每行左上角标路线名）。"""
import subprocess, sys, pathlib, tempfile
from PIL import Image, ImageDraw, ImageFont
ROOT = pathlib.Path(__file__).resolve().parent
FONT = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 22)

def grab(src, t, width):
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1",
                        "-vf", f"scale={width}:-2", f.name], check=True)
        return Image.open(f.name).convert("RGB").copy()

def duration(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                                capture_output=True, text=True).stdout)

def sheet(shot, videos, n=6, width=320):
    src = ROOT / "clips" / f"{shot}.mp4"
    dur = duration(src)
    rows = []
    for label, video in [("原片", src)] + videos:
        cells = [grab(video, min(dur * (i + 0.5) / n, duration(video) - 0.02), width) for i in range(n)]
        h = max(c.height for c in cells)
        row = Image.new("RGB", (width * n, h))
        for i, c in enumerate(cells):
            row.paste(c.resize((width, int(c.height * width / c.width))), (i * width, 0))
        d = ImageDraw.Draw(row)
        d.rectangle((0, 0, 14 * len(label) + 30, 34), fill=(0, 0, 0))
        d.text((8, 4), label, font=FONT, fill=(255, 255, 255))
        rows.append(row)
    out = Image.new("RGB", (width * n, sum(r.height for r in rows)))
    y = 0
    for r in rows:
        out.paste(r, (0, y)); y += r.height
    path = ROOT / "out" / f"compare_{shot}.jpg"
    out.save(path, quality=90)
    return path

if __name__ == "__main__":
    shot = sys.argv[1]
    vids = [(pathlib.Path(p).stem.split("_")[0], pathlib.Path(p)) for p in sys.argv[2:]]
    print(sheet(shot, vids))
