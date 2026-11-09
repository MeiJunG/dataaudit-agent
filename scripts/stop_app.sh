#!/usr/bin/env bash
set -euo pipefail

ROOT="${DATAAUDIT_ROOT:-/hy-tmp/dataaudit-agent}"
PIDFILE="$ROOT/gradio-app.pid"
if [[ ! -f "$PIDFILE" ]]; then
  echo "No project Gradio PID file."
  exit 0
fi
pid="$(cat "$PIDFILE")"
if [[ -r "/proc/$pid/cmdline" ]] && tr '\0' ' ' <"/proc/$pid/cmdline" | grep -Fq "$ROOT/dataaudit-agent/app.py"; then
  kill -TERM "$pid"
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
fi
rm -f "$PIDFILE"
echo "Stopped project Gradio app PID $pid."

