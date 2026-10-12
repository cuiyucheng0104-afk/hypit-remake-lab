"""构建前估算 AutoDL 市场花费：读 `hypit plan --json`，按实时单价（只读接口，不计费）算出高峰 / 闲时总价，并对照账本。

计划里被 Provider 拒绝的请求（例如市场 H3 不收参考视频）单独列出，不计价。
usage: market_estimate.py <run.svrun> [--endpoint h3.market]
"""
import json, os, subprocess, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import autodl_comfy  # noqa: E402

LEDGER = os.path.expanduser("~/.config/autodl/market-ledger.json")
WORKFLOWS = {"reference": "minimax_h3_z0903", "frame": "minimax_h3_b99_002", "text": "minimax_h3_lightx2v_no_pic"}
TIER = {"reference": "1088p", "frame": "736p", "text": "768p"}


def short(request):
    return urllib.parse.unquote(request).rsplit("::", 1)[-1].replace(":generate", "")


run = sys.argv[1]
endpoint = sys.argv[sys.argv.index("--endpoint") + 1] if "--endpoint" in sys.argv else "h3.market"
result = subprocess.run(["hypit", "plan", run, "--json"], capture_output=True, text=True)
try:
    plan = json.loads(result.stdout)
except json.JSONDecodeError:
    sys.exit(f"hypit plan 失败：\n{(result.stderr or result.stdout)[-3000:]}")

rejected = {}
for provider in plan.get("providers", []):
    if provider.get("status") == "unsupported":
        rejected[provider["request"]] = "；".join(r["message"] for r in provider.get("rejections", []))

prices, rows = {}, []
for need in plan.get("needs", []):
    if need.get("endpoint") != endpoint or need["request"] in rejected:
        continue
    fields = need.get("summary", {}).get("fields", {})
    refs = need.get("summary", {}).get("references", {})
    # FrameVideo 没有 aspect-ratio；TextVideo 没有参考；其余是 ReferenceVideo
    mode = "frame" if "aspectRatio" not in fields else "reference" if refs else "text"
    tier = "1440p" if (mode == "reference" and fields.get("resolution") == "2K") else TIER[mode]
    wf = WORKFLOWS[mode]
    if wf not in prices:
        data = autodl_comfy.call("GET", f"/workflows/{wf}").get("data", {})
        prices[wf] = list((data.get("billing_config") or {}).values())[0]
    rate = next((b for b in prices[wf] if b["resolution"] == tier), prices[wf][-1])
    seconds = int(fields.get("duration", 0))
    rows.append((short(need["request"]), mode, tier, seconds, rate["price"] / 1000 * seconds, rate["off_peak_price"] / 1000 * seconds))

peak = sum(r[4] for r in rows); off = sum(r[5] for r in rows); secs = sum(r[3] for r in rows)
for r in rows[:40]:
    print(f"  {r[0][:48]:48s} {r[1]:9s} {r[2]:6s} {r[3]:>3} 秒  高峰 ¥{r[4]:.3f}  闲时 ¥{r[5]:.3f}")
if len(rows) > 40:
    print(f"  … 共 {len(rows)} 个请求")
print(f"合计 {len(rows)} 个请求、{secs} 秒：高峰（北京时间 8–24 点）¥{peak:.2f}，闲时（0–8 点）¥{off:.2f}")
if rejected:
    print(f"✗ {len(rejected)} 个请求被拒绝，构建前要处理：")
    for request, message in rejected.items():
        print(f"  {short(request)}：{message}")
if os.path.exists(LEDGER):
    ledger = json.load(open(LEDGER))
    cap = ledger.get("capYuan")
    print(f"账本已记 ¥{ledger['spentYuan']:.2f}，上限 {cap if cap else '按 runtime 配置（默认 ¥30）'}")
print("注意：已被 build-record / file 固定的段落不会再生成，不在上面的清单里。")
