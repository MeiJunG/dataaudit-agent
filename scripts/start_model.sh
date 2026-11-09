#!/usr/bin/env bash
set -euo pipefail

ROOT="${DATAAUDIT_ROOT:-/hy-tmp/dataaudit-agent}"
MODEL="$ROOT/models/qwen2.5-7b-instruct-q4_K_M.gguf"
SERVER="$ROOT/llama.cpp/build/bin/llama-server"
PIDFILE="$ROOT/llama-server.pid"
LOG="$ROOT/logs/llama-server.log"

[[ -x "$SERVER" ]] || { echo "llama-server is not built: $SERVER" >&2; exit 1; }
[[ -s "$MODEL" ]] || { echo "Model file is missing or incomplete: $MODEL" >&2; exit 1; }
if [[ -f "$PIDFILE" ]]; then
  old_pid="$(cat "$PIDFILE")"
  if [[ -r "/proc/$old_pid/cmdline" ]] && tr '\0' ' ' <"/proc/$old_pid/cmdline" | grep -Fq "$SERVER"; then
    echo "Model server already running (PID $old_pid)."
    exit 0
  fi
  rm -f "$PIDFILE"
fi
mkdir -p "$ROOT/logs"
nohup "$SERVER" \
  --model "$MODEL" --alias qwen2.5-7b-instruct \
  --host 127.0.0.1 --port 8080 \
  --api-key local \
  --ctx-size 4096 --parallel 1 --threads 8 --threads-batch 8 \
  --n-gpu-layers 99 --jinja \
  >"$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
echo "Started llama-server PID $(cat "$PIDFILE"); log: $LOG"

