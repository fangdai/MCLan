#!/usr/bin/env bash
# mclan — pull-and-run LAN Minecraft server.
# Run with no arguments for the friendly beginner wizard:
#   ./start.sh
# Or skip the wizard with explicit options:
#   ./start.sh up --version 1.20.4 --memory 4096
set -euo pipefail

cd "$(dirname "$0")"

# Find a Python 3.8+ interpreter.
PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 8) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo
  echo "mclan needs Python 3.8 or newer, and it's not installed yet."
  echo "Get it free from https://python.org/downloads (Mac/Linux usually have it)."
  echo "Then run ./start.sh again."
  echo
  exit 1
fi

# No arguments -> beginner wizard. Arguments -> pass straight through.
if [ "$#" -eq 0 ]; then
  exec "$PY" -m mclan play
else
  exec "$PY" -m mclan "$@"
fi
