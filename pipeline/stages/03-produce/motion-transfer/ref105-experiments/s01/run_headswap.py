"""S01 换脸：K01「单人换头」分支（SAM3 追踪头部 + DWPose 表情 + Wan Animate 替换模式，只重画头部）。

输入是首帧精修 + Bernini 的镜头成片（s01/out/<id>.mp4，已补到 4n+1 帧），参考图是主角脸部近景。
usage: run_headswap.py <shot-id>…
"""
import copy, json, pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "trial"))
from comfy import upload, submit, wait, fetch_videos  # noqa: E402
import pipeline  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
BASE = json.load(open(HERE.parent / "trial" / "workflows" / "K01_headswap_api.json"))
FRAMES = {sid: pipeline.padded(b - a) for sid, a, b, *_ in pipeline.SHOTS}
# 多人镜头：SAM3 只追踪主角的头（刺客都戴斗笠）
TRACK = {"M": "head of the man with a topknot and no hat"}


def build(sid):
    p = copy.deepcopy(BASE)
    frames = FRAMES[sid]
    p["14"]["inputs"].update({"video": upload(HERE / "out" / f"{sid}.mp4", "ref105s01"), "force_rate": 30, "skip_first_frames": 0})
    p["15"]["inputs"]["value"] = 960   # 宽（与 Bernini 成片一致）
    p["16"]["inputs"]["value"] = 480   # 高
    p["22"]["inputs"]["value"] = frames
    p["35"]["inputs"]["image"] = upload(HERE / "hero_face.png", "ref105s01")
    p["70"]["inputs"]["prompt"] = TRACK.get(sid, "Head")
    p["36"]["inputs"]["keep_proportion"] = "pad"   # 脸部参考图是竖图，按生成画幅补边而不是裁掉
    p["91"]["inputs"]["positive_prompt"] = "束发髻的年轻男子，面容与参考图完全一致，神情冷峻，雨夜"
    p["110"]["inputs"].update({"frame_rate": 30, "filename_prefix": f"ref105s01/headswap_{sid}"})
    return p


if __name__ == "__main__":
    (HERE / "faceswap").mkdir(exist_ok=True)
    jobs = []
    for sid in sys.argv[1:]:
        pid = submit(build(sid)); jobs.append((sid, pid, time.time())); print("submitted headswap", sid, pid, flush=True)
    for sid, pid, started in jobs:
        try:
            entry = wait(pid, poll=5)
            saved = fetch_videos(entry, f"headswap_{sid}")
            target = HERE / "faceswap" / f"{sid}.mp4"
            final = [s for s in saved if s.endswith("_n110.mp4")]  # 节点 110 是成片，其余是遮罩/姿态预览
            pathlib.Path(final[0]).replace(target)
            print("done headswap", sid, f"{time.time() - started:.0f}s", target, flush=True)
        except BaseException as error:
            print("FAILED headswap", sid, str(error)[:1500], flush=True)
