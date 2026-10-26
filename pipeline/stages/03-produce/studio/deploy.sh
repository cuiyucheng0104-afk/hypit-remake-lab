#!/usr/bin/env bash
# Build the Studio page and copy the hypit_studio plugin into the 5090's ComfyUI.
# Usage: ./deploy.sh <ssh-target>      e.g. ./deploy.sh ROG@<5090-LAN-IP>
# ComfyUI must be restarted afterwards for a changed __init__.py / graphs.py to load
# (a web-only change just needs a browser refresh).
set -euo pipefail
TARGET="${1:?usage: ./deploy.sh <ssh-target>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REMOTE_NODES="D:/Apps/ComfyUI_windows_portable/ComfyUI/custom_nodes"

(cd "$HERE/web-src" && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build)

COPYFILE_DISABLE=1 tar -C "$HERE" -czf /tmp/hypit_studio.tgz --exclude='__pycache__' hypit_studio
scp -q -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 /tmp/hypit_studio.tgz "$TARGET:D:/Downloads/hypit_studio.tgz"
ssh -o IdentitiesOnly=yes -i ~/.ssh/id_ed25519 "$TARGET" "tar -xzf D:/Downloads/hypit_studio.tgz -C $REMOTE_NODES && del D:\\Downloads\\hypit_studio.tgz"
echo "deployed to $TARGET:$REMOTE_NODES/hypit_studio — restart ComfyUI if Python files changed, then open http://<5090>:8188/studio"
