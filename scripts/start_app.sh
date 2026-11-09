#!/usr/bin/env bash
set -euo pipefail

ROOT="${DATAAUDIT_ROOT:-/hy-tmp/dataaudit-agent}"
APP="$ROOT/dataaudit-agent/app.py"
PYTHON="$ROOT/dataaudit-agent/.venv/bin/python"
PIDFILE="$ROOT/gradio-app.pid"
LOG="$ROOT/logs/gradio-app.log"

if [[ -f "$PIDFILE" ]]; then
  old_pid="$(cat "$PIDFILE")"
  if [[ -r "/proc/$old_pid/cmdline" ]] && tr '\0' ' ' <"/proc/$old_pid/cmdline" | grep -Fq "$APP"; then
    echo "Gradio app already running (PID $old_pid)."
    exit 0
  fi
  rm -f "$PIDFILE"
fi
mkdir -p "$ROOT/logs"
nohup "$PYTHON" "$APP" >"$LOG" 2>&1 < /dev/null &
echo $! > "$PIDFILE"
echo "Started Gradio app PID $(cat "$PIDFILE"); log: $LOG"


