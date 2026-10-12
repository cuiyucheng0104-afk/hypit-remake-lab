import json, time
import run_scail2
from comfy import ROOT, submit, wait, fetch_videos
jobs = []
for shot in ("T1_S07_hero", "T2_S03_group", "T3_S04_spin"):
    p = run_scail2.build(shot)
    (ROOT / "workflows" / f"scail2_{shot}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
    pid = submit(p); jobs.append((shot, pid, time.time())); print("submitted scail2", shot, pid, flush=True)
for shot, pid, started in jobs:
    try:
        entry = wait(pid)
        print("done scail2", shot, f"{time.time() - started:.0f}s", fetch_videos(entry, f"scail2_{shot}"), flush=True)
    except BaseException as error:
        print("RUN-FAILED scail2", shot, str(error)[:1500], flush=True)
