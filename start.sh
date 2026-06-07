#!/usr/bin/env bash
# mclan — pull-and-run LAN Minecraft server.
# Run with no arguments for the friendly beginner wizard:
#   ./start.sh
# Or skip the wizard with explicit options:
#   ./start.sh up --version 1.20.4 --memory 4096
#
# On macOS and Linux, Python 3 is the zero-install path: it ships on nearly
# every Mac and Linux distro, so there's normally nothing to install (other than
# Java, which Minecraft itself needs).
set -euo pipefail

cd "$(dirname "$0")"

# Find a Python 3.8+ interpreter.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 8) else 1)' 2>/dev/null; then
      PY="$cand"; break
    fi
  fi
done

if [ -z "$PY" ]; then
  echo
  echo "mclan needs Python 3.8 or newer."
  echo "Most Macs and Linux systems already have it — try 'python3 --version'."
  echo "If it's missing:"
  echo "  macOS:          brew install python   (or get it from https://python.org)"
  echo "  Debian/Ubuntu:  sudo apt install python3"
  echo "  Fedora:         sudo dnf install python3"
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
