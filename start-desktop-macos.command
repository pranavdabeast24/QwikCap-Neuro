#!/bin/sh
set -eu
FORMBRIDGE_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
cd "$FORMBRIDGE_DIR"
if [ ! -x "$FORMBRIDGE_DIR/.venv/bin/python" ]; then
    printf '%s\n' 'Formbridge needs a local Python environment with Tk.' \
        'In this folder, run these commands yourself:' \
        '  python3.12 -m venv .venv' \
        '  .venv/bin/python -m pip install -r requirements.txt' \
        'Then run start-desktop-macos.command again.'
    exit 1
fi
if [ ! -f "$FORMBRIDGE_DIR/desktop.py" ]; then
    printf '%s\n' 'desktop.py is missing. Restore the complete Formbridge source folder.'
    exit 1
fi
if ! "$FORMBRIDGE_DIR/.venv/bin/python" -c 'import tkinter, PIL, pypdfium2, reportlab, pypdf, openpyxl, defusedxml'; then
    printf '%s\n' 'Install the application requirements explicitly:' \
        '  .venv/bin/python -m pip install -r requirements.txt' \
        'Use a Python installation with working Tk support.'
    exit 1
fi
exec "$FORMBRIDGE_DIR/.venv/bin/python" "$FORMBRIDGE_DIR/desktop.py"
