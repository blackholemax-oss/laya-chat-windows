#!/usr/bin/env bash
# Laya 常驻服务启动脚本（WSL 内运行）。仓库副本，部署时放到 ~/laya-serve/run.sh。
#
# 一次性准备（见《实现方案》Part A）：
#   mkdir -p ~/laya-serve && cd ~/laya-serve
#   ~/.local/bin/uv venv --python 3.12 .venv
#   ~/.local/bin/uv pip install --python .venv/bin/python \
#       --index-url https://download.pytorch.org/whl/cu128 torch
#   ~/.local/bin/uv pip install --python .venv/bin/python "laya[serve]"
#   printf '%s' "$(openssl rand -hex 24)" > ~/laya-serve/.api_key && chmod 600 ~/laya-serve/.api_key
#
# 启动：bash ~/laya-serve/run.sh
set -euo pipefail

ROOT="${HOME}/laya-serve"
KEY_FILE="${ROOT}/.api_key"

if [[ ! -x "${ROOT}/.venv/bin/laya-serve" ]]; then
  echo "找不到 ${ROOT}/.venv/bin/laya-serve，先按脚本头部注释装好依赖。" >&2
  exit 1
fi

# 监听 0.0.0.0，Windows 侧才能经 127.0.0.1 访问（WSL2 默认端口映射）
export LAYA_HOST=0.0.0.0
export LAYA_PORT=8765
export LAYA_PRELOAD=1                 # 起来就加载模型，避免第一次请求等太久
export LAYA_THREADS=4
export LAYA_MODELS=multilingual       # 322M，含中文；需要英文可写 "english,multilingual"
export LAYA_DEVICE=cuda               # 没有 GPU 就改成 cpu 或 auto
export LAYA_LOG_LEVEL=info

# 首次启动从 HuggingFace 下 ~1.4GB 权重；国内直连慢，默认走镜像（想要官方源就自己设 HF_ENDPOINT）
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
# 镜像不支持 Xet 传输协议（会 401），强制回到普通 HTTP 下载
export HF_HUB_DISABLE_XET=1

# API key 只存文件、权限 600；没建就留空（服务端不校验 Bearer）
if [[ -f "${KEY_FILE}" ]]; then
  export LAYA_API_KEY="$(cat "${KEY_FILE}")"
  echo "使用 ${KEY_FILE} 里的 API key 鉴权。"
else
  echo "未找到 ${KEY_FILE}，服务将不校验 key（仅供本机自用）。" >&2
fi

exec "${ROOT}/.venv/bin/laya-serve"