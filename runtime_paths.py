"""Resolve owned resources and the dedicated console worker in desktop bundles."""
from pathlib import Path
import os
import sys


ROOT = Path(__file__).resolve().parent
WORKER_KINDS = frozenset({"document", "template"})


def worker_command(kind):
    if kind not in WORKER_KINDS:
        raise ValueError("Unknown local worker operation.")
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ROOT))
        name = "FormbridgeWorker.exe" if os.name == "nt" else "FormbridgeWorker"
        helper = base / "helpers" / name
        if not helper.is_file():
            raise RuntimeError("The desktop worker is missing. Reinstall the complete application bundle.")
        return [str(helper), kind]
    interpreter = Path(sys.executable)
    if interpreter.name.casefold() == "pythonw.exe":
        interpreter = interpreter.with_name("python.exe")
        if not interpreter.is_file():
            raise RuntimeError("The console Python worker is missing from this environment.")
    return [str(interpreter), str(ROOT / "desktop_worker.py"), kind]


def process_options():
    if os.name == "nt":
        return {"creationflags": subprocess_flags()}
    return {"start_new_session": True}


def subprocess_flags():
    import subprocess
    return subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
