#!/usr/bin/env bash
set -euo pipefail

ROOT="${DATAAUDIT_ROOT:-/hy-tmp/dataaudit-agent}"
PIDFILE="$ROOT/llama-server.pid"
if [[ ! -f "$PIDFILE" ]]; then
  echo "No project model PID file."
  exit 0
fi
pid="$(cat "$PIDFILE")"
if [[ -r "/proc/$pid/cmdline" ]] && tr '\0' ' ' <"/proc/$pid/cmdline" | grep -Fq "$ROOT/llama.cpp/build/bin/llama-server"; then
  kill -TERM "$pid"
  for _ in $(seq 1 30); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
fi
rm -f "$PIDFILE"
echo "Stopped project model server PID $pid."

