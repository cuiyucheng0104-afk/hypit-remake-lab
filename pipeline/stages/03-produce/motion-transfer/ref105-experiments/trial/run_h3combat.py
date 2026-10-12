"""路线 4：H3 打斗（U20 双 LoRA：Combat + 动作连续性修复），加原镜头作 <Video 1> 参考，按镜头重拍。

H3 以 24 fps、17k+5 帧生成；出片后由对照脚本截回原镜头长度。
usage: run_h3combat.py <shot-name>
"""
import copy, json, sys, time
from comfy import ROOT, CHARS, upload, submit, wait, fetch_videos

SHOTS = {
    # 名称: (镜头秒数, 动作描述)
    "T2_S03_group": (1.9,
        "Wide shot, the camera drifts slightly left. Subject 1 stands in the middle of a ring of Subject 2 assassins, "
        "parries a slash with his sword, steps in and cuts down the attacker in front of him while the others close in."),
    "T3_S04_spin": (2.433,
        "Wide shot, the camera pans right following the action. Subject 1 dives low and spins through the crowd of "
        "Subject 2 assassins, sweeping his sword; two assassins are knocked off their feet and fall into the water."),
}


def prompt_text(seconds, action):
    end = f"00:{seconds:06.3f}"
    return f"""subject_definitions:
<Subject 1> is the swordsman from <Picture 1>: a young Chinese man with his hair tied in a topknot and no hat, wearing a long black robe with dark cloud and carp embroidery and a leather belt, holding a long straight sword.
<Subject 2> are the assassins from <Picture 2>: men in black martial-arts outfits and woven bamboo conical hats, armed with curved sabers.
<Subject 3> is the rainy night courtyard from <Picture 3>: dark wooden corridors, wet flagstone ground, heavy rain.

summary:
[reference generation] Recreate <Video 1> shot for shot: identical choreography, positions, timing and camera movement, but <Subject 1> replaces the man in the light blue robe and straw hat, every black-clad fighter becomes a <Subject 2> assassin, and the location becomes <Subject 3>.

retention_analysis:
<Subject 1>, <Subject 2>, <Subject 3>: fully_preserved. <Video 1>: motion, blocking, framing and camera movement fully preserved; costumes, faces and location replaced.

detailed_description:
prfight2, bunny_crisp_motion. Raw 1.0x real-time speed, no slow motion, cinematic night rain, realistic impacts and splashing water.
[Shot 1] (00:00.000 - {end}) Follow <Video 1> exactly. {action}

overall_soundscape:
Heavy rain, splashing footsteps, sword clashes and grunts.

non_diegetic_music:
N/A"""


def build(shot):
    seconds, action = SHOTS[shot]
    p = copy.deepcopy(json.load(open(ROOT / "workflows" / "U20_combat_api.json")))
    for note in ("167", "180", "181", "182"):  # 只是提示词写法说明，不参与生成
        p.pop(note, None)
    p["137"]["inputs"]["image"] = upload(CHARS / "图片1_主角.jpg")
    p["152"]["inputs"]["image"] = upload(CHARS / "图片3_配角群.jpg")
    p["153"] = {"class_type": "LoadImage", "inputs": {"image": upload(CHARS / "图片4_场景.jpg")}}
    p["900"] = {"class_type": "VHS_LoadVideo", "inputs": {
        "video": upload(ROOT / "clips" / f"{shot}.mp4"), "force_rate": 24, "custom_width": 0, "custom_height": 0,
        "frame_load_cap": 0, "skip_first_frames": 0, "select_every_nth": 1, "format": "None"}}
    p["901"] = {"class_type": "ImageResizeKJv2", "inputs": {
        "width": 0, "height": 0, "upscale_method": "lanczos", "keep_proportion": "resize", "pad_color": "0, 0, 0",
        "crop_position": "center", "divisible_by": 32, "device": "cpu", "image": ["900", 0]}}
    ref = p["136"]["inputs"]
    ref.update({"prompt": ["138", 0], "width": 992, "height": 480,
                "ref_images.ref_image_2": ["153", 0], "ref_videos.ref_video_0": ["901", 0]})
    p["132"]["inputs"]["value"] = seconds
    p["138"]["inputs"]["value"] = prompt_text(seconds, action)
    p["92"]["inputs"]["filename_prefix"] = f"ref105trial/h3combat_{shot}"
    return p


if __name__ == "__main__":
    shot = sys.argv[1]
    prompt = build(shot)
    (ROOT / "workflows" / f"h3combat_{shot}.json").write_text(json.dumps(prompt, ensure_ascii=False, indent=1))
    started = time.time()
    pid = submit(prompt)
    print("submitted", shot, pid, flush=True)
    entry = wait(pid)
    print("done", shot, f"{time.time() - started:.0f}s", fetch_videos(entry, f"h3combat_{shot}"), flush=True)
