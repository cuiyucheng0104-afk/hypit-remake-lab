"""汇总 ref105 的 79 个镜头（S01 的 13 个 + S02–S09 的 66 个）为 shots.json。

每个镜头：id、所在段、段内起止帧、全片起止帧、原长秒数、生成秒数（按 Hypit 规定 H3 至少 4 秒）、类别、
景别与动作描述（desc，待按原片反推）、从生成结果的第几帧开始取（take_offset，默认 0）。
"""
import importlib.util, json, math, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
REMAKE = HERE.parent / "ref105-remake"
sys.argv = ["x"]
spec = importlib.util.spec_from_file_location("s01p", REMAKE / "s01" / "pipeline.py")
s01 = importlib.util.module_from_spec(spec); spec.loader.exec_module(s01)
plan = json.load(open(REMAKE / "segs" / "plan.json"))
segments = {s["id"]: s for s in json.load(open(REMAKE / "export" / "segments.json"))}

shots, cursor = [], 0
s01_shots = [(f"S01-{sid}", a, b, kind) for sid, a, b, kind, *_ in s01.SHOTS]
seg_frames = {"S01": 249}
all_shots = [("S01", *x) for x in s01_shots]
for seg, info in plan.items():
    seg_frames[seg] = info["frames"]
    all_shots += [(seg, f"{seg}-{i}", a, b, k) for i, ((a, b), k) in enumerate(zip(info["shots"], info["kinds"]), 1)]
offsets, acc = {}, 0
for seg in ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09"]:
    offsets[seg] = acc; acc += seg_frames[seg]
for seg, sid, a, b, kind in all_shots:
    n = b - a
    shots.append({"id": sid, "segment": seg, "seg_frames": [a, b], "film_frames": [offsets[seg] + a, offsets[seg] + b],
                  "source_seconds": round(n / 30, 3), "generate_seconds": max(4, math.ceil(n / 30)), "kind": kind,
                  "segment_content": segments[seg]["content"], "desc": "", "take_offset": 0})
json.dump({"fps": 30, "total_frames": acc, "shots": shots}, open(HERE / "shots.json", "w"), ensure_ascii=False, indent=1)
print(len(shots), "shots,", acc, "frames,", sum(s["generate_seconds"] for s in shots), "generated seconds")
