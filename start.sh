#!/usr/bin/env bash
# mclan — pull-and-run LAN Minecraft server.
# Usage: ./start.sh [extra args passed to `mclan up`]
#   ./start.sh                       # latest release, ./server
#   ./start.sh --version 1.20.4 --memory 4096
set -euo pipefail

cd "$(dirname "$0")"

# Find a Python 3 interpreter.
PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 8) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo "mclan needs Python 3.8+ on PATH. Install from https://python.org and re-run." >&2
  exit 1
fi

exec "$PY" -m mclan up "$@"
