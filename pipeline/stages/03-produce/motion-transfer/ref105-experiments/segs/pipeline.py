"""S02–S09 流水线（沿用 S01 的方法）：首帧精修（只换人、背景调成雨夜）→ Bernini 传播 → 主角近景换脸 → 拼接。

镜头计划在 segs/plan.json（0.3 阈值切点，碎片并入前一镜头；kinds 为人工分类）。镜头 id 形如 S02-3。
usage:
  pipeline.py prepare [段…]            切镜头（补到 4n+1 帧）、抽首帧
  pipeline.py frames [段或镜头…]        首帧精修 → segs/<段>/edited/<id>.png
  pipeline.py videos [段或镜头…]        Bernini 传播 → segs/<段>/out/<id>.mp4
  pipeline.py faceswap [段或镜头…]      主角近景换脸（kind=hero）→ segs/<段>/faceswap/<id>.mp4
  pipeline.py assemble                 每段拼接 + 全片（接 S01 最终版）+ 对照
"""
import copy, json, pathlib, subprocess, sys, time, urllib.parse
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "trial"))
from comfy import call, upload, submit, wait, fetch_videos  # noqa: E402

WF = ROOT / "trial" / "workflows"
EXPORT = ROOT / "export"
PLAN = json.load(open(HERE / "plan.json"))
HERO_FACE, HERO_FULL = ROOT / "s01" / "hero_face.png", ROOT / "trial" / "clips" / "hero_front_full.png"
HENCH, BOSS_FACE = EXPORT / "characters" / "图片3_配角群.jpg", HERE / "boss_face.png"

HERO_DESC = "束发髻、不戴斗笠、穿黑色暗纹刺绣长袍的男子"
HENCH_DESC = "戴竹编斗笠、穿黑色劲装的刺客"
BOSS_DESC = "头戴黑色斗笠、穿黑色刺绣长袍的中年男子"
SCENE = "背景保持原画面的建筑、门窗和布局不变，只把光线调成夜晚下大雨的冷色调"
KEEP = ("不要改变画面构图：景别、机位、镜头角度、人物大小、人物数量、每个人的姿势、朝向、位置和动作都与图1完全相同，"
        "只修改人物外观。画面中不出现文字和水印。")


def shots(selectors=()):
    """展开 (段, 镜头id, 起, 止, 类别)；selectors 可以是段名或镜头 id（-- 开头的是选项，忽略）。"""
    selectors = [x for x in selectors if not x.startswith("--")]
    out = []
    for seg, info in PLAN.items():
        for i, ((a, b), kind) in enumerate(zip(info["shots"], info["kinds"]), 1):
            sid = f"{seg}-{i}"
            if not selectors or seg in selectors or sid in selectors:
                out.append((seg, sid, a, b, kind))
    return out


def d(seg, name):
    path = HERE / seg / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def padded(n):
    return n if n % 4 == 1 else n + (1 - n) % 4


def plan(kind):
    """(Qwen 参考图, 精修指令, Bernini 附加参考图, 传播时的外观说明)"""
    if kind == "hero":
        return ([HERO_FACE], f"把图1中戴斗笠、穿浅蓝色长袍的男子换成图2中的男子（{HERO_DESC}），面容、发型和服装与图2一致；{SCENE}。",
                [HERO_FACE], f"主角是图2中的男子（{HERO_DESC}）")
    if kind == "hand":
        return ([HERO_FACE], f"把图1中浅蓝色的衣袖和衣服改为图2男子的黑色暗纹刺绣长袍衣料，手和剑保持不变；{SCENE}。",
                [HERO_FACE], f"衣袖是图2男子的黑色暗纹刺绣长袍")
    if kind == "hench":
        return ([HENCH], f"把图1中所有穿黑衣的人换成图2中的刺客（{HENCH_DESC}），每个人都戴竹编斗笠；{SCENE}。",
                [HENCH], f"所有敌人都是图2中的刺客（{HENCH_DESC}）")
    if kind == "boss":
        return ([BOSS_FACE], f"把图1中穿黑衣的敌人换成图2中的男子（{BOSS_DESC}），面容与图2一致；{SCENE}。",
                [BOSS_FACE], f"敌人是图2中的头目（{BOSS_DESC}）")
    return ([HERO_FULL, HENCH], f"把图1中戴斗笠、穿浅蓝色长袍的男子换成图2中的男子（{HERO_DESC}）；"
            f"把图1中其余所有穿黑衣的人换成图3中的刺客（{HENCH_DESC}），每个人都戴竹编斗笠；{SCENE}。",
            [HERO_FACE, HENCH], f"主角是图2中的男子（{HERO_DESC}），所有敌人都是图3中的刺客（{HENCH_DESC}）")


