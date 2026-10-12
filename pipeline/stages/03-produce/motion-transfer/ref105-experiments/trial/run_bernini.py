"""路线 3：Bernini rv2v —— 以原镜头为编辑底，按参考图换人换景。

usage: run_bernini.py <shot-name> [--submit-only]
"""
import copy, json, sys, time
from comfy import ROOT, CHARS, upload, submit, wait, fetch_videos

SHOTS = {
    # 名称: (帧数, 参考图, 提示词)
    "T1_S07_hero": (45, ["图片1_主角.jpg", "图片4_场景.jpg"],
        "将视频中戴斗笠、穿浅蓝色长袍的男子替换为图1中的男子：头顶束发髻，不戴斗笠，黑色暗纹刺绣长袍，面容与图1完全一致。"
        "把背景替换为图2的雨夜院落：木质回廊、湿漉漉的青石地面、夜色与大雨。"
        "人物的动作、神情变化、机位、镜头运动和构图与原视频完全一致，保留雨水。"),
    "T2_S03_group": (57, ["图片1_主角.jpg", "图片3_配角群.jpg", "图片4_场景.jpg"],
        "将视频中戴斗笠、穿浅蓝色长袍的主角替换为图1中的男子：头顶束发髻，不戴斗笠，黑色暗纹刺绣长袍，面容与图1一致。"
        "将视频中其余所有穿黑衣的敌人替换为图2中戴竹编斗笠、黑色劲装、持刀的刺客。"
        "把整个场景替换为图3的雨夜院落：木质回廊、湿漉漉的青石地面、夜色与大雨。"
        "每个人的动作、站位、出招时机，以及机位、镜头运动和构图都与原视频完全一致，保留雨水和水花。"),
    "T3_S04_spin": (73, ["图片1_主角.jpg", "图片3_配角群.jpg", "图片4_场景.jpg"],
        "将视频中穿浅蓝色长袍的主角替换为图1中的男子：头顶束发髻，不戴斗笠，黑色暗纹刺绣长袍，面容与图1一致。"
        "将视频中其余所有穿黑衣的敌人替换为图2中戴竹编斗笠、黑色劲装、持刀的刺客。"
        "把整个场景替换为图3的雨夜院落：木质回廊、湿漉漉的青石地面、夜色与大雨。"
        "主角旋身穿过人群的动作、每个敌人的动作与倒地时机，以及机位、镜头运动和构图都与原视频完全一致，保留雨水和水花。"),
}
SYSTEM = "You are a helpful assistant specialized in video editing with reference.\n"
REF_SLOTS = ["319", "305", "307"]  # reference_image_1..3 对应的 LoadImage 节点


def build(shot):
    frames, refs, instruction = SHOTS[shot]
    base = json.load(open(ROOT / "workflows" / "K08_bernini_api.json"))
    p = copy.deepcopy(base)
    video = upload(ROOT / "clips" / f"{shot}.mp4")
    p["123"]["inputs"]["value"] = 960   # 宽
    p["124"]["inputs"]["value"] = 480   # 高（原片 1280×620，居中裁 1.5%）
    p["125"]["inputs"]["value"] = frames
    p["268"]["inputs"].update({"video": video, "force_rate": 30, "frame_load_cap": frames})
    bern = p["329"]["inputs"]
    bern["task_type"] = "rv2v"
    for i in range(1, 11):
        bern.pop(f"reference_image_{i}", None)
    for i, (slot, ref) in enumerate(zip(REF_SLOTS, refs), start=1):
        p[slot]["inputs"]["image"] = upload(CHARS / ref)
        bern[f"reference_image_{i}"] = [slot, 0]
    for slot in REF_SLOTS[len(refs):]:
        p.pop(slot)
    # 没用到的参考视频加载器
    p.pop("313", None); p.pop("315", None)
    p["261"]["inputs"]["positive_prompt"] = SYSTEM + instruction
    p["261"]["inputs"]["negative_prompt"] = "画面模糊，人物变形，多余的手指，重影，字幕，水印，静止画面"
    p["136"]["inputs"].update({"frame_rate": 30, "filename_prefix": f"ref105trial/bernini_{shot}"})
    return p


if __name__ == "__main__":
    shot = sys.argv[1]
    prompt = build(shot)
    (ROOT / "workflows" / f"bernini_{shot}.json").write_text(json.dumps(prompt, ensure_ascii=False, indent=1))
    started = time.time()
    pid = submit(prompt)
    print("submitted", shot, pid, flush=True)
    if "--submit-only" in sys.argv:
        sys.exit(0)
    entry = wait(pid)
    print("done", shot, f"{time.time() - started:.0f}s", fetch_videos(entry, f"bernini_{shot}"), flush=True)
