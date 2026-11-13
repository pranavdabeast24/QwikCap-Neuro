"""Verify timeout cleanup against a real disposable process tree."""
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import terminate_tree


class ProcessCleanupTests(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Windows taskkill requires a Windows test host")
    def test_worker_group_cleanup_stops_child_process(self):
        script = "import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); print(p.pid,flush=True); time.sleep(60)"
        process = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True, start_new_session=True)
        try:
            child = int(process.stdout.readline().strip())
            terminate_tree(process)
            process.wait(timeout=3)
            deadline = time.monotonic() + 3
            state = "running"
            while time.monotonic() < deadline:
                result = subprocess.run(["ps", "-o", "stat=", "-p", str(child)], capture_output=True, text=True, check=False)
                state = result.stdout.strip()
                if not state or state.startswith("Z"):
                    break
                time.sleep(0.02)
            self.assertTrue(not state or state.startswith("Z"), f"Child still executes with state {state}")
        finally:
            terminate_tree(process)
            process.wait(timeout=3)
            process.stdout.close()


if __name__ == "__main__":
    unittest.main()