def prepare(selectors):
    for seg, sid, a, b, _ in shots(selectors):
        src = EXPORT / "refclips_sil" / f"{seg}.mp4"
        n, m = b - a, padded(b - a)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-vf", f"select=between(n\\,{a}\\,{b - 1}),setpts=N/30/TB,tpad=stop_mode=clone:stop={m - n}",
                        "-map", "0:v", "-map", "1:a", "-frames:v", str(m), "-r", "30", "-c:v", "libx264", "-crf", "12",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d(seg, "clips") / f"{sid}.mp4")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"select=eq(n\\,{a})", "-frames:v", "1",
                        str(d(seg, "first") / f"{sid}.png")], check=True)
    print("prepared", len(shots(selectors)), "shots")


def qwen_graph(seg, sid, kind):
    refs, instruction, _, _ = plan(kind)
    p = copy.deepcopy(json.load(open(WF / "Y01_qwenedit_api.json")))
    p.pop("2", None)
    p["25"]["inputs"]["image"] = upload(HERE / seg / "first" / f"{sid}.png", "ref105segs")
    for i, ref in enumerate(refs):
        node = str(40 + i)
        p[node] = {"class_type": "LoadImage", "inputs": {"image": upload(ref, "ref105segs")}}
        for enc in ("9", "11"):
            p[enc]["inputs"][f"image{i + 2}"] = [node, 0]
    p["11"]["inputs"]["prompt"] = instruction + KEEP
    p["32"]["inputs"]["seed"] = 20260930
    p["35"]["inputs"]["filename_prefix"] = f"ref105segs/first_{sid}"
    return p


def bernini_graph(seg, sid, kind, frames):
    _, _, extra, look = plan(kind)
    p = copy.deepcopy(json.load(open(WF / "K08_bernini_api.json")))
    p["123"]["inputs"]["value"], p["124"]["inputs"]["value"], p["125"]["inputs"]["value"] = 960, 480, frames
    p["268"]["inputs"].update({"video": upload(HERE / seg / "clips" / f"{sid}.mp4", "ref105segs"), "force_rate": 30, "frame_load_cap": frames})
    bern = p["329"]["inputs"]
    bern["task_type"] = "rv2v"
    for i in range(1, 11):
        bern.pop(f"reference_image_{i}", None)
    chosen = HERE / seg / "chosen" / f"{sid}.png"
    if "--refonly" in sys.argv:   # 对照版：不用首帧，只按参考图改原片
        chosen = HERE / "__none__.png"
    # 首帧精修失败的镜头（多为拖影/抽象画面）不用首帧，直接按参考图编辑原片（T2/T3 验证过的做法）
    refs = ([chosen] if chosen.exists() else []) + extra
    slots = ["319", "305", "307"]
    for i, (slot, ref) in enumerate(zip(slots, refs), start=1):
        p[slot]["inputs"]["image"] = upload(ref, "ref105segs")
        bern[f"reference_image_{i}"] = [slot, 0]
    for slot in slots[len(refs):]:
        p.pop(slot)
    p.pop("313", None); p.pop("315", None)
    if chosen.exists():
        p["261"]["inputs"]["positive_prompt"] = (
            "You are a helpful assistant specialized in video editing on content propagation.\n"
            f"图1是这个视频第一帧的编辑结果。把图1的修改传播到整个视频：{look}，场景是夜晚下大雨的院落。"
            "每一帧的人物外观、服装、发型和场景都与图1保持一致；人物的动作、位置、机位、镜头运动、构图和节奏与原视频完全一致，保留雨水和水花。")
    else:
        look = look.replace("图3", "图2").replace("图2中的男子", "图1中的男子") if len(extra) > 1 else look.replace("图2", "图1")
        p["261"]["inputs"]["positive_prompt"] = (
            "You are a helpful assistant specialized in video editing with reference.\n"
            f"按参考图修改视频中的人物：{look}；穿浅蓝色长袍、戴斗笠的主角不再戴斗笠。场景改为夜晚下大雨的院落。"
            "人物的动作、位置、机位、镜头运动、构图和节奏与原视频完全一致，保留雨水和水花。")
    p["261"]["inputs"]["negative_prompt"] = "画面模糊，人物变形，多余的手指，重影，字幕，水印，静止画面，浅蓝色长袍，草帽"
    p["136"]["inputs"].update({"frame_rate": 30, "filename_prefix": f"ref105segs/shot_{sid}"})
    return p


