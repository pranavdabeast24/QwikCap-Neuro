"""Verify timeout cleanup against a real disposable process tree."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import terminate_tree
from runtime_paths import process_options


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

    @unittest.skipUnless(os.name == "nt", "Requires the Windows taskkill implementation")
    def test_windows_taskkill_stops_real_worker_and_child(self):
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        script = (
            "import pathlib,subprocess,sys,time; "
            "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
            "pending=pathlib.Path(sys.argv[1]+'.tmp'); pending.write_text(str(p.pid),encoding='ascii'); "
            "pending.replace(sys.argv[1]); time.sleep(60)"
        )
        with tempfile.TemporaryDirectory(prefix="quickcap-process-test-") as folder:
            pid_file = Path(folder) / "child.pid"
            process = subprocess.Popen(
                [sys.executable, "-c", script, str(pid_file)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **process_options(),
            )
            child_handle = None
            try:
                deadline = time.monotonic() + 5
                while not pid_file.is_file() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(pid_file.is_file(), "Disposable worker did not start its child")
                child = int(pid_file.read_text(encoding="ascii"))
                child_handle = kernel.OpenProcess(0x00100000 | 0x0001, False, child)
                self.assertTrue(child_handle, "Disposable child could not be observed")
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 0), 0x00000102)
                terminate_tree(process)
                process.wait(timeout=5)
                self.assertNotEqual(process.returncode, 0)
                self.assertEqual(kernel.WaitForSingleObject(child_handle, 5000), 0,
                                 "Windows cancellation left the disposable child running")
            finally:
                terminate_tree(process)
                process.wait(timeout=5)
                if child_handle:
                    if kernel.WaitForSingleObject(child_handle, 0) == 0x00000102:
                        kernel.TerminateProcess(child_handle, 1)
                        kernel.WaitForSingleObject(child_handle, 5000)
                    kernel.CloseHandle(child_handle)


if __name__ == "__main__":
    unittest.main()
