"""Emit the pointer layer (arrows + circle) of lanv.svml from measured burned-in positions.

Source clip 392x704 is shown through a Frame scaled by S=2.395 so that the source window
v∈[0.28,0.755], u centred on 0.55 fills the 720x800 stage (y 250–1050).
canvas = (FRAME_LEFT + u*W*S, FRAME_TOP + v*H*S)
"""
W, H, S = 392, 704, 2.395
FRAME_LEFT = 360 - 0.55 * W * S
FRAME_TOP = 650 - 0.5175 * H * S

def cx(u): return FRAME_LEFT + u * W * S
def cy(v): return FRAME_TOP + v * H * S

# id, centre u, top v (min of bounce), tip v (max of bounce), start moment, end (moment or program.end), cycles
ARROWS = [
    ("menu",     .472, .270, .406, "menu",     "service",    2),
    ("service",  .584, .369, .507, "service",  "lanv",       2),
    ("lanv",     .316, .401, .538, "lanv",     "apply-say",  1),
    ("apply",    .675, .517, .658, "apply",    "choose",     2),
    ("transfer", .618, .489, .626, "transfer", "zero",       4),
    ("next",     .811, .528, .618, "account",  "qual-say",   2),
    ("qual",     .415, .344, .482, "qual",     "body-say",   2),
    ("body",     .468, .321, .459, "body",     "upload-say", 1),
    ("submit",   .398, .307, .445, "submit",   None,         2),
]
SHAFT, HEAD_W, HEAD_H, EDGE = 22, 54, 66, 6

def arrow_points(tx, ty, top, grow):
    s, hw, hh = SHAFT + grow, HEAD_W + grow, HEAD_H
    t = top - grow
    return [(tx - s, t), (tx + s, t), (tx + s, ty - hh), (tx + hw, ty - hh),
            (tx, ty + grow * 1.6), (tx - hw, ty - hh), (tx - s, ty - hh)]

def path(pid, pts):
    head, *rest = pts
    body = "".join(f'<space:Line x="{x:.1f}" y="{y:.1f}"/>' for x, y in rest)
    return f'  <space:Path id="{pid}"><space:Move x="{head[0]:.1f}" y="{head[1]:.1f}"/>{body}<space:Close/></space:Path>'

def ellipse(cx_, cy_, rx, ry, clockwise=True):
    k = 0.5523
    if clockwise:
        segs = [((cx_ + rx, cy_), (cx_ + rx, cy_ + k * ry), (cx_ + k * rx, cy_ + ry), (cx_, cy_ + ry)),
                (None, (cx_ - k * rx, cy_ + ry), (cx_ - rx, cy_ + k * ry), (cx_ - rx, cy_)),
                (None, (cx_ - rx, cy_ - k * ry), (cx_ - k * rx, cy_ - ry), (cx_, cy_ - ry)),
                (None, (cx_ + k * rx, cy_ - ry), (cx_ + rx, cy_ - k * ry), (cx_ + rx, cy_))]
    else:
        segs = [((cx_ + rx, cy_), (cx_ + rx, cy_ - k * ry), (cx_ + k * rx, cy_ - ry), (cx_, cy_ - ry)),
                (None, (cx_ - k * rx, cy_ - ry), (cx_ - rx, cy_ - k * ry), (cx_ - rx, cy_)),
                (None, (cx_ - rx, cy_ + k * ry), (cx_ - k * rx, cy_ + ry), (cx_, cy_ + ry)),
                (None, (cx_ + k * rx, cy_ + ry), (cx_ + rx, cy_ + k * ry), (cx_ + rx, cy_))]
    out = f'<space:Move x="{segs[0][0][0]:.1f}" y="{segs[0][0][1]:.1f}"/>'
    for _, c1, c2, end in segs:
        out += (f'<space:Cubic control1-x="{c1[0]:.1f}" control1-y="{c1[1]:.1f}" '
                f'control2-x="{c2[0]:.1f}" control2-y="{c2[1]:.1f}" x="{end[0]:.1f}" y="{end[1]:.1f}"/>')
    return out + "<space:Close/>"

