"""AutoDL 市场花费账本（provider-autodl-market 在每次提交前记账，超过上限拒绝提交）。

usage:
  market_ledger.py show            看已记花费与明细
  market_ledger.py cap <元>        设上限（写进账本；runtime 配置里的 spendCapYuan 是默认值）
  market_ledger.py reset           清零（开始一轮新的构建前）
"""
import json, os, sys
LEDGER = os.path.expanduser("~/.config/autodl/market-ledger.json")

def load():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {"capYuan": None, "spentYuan": 0, "entries": []}

def save(d):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    json.dump(d, open(LEDGER, "w"), ensure_ascii=False, indent=1)

cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
d = load()
if cmd == "show":
    print(f"已记 ¥{d['spentYuan']:.3f}，账本上限 {d.get('capYuan')}，{len(d['entries'])} 笔")
    for e in d["entries"][-20:]:
        print(f"  {e['at'][:19]}  {e['workflow']:28s} {e['seconds']:>3} 秒  ¥{e['yuan']:.3f}")
elif cmd == "cap":
    d["capYuan"] = float(sys.argv[2]); save(d); print("上限设为", d["capYuan"])
elif cmd == "reset":
    save({"capYuan": d.get("capYuan"), "spentYuan": 0, "entries": []}); print("账本已清零")
