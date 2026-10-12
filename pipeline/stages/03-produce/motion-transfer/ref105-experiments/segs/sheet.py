"""首帧检查图：每格左原首帧、右精修结果，按段分页。"""
import json, sys, pathlib
from PIL import Image, ImageDraw, ImageFont
HERE = pathlib.Path(__file__).resolve().parent
PLAN = json.load(open(HERE / "plan.json"))
font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 18)
W = 240
def page(segs, out, folder="edited"):
    cells = []
    for seg in segs:
        for i, kind in enumerate(PLAN[seg]["kinds"], 1):
            sid = f"{seg}-{i}"
            a = Image.open(HERE / seg / "first" / f"{sid}.png").convert("RGB")
            p = HERE / seg / folder / f"{sid}.png"
            b = Image.open(p).convert("RGB") if p.exists() else Image.new("RGB", a.size, "red")
            a = a.resize((W, int(a.height * W / a.width))); b = b.resize((W, int(b.height * W / b.width)))
            c = Image.new("RGB", (W * 2 + 4, max(a.height, b.height)), "white"); c.paste(a, (0, 0)); c.paste(b, (W + 4, 0))
            dr = ImageDraw.Draw(c); dr.rectangle((0, 0, 150, 22), fill=(0, 0, 0)); dr.text((4, 1), f"{sid} {kind}", font=font, fill=(255, 255, 0))
            cells.append(c)
    cols = 4; w = cells[0].width; h = max(c.height for c in cells); rows = (len(cells) + cols - 1) // cols
    img = Image.new("RGB", (w * cols + 8 * (cols - 1), (h + 4) * rows), "white")
    for k, c in enumerate(cells): img.paste(c, ((k % cols) * (w + 8), (k // cols) * (h + 4)))
    img.save(out, quality=85); print(out, len(cells))
if __name__ == "__main__":
    page(["S02", "S03", "S04"], HERE / "review_1.jpg")
    page(["S05", "S06", "S07", "S08", "S09"], HERE / "review_2.jpg")
