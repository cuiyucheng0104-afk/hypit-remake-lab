"""S01 首帧精修流水线：Qwen-Image-Edit 2511 精修每个镜头的首帧 → Bernini 以精修帧为参考把改动传播到整个镜头 → 按原切点拼回。

usage:
  pipeline.py prepare          切镜头（补到 4n+1 帧）、抽首帧
  pipeline.py frames [ids…]    提交首帧精修，取回 s01/edited/<id>.png
  pipeline.py videos [ids…]    提交 Bernini 传播，取回 s01/out/<id>.mp4
  pipeline.py assemble         截回原长度、按顺序拼接，出对照
"""
import copy, json, pathlib, subprocess, sys, time, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "trial"))
from comfy import call, upload, submit, wait, fetch_videos  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
TRIAL = HERE.parent / "trial"
CHARS = HERE.parent / "export" / "characters"
SOURCE = HERE.parent / "export" / "refclips_sil" / "S01.mp4"
HERO, HENCH, SCENE = CHARS / "图片1_主角.jpg", CHARS / "图片3_配角群.jpg", CHARS / "图片4_场景.jpg"

HERO_DESC = "束发髻、不戴斗笠、穿黑色暗纹刺绣长袍的男子"
HENCH_DESC = "戴竹编斗笠、穿黑色劲装的刺客"
SCENE_DESC = "夜晚下大雨：建筑保留原有的结构和位置，只改为深色木质门窗与回廊，地面是湿漉漉反光的青石板"
HERO_FACE, HERO_FULL = HERE / "hero_face.png", TRIAL / "clips" / "hero_front_full.png"

# 镜头：id、起止帧（原片帧号，终点不含）、类别、景别（精修时要求保持）
SHOTS = [
    ("A", 0, 27, "hero", "人物胸像中近景，人物居中"), ("B", 27, 42, "hench", "多人侧脸近景，前景人物很大且虚焦"),
    ("C", 42, 66, "hench", "高角度俯拍的人群全景"), ("D", 66, 88, "hero", "面部特写，脸部占满画面右半"),
    ("E", 88, 104, "hand", "手握剑柄的局部特写"), ("F", 104, 114, "hero", "从正上方垂直俯拍，只看到头顶和肩"),
    ("G", 114, 128, "both", "前景是人群背影，远处中间站着主角"), ("H", 128, 135, "hench", "昏暗的动态模糊局部"),
    ("I", 135, 147, "hench", "冲锋人群的中近景"), ("J", 147, 161, "hero", "面部特写，脸部占满画面"),
    ("K", 161, 171, "hand", "手握剑的局部特写"), ("L", 171, 191, "both", "低机位全景，人群奔跑"),
    ("M", 191, 249, "both", "快速横移的动态模糊中景"),
]
KEEP_TMPL = ("不要改变画面构图：景别保持为{framing}，机位、镜头角度、人物大小、人物数量、每个人的姿势、朝向和位置都与图1完全相同，"
             "只修改人物外观与场景材质。画面中不出现文字和水印。")


def plan(kind, sid=None):
    """每类镜头：(Qwen 的参考图, 精修指令, Bernini 附加参考图, 传播时的外观说明)"""
    if kind == "hero":
        ref = HERO_FULL if sid == "F" else HERO_FACE
        return ([ref], f"把图1中戴斗笠、穿浅蓝色长袍的男子换成图2中的男子（{HERO_DESC}），面容、发型和服装与图2一致；"
                f"背景改为{SCENE_DESC}。", [HERO_FACE], f"主角是图2中的男子（{HERO_DESC}），场景是{SCENE_DESC}")
    if kind == "hand":
        return ([HERO_FACE], f"把图1中浅蓝色的衣袖和衣服改为图2男子的黑色暗纹刺绣长袍衣料，手和剑保持不变；背景改为{SCENE_DESC}。",
                [HERO_FACE], f"衣袖是图2男子的黑色暗纹刺绣长袍，场景是{SCENE_DESC}")
    if kind == "hench":
        return ([HENCH], f"把图1中所有穿黑衣的人换成图2中的刺客（{HENCH_DESC}），每个人都戴竹编斗笠；背景改为{SCENE_DESC}。",
                [HENCH], f"所有敌人都是图2中的刺客（{HENCH_DESC}），场景是{SCENE_DESC}")
    return ([HERO_FULL, HENCH], f"把图1中戴斗笠、穿浅蓝色长袍的男子换成图2中的男子（{HERO_DESC}）；"
            f"把图1中其余所有穿黑衣的人换成图3中的刺客（{HENCH_DESC}），每个人都戴竹编斗笠；背景改为{SCENE_DESC}。",
            [HERO_FACE, HENCH], f"主角是图2中的男子（{HERO_DESC}），所有敌人都是图3中的刺客（{HENCH_DESC}），场景是{SCENE_DESC}")


