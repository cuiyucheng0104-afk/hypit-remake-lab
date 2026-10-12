"""把原镜头与各路线成片上下叠成一条同步对照视频（统一 30fps、截到原镜头长度，每行左上角贴标签）。"""
import subprocess, sys, pathlib
from PIL import Image, ImageDraw, ImageFont
ROOT = pathlib.Path(__file__).resolve().parent
FONT = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 24)
W = 640

def label(text):
    path = ROOT / "out" / f"label_{text}.png"
    im = Image.new("RGBA", (16 * len(text) + 40, 40), (0, 0, 0, 170))
    ImageDraw.Draw(im).text((10, 5), text, font=FONT, fill=(255, 255, 255, 255))
    im.save(path)
    return path

def stack(shot, rows):
    src = ROOT / "clips" / f"{shot}.mp4"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                               capture_output=True, text=True).stdout)
    inputs, filters, names = [], [], []
    for i, (text, video) in enumerate([("原片", src)] + rows):
        inputs += ["-i", str(video), "-i", str(label(text))]
        v, l = 2 * i, 2 * i + 1
        filters.append(f"[{v}:v]fps=30,trim=duration={dur:.3f},setpts=PTS-STARTPTS,scale={W}:310:force_original_aspect_ratio=decrease,"
                       f"pad={W}:310:(ow-iw)/2:(oh-ih)/2[s{i}];[s{i}][{l}:v]overlay=0:0[r{i}]")
        names.append(f"[r{i}]")
    filters.append("".join(names) + f"vstack=inputs={len(names)}[out]")
    out = ROOT / "out" / f"stack_{shot}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(filters), "-map", "[out]",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out

if __name__ == "__main__":
    shot = sys.argv[1]
    rows = [(a.split("=")[0], ROOT / a.split("=")[1]) for a in sys.argv[2:]]
    print(stack(shot, rows))