def ring(pid, cx_, cy_, rx, ry, width):
    h = width / 2
    return (f'  <space:Path id="{pid}">' + ellipse(cx_, cy_, rx + h, ry + h, True)
            + ellipse(cx_, cy_, rx - h, ry - h, False) + "</space:Path>")

def window(start, end):
    s = f'start="moment.cue" start-source={{story.moment.{start}}}'
    e = (f'end="moment.cue" end-source={{story.moment.{end}}}' if end else 'end="program.end"')
    return f"{s} {e}"

geometry, items = [], []
for name, u, top_v, tip_v, start, end, cycles in ARROWS:
    tx, ty, top = cx(u), cy(tip_v) + 6, cy(top_v)
    edge, fill = arrow_points(tx, ty, top, EDGE), arrow_points(tx, ty, top, 0)
    xs, ys = [p[0] for p in edge], [p[1] for p in edge]
    geometry.append(f'  <!-- {name}: tip ({tx:.0f},{ty:.0f}) -->')
    geometry.append(f'  <space:Frame id="arrow-{name}-box" within={{vertical}} left="{min(xs)-4:.1f}px" '
                    f'top="{min(ys)-4:.1f}px" right="{max(xs)+4:.1f}px" bottom="{max(ys)+4:.1f}px"/>')
    geometry.append(path(f"arrow-{name}-edge", edge))
    geometry.append(path(f"arrow-{name}-fill", fill))
    motion = f"recipes.motion.pointer-{cycles}"
    for layer, paint in (("edge", "white"), ("fill", "red")):
        items.append(f'    <media-track:Item id="arrow-{name}-{layer}" frame={{arrow-{name}-box}} '
                     f'clip={{arrow-{name}-{layer}}} appearance={{recipes.media.pointer-{layer}}} '
                     f'motion={{{motion}}} {window(start, end)}>'
                     f'<media-track:Paint appearance={{recipes.paint.{paint}}}/></media-track:Item>')

# 「原先的抖音号」手绘红圈的位置：u .296–.707, v .338–.504
ccx, ccy = (cx(.296) + cx(.707)) / 2, (cy(.338) + cy(.504)) / 2
rx, ry = (cx(.707) - cx(.296)) / 2, (cy(.504) - cy(.338)) / 2
geometry.append(f'  <!-- origin circle: centre ({ccx:.0f},{ccy:.0f}) radii ({rx:.0f},{ry:.0f}) -->')
geometry.append(f'  <space:Frame id="circle-origin-box" within={{vertical}} left="{ccx-rx-20:.1f}px" '
                f'top="{ccy-ry-20:.1f}px" right="{ccx+rx+20:.1f}px" bottom="{ccy+ry+20:.1f}px"/>')
geometry.append(ring("circle-origin-edge", ccx, ccy, rx, ry, 22))
geometry.append(ring("circle-origin-fill", ccx, ccy, rx, ry, 12))
for layer, paint in (("edge", "white"), ("fill", "red")):
    items.append(f'    <media-track:Item id="circle-origin-{layer}" frame={{circle-origin-box}} '
                 f'clip={{circle-origin-{layer}}} appearance={{recipes.media.pointer-{layer}}} '
                 f'motion={{recipes.motion.circle}} {window("origin", "qual-say")}>'
                 f'<media-track:Paint appearance={{recipes.paint.{paint}}}/></media-track:Item>')

demo_frame = (FRAME_LEFT, FRAME_TOP, FRAME_LEFT + W * S, FRAME_TOP + H * S)
print("<!-- GEOMETRY -->")
print(f'  <space:Frame id="demo-frame" within={{vertical}} left="{demo_frame[0]:.1f}px" '
      f'top="{demo_frame[1]:.1f}px" right="{demo_frame[2]:.1f}px" bottom="{demo_frame[3]:.1f}px"/>')
print("\n".join(geometry))
print("<!-- ITEMS -->")
print("\n".join(items))
