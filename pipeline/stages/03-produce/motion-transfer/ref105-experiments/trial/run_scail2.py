"""路线 2：SCAIL-2 —— SAM3 追踪人物、按颜色绑定参考身份，按原片动作重画。

T1 用动画模式（人和背景都换，背景给场景图）；T2/T3 用替换模式（只换被追踪的主角，原场景与其他人保留）。
usage: run_scail2.py <shot-name>
"""
import copy, json, sys, time
from comfy import ROOT, CHARS, upload, submit, wait, fetch_videos

SHOTS = {
    # 名称: (帧数, 动画模式?, 追踪提示词, 画面描述)
    "T1_S07_hero": (45, True, "man wearing a straw hat",
        "雨夜院落中，束发髻、身穿黑色暗纹刺绣长袍的年轻男子正面近景，神情冷峻，大雨落下，木质回廊与青石地面。"),
    "T2_S03_group": (57, False, "man wearing a light blue robe and a straw hat",
        "雨中院落里，束发髻、身穿黑色暗纹刺绣长袍的男子持剑与一群黑衣人交手，大雨，地面积水飞溅。"),
    "T3_S04_spin": (73, False, "man wearing a light blue robe",
        "雨中院落里，束发髻、身穿黑色暗纹刺绣长袍的男子旋身穿过一群黑衣人，出剑迅猛，大雨，地面积水飞溅。"),
}


def build(shot):
    frames, animation, track_prompt, description = SHOTS[shot]
    p = copy.deepcopy(json.load(open(ROOT / "workflows" / "P24_scail2_api.json")))
    video = upload(ROOT / "clips" / f"{shot}.mp4")
    hero = upload(ROOT / "clips" / "hero_front_full.png")
    p["112"]["inputs"].update({"video": video, "force_rate": 30})
    p["110"]["inputs"]["Number"] = str(frames)   # frame_load_cap
    p["111"]["inputs"]["Number"] = "0"           # skip_first_frames
    p["115"]["inputs"]["value"] = 992            # SCAIL-2 要求 32 对齐；原片 1280×620 ≈ 2.07:1
    p["116"]["inputs"]["value"] = 480
    p["58"]["inputs"]["positive_prompt"] = description
    # 驱动视频只追踪主角：单独的文字条件，最多 1 个对象
    p["900"] = {"class_type": "CLIPTextEncode", "inputs": {"text": track_prompt, "clip": ["78", 1]}}
    p["79"]["inputs"].update({"conditioning": ["900", 0], "max_objects": 1})
    # 参考拼贴：只放主角正面全身像
    p["210"]["inputs"]["image"] = hero
    for slot in ("212", "213", "214", "255"):
        p.pop(slot)
    collage = p["344"]["inputs"]
    for key in ("image_2", "image_3", "image_4", "image_5"):
        collage.pop(key, None)
    collage["layout_json"] = json.dumps({"width": 992, "height": 480, "background": "black",
                                         "items": [{"x": 0.5, "y": 0.5, "scale": 1.0, "z": 1}]})
    p["197"]["inputs"]["replacement_mode"] = not animation
    embeds = p["347"]["inputs"]
    embeds["replacement_mode"] = not animation
    if animation:
        scene = upload(CHARS / "图片4_场景.jpg")
        p["901"] = {"class_type": "LoadImage", "inputs": {"image": scene}}
        embeds["bg_image"] = ["901", 0]
    p.pop("42", None)  # 提示音节点
    # 界面里的「二选一」开关（FastGroupsBypassSwitch）在 API 里没有另一路输入会报错：去掉开关直接连线
    bypass = {"321": ["344", 0], "550": ["90", 0]}
    for node in p.values():
        for key, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2 and value[0] in bypass:
                node["inputs"][key] = bypass[value[0]]
    for switch in bypass:
        p.pop(switch, None)
    p["119"]["inputs"]["filename_prefix"] = f"ref105trial/scail2_{shot}"
    return p


if __name__ == "__main__":
    shot = sys.argv[1]
    prompt = build(shot)
    (ROOT / "workflows" / f"scail2_{shot}.json").write_text(json.dumps(prompt, ensure_ascii=False, indent=1))
    started = time.time()
    pid = submit(prompt)
    print("submitted", shot, pid, flush=True)
    entry = wait(pid)
    print("done", shot, f"{time.time() - started:.0f}s", fetch_videos(entry, f"scail2_{shot}"), flush=True)
