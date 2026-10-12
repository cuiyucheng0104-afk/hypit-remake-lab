#!/bin/bash
# 用法: poll.sh <prompt_id> [间隔秒] [最多次数]
PID=$1; EVERY=${2:-30}; MAX=${3:-240}
SSH="ssh -i $HOME/.ssh/autodl_ed25519 -p <SSH_PORT> -o BatchMode=yes -o ConnectTimeout=15 root@<AUTODL_SSH_HOST>"
for ((i=1; i<=MAX; i++)); do
  H=$($SSH "curl -s -m 10 http://127.0.0.1:6006/history/$PID" 2>/dev/null)
  if echo "$H" | grep -q '"status_str"'; then
    echo "$(date +%H:%M:%S) FINISHED"
    echo "$H" | python3 -c '
import sys,json
d=json.load(sys.stdin); h=list(d.values())[0]; st=h["status"]
print("status:",st.get("status_str"))
for m in st.get("messages",[]):
    if m[0]=="execution_error":
        e=m[1]; print("ERROR node",e.get("node_id"),e.get("node_type"),"|",str(e.get("exception_message"))[:600])
    if m[0]=="execution_success": print("success at",m[1].get("timestamp"))
for nid,o in h.get("outputs",{}).items():
    for k in ("gifs","videos","images"):
        for f in o.get(k,[]): print("OUT",nid,f.get("type"),f.get("subfolder"),f.get("filename"))
'
    exit 0
  fi
  LAST=$($SSH "curl -s -m 8 http://127.0.0.1:6008/api/comfy/logs" 2>/dev/null | grep '^data:' | tail -40 | sed 's/^data: //' | python3 -c '
import sys,json,re
lines=[]
for l in sys.stdin:
    try: lines.append(json.loads(l)["line"])
    except Exception: pass
keep=[re.sub(r"\x1b\[[0-9;]*m","",x) for x in lines if re.search(r"%|it/s|s/it|window|frame|Sampling|Loading|SeC|pose|Prompt", x)]
print(" | ".join(keep[-2:])[-230:])' 2>/dev/null)
  echo "$(date +%H:%M:%S) running  $LAST"
  sleep "$EVERY"
done
echo "timeout"; exit 1
