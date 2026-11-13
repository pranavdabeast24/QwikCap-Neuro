#!/bin/sh
cd "$(dirname "$0")" || exit 1
if [ -x .venv/bin/python ]; then
  exec .venv/bin/python server.py
fi
echo "Create a virtual environment and install requirements first. See README.md."
exit 1