def padded(n):
    return n if n % 4 == 1 else n + (1 - n) % 4


def prepare():
    (HERE / "clips").mkdir(exist_ok=True); (HERE / "first").mkdir(exist_ok=True)
    for sid, a, b, *_ in SHOTS:
        n, m = b - a, padded(b - a)
        # 末帧重复补齐到 4n+1（Bernini 帧数要求），生成后再截回
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SOURCE), "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                        "-vf", f"select=between(n\\,{a}\\,{b - 1}),setpts=N/30/TB,tpad=stop_mode=clone:stop={m - n}",
                        "-map", "0:v", "-map", "1:a", "-frames:v", str(m), "-r", "30", "-c:v", "libx264", "-crf", "12",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(HERE / "clips" / f"{sid}.mp4")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SOURCE), "-vf", f"select=eq(n\\,{a})", "-frames:v", "1",
                        str(HERE / "first" / f"{sid}.png")], check=True)
        print(sid, n, "→", m)


LOCAL_SCENE = "背景保持原画面的建筑、门窗和布局不变，只把光线调成夜晚下大雨的冷色调"


def qwen_graph(sid, kind, framing):
    refs, instruction, _, _ = plan(kind, sid)
    if "--local" in sys.argv:  # 只换人、不重画背景，构图更稳
        instruction = instruction.replace(f"背景改为{SCENE_DESC}", LOCAL_SCENE)
    base = json.load(open(TRIAL / "workflows" / "Y01_qwenedit_api.json"))
    p = copy.deepcopy(base)
    p.pop("2", None)  # 提示音
    p["25"]["inputs"]["image"] = upload(HERE / "first" / f"{sid}.png", "ref105s01")
    for i, ref in enumerate(refs):
        node = str(40 + i)
        p[node] = {"class_type": "LoadImage", "inputs": {"image": upload(ref, "ref105s01")}}
        for enc in ("9", "11"):
            p[enc]["inputs"][f"image{i + 2}"] = [node, 0]
    p["11"]["inputs"]["prompt"] = instruction + KEEP_TMPL.format(framing=framing)
    p["32"]["inputs"]["seed"] = 20260929
    p["35"]["inputs"]["filename_prefix"] = f"ref105s01/first_{sid}"
    return p


def fetch_image(entry, target):
    for output in entry.get("outputs", {}).values():
        for item in output.get("images", []):
            if item.get("type") == "output":
                q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""), "type": "output"})
                target.write_bytes(call(f"/view?{q}", timeout=300))
                return target
    raise SystemExit(f"no image output for {target.name}")


