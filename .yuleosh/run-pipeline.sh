#!/bin/bash
# can-codec-python-demo pipeline runner — 持久化 yuleOSH guard 配置
# 后台运行: 显式 source 密钥 + 显式 venv python (后台 PATH 会漂移)
set -a
source "$HOME/.hermes/.env"
set +a
export PATH="/Users/stefan/.venvs/hermes-agent/bin:$PATH"
cd /Users/stefan/workspace/can-codec-python-demo
exec /Users/stefan/.venvs/hermes-agent/bin/yuleosh pipeline run spec.md "$@"
