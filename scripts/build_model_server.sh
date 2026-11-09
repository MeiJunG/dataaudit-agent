#!/usr/bin/env bash
set -euo pipefail

ROOT="${DATAAUDIT_ROOT:-/hy-tmp/dataaudit-agent}"
CMAKE="$ROOT/dataaudit-agent/.venv/bin/cmake"
[[ -x "$CMAKE" ]] || { echo "Install build-requirements.txt in the project venv first." >&2; exit 1; }
"$CMAKE" -S "$ROOT/llama.cpp" -B "$ROOT/llama.cpp/build" \
  -DGGML_CUDA=ON -DGGML_CUDA_FA=OFF -DCMAKE_CUDA_ARCHITECTURES=70 \
  -DCMAKE_BUILD_TYPE=Release -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF
"$CMAKE" --build "$ROOT/llama.cpp/build" --target llama-server -j "${BUILD_JOBS:-8}"