def bernini_graph(sid, kind, frames):
    _, _, extra_refs, look = plan(kind, sid)
    p = copy.deepcopy(json.load(open(TRIAL / "workflows" / "K08_bernini_api.json")))
    p["123"]["inputs"]["value"] = 960
    p["124"]["inputs"]["value"] = 480
    p["125"]["inputs"]["value"] = frames
    p["268"]["inputs"].update({"video": upload(HERE / "clips" / f"{sid}.mp4", "ref105s01"), "force_rate": 30, "frame_load_cap": frames})
    bern = p["329"]["inputs"]
    bern["task_type"] = "rv2v"
    for i in range(1, 11):
        bern.pop(f"reference_image_{i}", None)
    refs = [HERE / "chosen" / f"{sid}.png"] + extra_refs
    slots = ["319", "305", "307"]
    for i, (slot, ref) in enumerate(zip(slots, refs), start=1):
        p[slot]["inputs"]["image"] = upload(ref, "ref105s01")
        bern[f"reference_image_{i}"] = [slot, 0]
    for slot in slots[len(refs):]:
        p.pop(slot)
    p.pop("313", None); p.pop("315", None)
    p["261"]["inputs"]["positive_prompt"] = (
        "You are a helpful assistant specialized in video editing on content propagation.\n"
        f"图1是这个视频第一帧的编辑结果。把图1的修改传播到整个视频：{look}。"
        "每一帧的人物外观、服装、发型和场景都与图1保持一致；人物的动作、位置、机位、镜头运动、构图和节奏与原视频完全一致，保留雨水和水花。")
    p["261"]["inputs"]["negative_prompt"] = "画面模糊，人物变形，多余的手指，重影，字幕，水印，静止画面，浅蓝色长袍，草帽"
    p["136"]["inputs"].update({"frame_rate": 30, "filename_prefix": f"ref105s01/shot_{sid}"})
    return p


def run_stage(stage, ids):
    ids = [i for i in ids if not i.startswith("--")]
    todo = [s for s in SHOTS if not ids or s[0] in ids]
    jobs = []
    for sid, a, b, kind, framing in todo:
        graph = qwen_graph(sid, kind, framing) if stage == "frames" else bernini_graph(sid, kind, padded(b - a))
        pid = submit(graph)
        jobs.append((sid, pid, time.time()))
        print("submitted", stage, sid, pid, flush=True)
    for d in ("edited", "edited_local", "out"):
        (HERE / d).mkdir(exist_ok=True)
    for sid, pid, started in jobs:
        try:
            entry = wait(pid, poll=5)
            if stage == "frames":
                result = fetch_image(entry, HERE / ("edited_local" if "--local" in sys.argv else "edited") / f"{sid}.png")
            else:
                saved = fetch_videos(entry, f"s01_{sid}")
                result = HERE / "out" / f"{sid}.mp4"
                pathlib.Path(saved[0]).replace(result)
            print("done", stage, sid, f"{time.time() - started:.0f}s", result, flush=True)
        except BaseException as error:
            print("FAILED", stage, sid, str(error)[:1200], flush=True)


def assemble():
    parts = []
    for sid, a, b, *_ in SHOTS:
        swapped = HERE / "faceswap" / f"{sid}.mp4"   # 有换脸版就用换脸版
        out = swapped if swapped.exists() else HERE / "out" / f"{sid}.mp4"
        trimmed = HERE / "out" / f"{sid}_trim.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", f"trim=end_frame={b - a},setpts=PTS-STARTPTS,fps=30",
                        "-an", "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(trimmed)], check=True)
        parts.append(trimmed)
    listing = HERE / "out" / "concat.txt"
    listing.write_text("".join(f"file '{p}'\n" for p in parts))
    final = HERE / (sys.argv[2] if len(sys.argv) > 2 else "S01_remake.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(final)], check=True)
    compare = final.with_name(final.stem + "_compare.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SOURCE), "-i", str(final), "-filter_complex",
                    "[0:v]scale=960:-2,setsar=1[a];[1:v]scale=960:-2,setsar=1[b];[a][b]vstack=inputs=2[v]",
                    "-map", "[v]", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(compare)], check=True)
    print(final, compare)


if __name__ == "__main__":
    cmd, ids = sys.argv[1], sys.argv[2:]
    {"prepare": lambda: prepare(), "assemble": lambda: assemble()}.get(cmd, lambda: run_stage(cmd, ids))()
