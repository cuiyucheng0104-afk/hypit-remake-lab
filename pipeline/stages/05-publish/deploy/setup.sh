#!/bin/sh
# 生成本机 .env（随机 JWT 密钥），只需运行一次；.env 不入库
cd "$(dirname "$0")"
[ -f .env ] || printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 32)" > .env && chmod 600 .env
echo ".env ready"
