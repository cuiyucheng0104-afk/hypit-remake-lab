"""路线 3 变体：Bernini rv2v + cfg_chain（作者推荐：V=1.25 I=4.5 TI=4.0），加强参考图与文字指令的作用。"""
import json, sys, time
import run_bernini
from comfy import ROOT, submit, wait, fetch_videos

def build(shot, omega_i=4.5, omega_ti=4.0):
    p = run_bernini.build(shot)
    for node in ("281", "283"):
        p[node]["inputs"].update({"guidance_mode": "cfg_chain", "cfg": 2.0,
                                  "chain_omega_V": 1.25, "chain_omega_I": omega_i, "chain_omega_TI": omega_ti})
    p["136"]["inputs"]["filename_prefix"] = f"ref105trial/berninichain_{shot}"
    return p

if __name__ == "__main__":
    shot = sys.argv[1]
    p = build(shot)
    (ROOT / "workflows" / f"berninichain_{shot}.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
    started = time.time(); pid = submit(p); print("submitted berninichain", shot, pid, flush=True)
    entry = wait(pid)
    print("done berninichain", shot, f"{time.time() - started:.0f}s", fetch_videos(entry, f"berninichain_{shot}"), flush=True)
