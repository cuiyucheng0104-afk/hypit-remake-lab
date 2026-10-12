"""一次性提交剩余试验任务（服务器单卡顺序执行），再逐个等结果、取回成片。"""
import json, sys, time
import run_bernini, run_scail2, run_h3combat
from comfy import ROOT, submit, wait, fetch_videos

JOBS = [
    ("bernini", run_bernini, "T2_S03_group"), ("bernini", run_bernini, "T3_S04_spin"),
    ("scail2", run_scail2, "T1_S07_hero"), ("scail2", run_scail2, "T2_S03_group"), ("scail2", run_scail2, "T3_S04_spin"),
    ("h3combat", run_h3combat, "T2_S03_group"), ("h3combat", run_h3combat, "T3_S04_spin"),
]

submitted = []
for route, module, shot in JOBS:
    try:
        prompt = module.build(shot)
        (ROOT / "workflows" / f"{route}_{shot}.json").write_text(json.dumps(prompt, ensure_ascii=False, indent=1))
        pid = submit(prompt)
        submitted.append((route, shot, pid, time.time()))
        print("submitted", route, shot, pid, flush=True)
    except BaseException as error:  # 某条路线配置有问题时，其余照常提交
        print("SUBMIT-FAILED", route, shot, str(error)[:1500], flush=True)

for route, shot, pid, started in submitted:
    try:
        entry = wait(pid)
        print("done", route, shot, f"{time.time() - started:.0f}s", fetch_videos(entry, f"{route}_{shot}"), flush=True)
    except BaseException as error:
        print("RUN-FAILED", route, shot, str(error)[:1500], flush=True)
