#!/bin/bash
# 视频阶段结束后：主角近景换脸 → 拼全片。日志写 chain.log。
cd "$(dirname "$0")"
while pgrep -f "pipeline.py videos" >/dev/null; do sleep 30; done
echo "STAGE videos finished $(date +%H:%M)"
python3 pipeline.py faceswap 2>&1
echo "STAGE faceswap finished $(date +%H:%M)"
python3 pipeline.py assemble 2>&1 && echo "STAGE assemble finished $(date +%H:%M)" || echo "STAGE assemble FAILED"
