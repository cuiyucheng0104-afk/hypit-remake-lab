"""换脸检查图：左侧参考脸，右侧每个镜头三行（原片 / 换脸前 / 换脸后），各取三帧。"""
import subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont
font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 22)

def grab(src, t, w=320):
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-vf", f"scale={w}:-2", f.name], check=True)
        return Image.open(f.name).convert("RGB").copy()

def duration(src):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, text=True).stdout)

def sheet(sid, out):
    w, h = 320, 160
    dur = min(duration(f"out/{sid}.mp4"), duration(f"faceswap/{sid}.mp4"))
    ts = [dur * 0.1, dur * 0.5, dur * 0.85]
    rows = [("原片", f"clips/{sid}.mp4"), ("换脸前", f"out/{sid}.mp4"), ("换脸后", f"faceswap/{sid}.mp4")]
    ref = Image.open("hero_face.png").convert("RGB"); ref = ref.resize((int(ref.width * h * 3 / ref.height), h * 3))
    img = Image.new("RGB", (ref.width + 6 + w * 3, h * 3), "white"); img.paste(ref, (0, 0))
    d = ImageDraw.Draw(img)
    for r, (label, src) in enumerate(rows):
        for c, t in enumerate(ts):
            img.paste(grab(src, t, w).resize((w, h)), (ref.width + 6 + c * w, r * h))
        d.rectangle((ref.width + 6, r * h, ref.width + 130, r * h + 30), fill=(0, 0, 0))
        d.text((ref.width + 12, r * h + 2), f"{sid} {label}", font=font, fill=(255, 255, 0))
    img.save(out, quality=90)

if __name__ == "__main__":
    for sid in sys.argv[1:]:
        sheet(sid, f"faceswap_{sid}_check.jpg"); print(f"faceswap_{sid}_check.jpg")