def faceswap_graph(seg, sid, frames):
    p = copy.deepcopy(json.load(open(WF / "K01_headswap_api.json")))
    p["2"]["inputs"].pop("compile_args", None)   # 关掉即时编译：S01-M 曾在编译处卡死
    p.pop("3", None)
    p["14"]["inputs"].update({"video": upload(HERE / seg / "out" / f"{sid}.mp4", "ref105segs"), "force_rate": 30, "skip_first_frames": 0})
    p["15"]["inputs"]["value"], p["16"]["inputs"]["value"], p["22"]["inputs"]["value"] = 960, 480, frames
    p["35"]["inputs"]["image"] = upload(HERO_FACE, "ref105segs")
    p["36"]["inputs"]["keep_proportion"] = "pad"
    p["91"]["inputs"]["positive_prompt"] = "束发髻的男子，面容与参考图完全一致，神情冷峻，雨夜"
    p["110"]["inputs"].update({"frame_rate": 30, "filename_prefix": f"ref105segs/headswap_{sid}"})
    return p


def fetch_image(entry, target):
    for output in entry.get("outputs", {}).values():
        for item in output.get("images", []):
            if item.get("type") == "output":
                q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": "output"})
                target.write_bytes(call(f"/view?{q}", timeout=300))
                return target
    raise RuntimeError(f"no image output for {target.name}")


def run(stage, selectors):
    todo = shots(selectors)
    if stage == "faceswap":
        todo = [s for s in todo if s[4] == "hero"]
    jobs = []
    for seg, sid, a, b, kind in todo:
        if stage == "frames":
            graph = qwen_graph(seg, sid, kind)
        elif stage == "videos":
            graph = bernini_graph(seg, sid, kind, padded(b - a))
        else:
            graph = faceswap_graph(seg, sid, padded(b - a))
        pid = submit(graph)
        jobs.append((seg, sid, pid, time.time()))
        print("submitted", stage, sid, pid, flush=True)
    for seg, sid, pid, started in jobs:
        try:
            entry = wait(pid, poll=5)
            if stage == "frames":
                result = fetch_image(entry, d(seg, "edited") / f"{sid}.png")
            else:
                saved = fetch_videos(entry, f"segs_{stage}{'_ro' if '--refonly' in sys.argv else ''}_{sid}")
                node = "_n110.mp4" if stage == "faceswap" else "_n136.mp4"
                folder = ("out_refonly" if "--refonly" in sys.argv else "out") if stage == "videos" else "faceswap"
                target = d(seg, folder) / f"{sid}.mp4"
                pathlib.Path([s for s in saved if s.endswith(node)][0]).replace(target)
                result = target
            print("done", stage, sid, f"{time.time() - started:.0f}s", result, flush=True)
        except BaseException as error:
            print("FAILED", stage, sid, str(error)[:1200], flush=True)


# 逐镜头指定来源（质检后填写）：refonly = 用「原片+参考图」对照版；source = 生成失败，用原片调成雨夜冷色占位
OVERRIDES = json.load(open(HERE / "overrides.json")) if (HERE / "overrides.json").exists() else {}
NIGHT_GRADE = "scale=960:480,eq=brightness=-0.12:saturation=0.75:gamma_b=1.15"


def trimmed(seg, sid, n):
    choice = OVERRIDES.get(sid)
    swapped = HERE / seg / "faceswap" / f"{sid}.mp4"
    if choice == "source":
        src, grade = HERE / seg / "clips" / f"{sid}.mp4", NIGHT_GRADE + ","
    elif choice == "refonly":
        src, grade = HERE / seg / "out_refonly" / f"{sid}.mp4", ""
    else:
        src, grade = (swapped if swapped.exists() else HERE / seg / "out" / f"{sid}.mp4"), ""
    out = d(seg, "trim") / f"{sid}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", f"{grade}trim=end_frame={n},setpts=PTS-STARTPTS,fps=30,scale=960:480",
                    "-an", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(out)], check=True)
    return out


def concat(parts, target):
    listing = target.with_suffix(".txt")
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target)], check=True)
    return target


def stack(top, bottom, target):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(top), "-i", str(bottom), "-filter_complex",
                    "[0:v]scale=960:-2,setsar=1[a];[1:v]scale=960:-2,setsar=1[b];[a][b]vstack=inputs=2[v]",
                    "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(target)], check=True)


def assemble():
    segments = []
    for seg in PLAN:
        parts = [trimmed(seg, sid, b - a) for _, sid, a, b, _ in shots([seg])]
        segments.append(concat(parts, HERE / f"{seg}_remake.mp4"))
        stack(EXPORT / "refclips_sil" / f"{seg}.mp4", segments[-1], HERE / f"{seg}_compare.mp4")
    full = concat([ROOT / "s01" / "S01_final_v2.mp4"] + segments, HERE / "ref105_full_remake.mp4")
    source = concat([EXPORT / "refclips_sil" / f"S0{i}.mp4" for i in range(1, 10)], HERE / "ref105_source_concat.mp4")
    stack(source, full, HERE / "ref105_full_compare.mp4")
    print(full)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "prepare":
        prepare(args)
    elif cmd == "assemble":
        assemble()
    else:
        run(cmd, args)
