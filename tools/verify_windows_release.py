"""Build and verify the portable Windows ZIP using fictional fixtures only."""
from __future__ import annotations

import argparse
import base64
from importlib import metadata
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
from branding import APP_BASENAME
from server import terminate_tree


class VerificationError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise VerificationError(message)


def read_report(path):
    require(path.is_file() and path.stat().st_size <= 128 * 1024, "Verification report missing or oversized")
    result = json.loads(path.read_text(encoding="utf-8"))
    require(result.get("status") == "passed", "Verification report did not pass")
    return result


def retain_acceptance_summary(source, target, expected_groups=None):
    result = read_report(source)
    if expected_groups is not None:
        require(len(result.get("checks", [])) == expected_groups
                and all(item.get("status") == "passed" for item in result["checks"]),
                "Acceptance group totals changed")
    summary = {key: result[key] for key in
               ("status", "documents", "extractedMatches", "destinationColumns", "patientRows", "originalForms",
                "mappedFields", "exportedCellsMatched") if key in result}
    summary["checks"] = [{"check": item["check"], "status": item["status"]} for item in result.get("checks", [])]
    summary["exports"] = [{key: item[key] for key in ("records", "cellsMatched", "headersMatched") if key in item}
                          for item in result.get("exports", [])]
    target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def run_check(name, command, report, environment, cwd, timeout=600):
    report["currentStage"] = name
    started = time.monotonic()
    entry = {"check": name, "status": "failed"}
    report["checks"].append(entry)
    process = subprocess.Popen(command, cwd=cwd, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_tree(process)
        output, _ = process.communicate(timeout=15)
        entry["failure"] = "deadline-exceeded"
        raise VerificationError(f"{name} exceeded its deadline") from None
    finally:
        entry["seconds"] = round(time.monotonic() - started, 2)
    entry.update(exitCode=process.returncode, outputSHA256=hashlib.sha256(output).hexdigest())
    if name == "source-unit-tests":
        text = output.decode("utf-8", errors="replace")
        totals = re.search(r"Ran (\d+) tests? in ([0-9.]+)s", text)
        skipped = re.findall(r"^(test_\w+ \([^)]+\)) \.\.\. skipped", text, re.MULTILINE)
        if totals:
            entry.update(testsRun=int(totals[1]), testSeconds=float(totals[2]),
                         skippedTests=skipped, skippedCount=len(skipped))
    # These commands only read committed or generated fictional acceptance inputs.
    print(output.decode("utf-8", errors="replace")[-100_000:], end="", flush=True)
    require(process.returncode == 0, f"{name} failed")
    if name == "source-unit-tests":
        require(entry.get("testsRun", 0) >= 218, "Unit test summary is missing or incomplete")
        require(not any("test_windows_runtime." in item or "test_desktop_layout." in item
                        for item in entry["skippedTests"]), "Required Windows native tests were skipped")
    entry["status"] = "passed"


def invoke_packaged_helper(helper, kind, payload, environment, cwd, timeout):
    command = [str(helper), kind]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=cwd, env=environment,
                               creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    try:
        stdout, stderr = process.communicate(json.dumps(payload, ensure_ascii=True).encode("ascii"), timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_tree(process)
        process.communicate(timeout=15)
        raise VerificationError("Packaged companion exceeded its deadline") from None
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def verify_packaged_helper(bundle, output, environment):
    helper = bundle / "_internal/helpers/FormbridgeWorker.exe"
    require(helper.is_file(), "Packaged console companion is missing")
    assets = output / "Unicode assets 測試 Café 😀"
    assets.mkdir()
    value = "SYNTHETIC 測試 Café 😀"
    payload = {"data": base64.b64encode(("Record ID: " + value).encode("utf-8")).decode("ascii"),
               "filename": "fictional 測試 Café 😀.txt", "assetDir": str(assets), "recordId": "fictional-unicode",
               "schema": [{"name": "record_id", "label": "Record ID", "type": "text", "required": True}]}
    child = invoke_packaged_helper(helper, "document", payload, environment, output, 90)
    require(child.returncode == 0 and len(child.stdout) <= 2 * 1024 * 1024, "Packaged Unicode worker failed")
    response = json.loads(child.stdout.decode("ascii"))
    require("error" not in response and response["values"]["record_id"] == value,
            "Packaged Unicode JSON roundtrip changed values")
    template = {"operation": "inspect", "filename": "fictional 測試 Café 😀.csv",
                "data": base64.b64encode("Café 測試 😀\n".encode("utf-8")).decode("ascii")}
    child = invoke_packaged_helper(helper, "template", template, environment, output, 60)
    require(child.returncode == 0, "Packaged Unicode template worker failed")
    response = json.loads(child.stdout.decode("ascii"))
    require("error" not in response and response["result"]["columns"][0]["name"] == "Café 測試 😀",
            "Packaged Unicode template header changed")
    no_ocr = environment.copy()
    no_ocr["FORMBRIDGE_TESSERACT"] = str(output / "missing-ocr/tesseract.exe")
    scan = bundle / "_internal/samples/practice-06-scan.pdf"
    payload.update(data=base64.b64encode(scan.read_bytes()).decode("ascii"),
                   filename="fictional-scan.pdf", recordId="fictional-no-ocr")
    child = invoke_packaged_helper(helper, "document", payload, no_ocr, output, 90)
    require(child.returncode == 0, "Packaged no-OCR worker failed")
    response = json.loads(child.stdout.decode("ascii"))
    require("error" not in response and response["values"]["record_id"] == "" and response.get("issues"),
            "Packaged no-OCR scan must retain a blank suggestion for manual review")


def verify(output, dist, report):
    require(sys.platform == "win32" and platform.machine().upper() in {"AMD64", "X86_64"},
            "This acceptance check requires native Windows x64")
    environment = os.environ.copy()
    environment.update(FORMBRIDGE_REQUIRE_OCR="1", PYTHONUTF8="1")
    engine = Path(environment.get("FORMBRIDGE_TESSERACT", ""))
    require(engine.is_absolute() and engine.is_file(), "Operational Tesseract must be explicitly configured")
    version = subprocess.run([str(engine), "--version"], capture_output=True, timeout=15, check=True)
    require(b"tesseract 5.5.3" in version.stdout, "Unexpected Tesseract version")
    require((engine.parent / "tessdata/eng.traineddata").is_file(), "English OCR data is missing")
    report["environment"] = {
        "commit": os.environ.get("GITHUB_SHA", "local-uncommitted"), "os": platform.platform(),
        "architecture": platform.machine(), "python": platform.python_version(),
        "dependencies": {name: metadata.version(name) for name in
                         ("Pillow", "pypdfium2", "reportlab", "pypdf", "openpyxl", "defusedxml", "pyinstaller")},
        "requirements": {name: (APP / name).read_text(encoding="utf-8").splitlines()
                         for name in ("requirements.txt", "requirements-build.txt")},
        "tesseractVersion": version.stdout.decode("utf-8", errors="replace").splitlines()[0],
        "tesseractInstallerSHA256": environment.get("FORMBRIDGE_TESSERACT_INSTALLER_SHA256"),
        "ocrBundled": False,
    }
    python = str(Path(sys.executable).resolve())
    run_check("source-unit-tests", [python, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
              report, environment, APP)
    source_startup = output / "source-startup.json"
    run_check("source-native-startup", [python, "-B", str(APP / "desktop.py"), "--verify-startup", str(source_startup)],
              report, environment, APP, 60)
    require(not read_report(source_startup)["frozen"], "Source verification unexpectedly used a frozen app")
    for script, name in (("verify_pace_flow.py", "pace"), ("verify_custom_masks.py", "custom-masks")):
        run_check("source-" + name, [python, "-B", str(APP / "tools" / script), "--output", str(output / ("source-" + name))],
                  report, environment, APP)
        result_name = "pace-results.json" if name == "pace" else "custom-mask-results.json"
        retain_acceptance_summary(output / ("source-" + name) / result_name,
                                  output / "reports" / ("source-" + result_name), 9 if name == "pace" else 10)
    run_check("build-native-bundle", [python, "-B", str(APP / "build_desktop.py"),
              "--work-dir", str(output / "build"), "--dist-dir", str(dist)], report, environment, APP, 600)
    bundle = dist / APP_BASENAME
    archive = dist / f"{APP_BASENAME}-Windows-x64.zip"
    require(bundle.is_dir() and not archive.exists(), "Windows output missing or archive already exists")
    shutil.copyfile(APP / "docs/WINDOWS.md", bundle / "WINDOWS_README.md")
    shutil.copyfile(APP / "OWNERSHIP.md", bundle / "OWNERSHIP.md")
    report["currentStage"] = "distribution-notices-and-inventory"
    from tools.collect_windows_notices import collect
    inventory = collect(bundle)
    report["distribution"] = {"manifest": "BUILD_MANIFEST.json", **inventory}
    shutil.copyfile(bundle / "BUILD_MANIFEST.json", output / "reports/BUILD_MANIFEST.json")
    report["currentStage"] = "portable-zip-and-relocation"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path in sorted(bundle.rglob("*")):
            require(not path.is_symlink(), "Application ZIP cannot include symbolic links")
            if path.is_file():
                zipped.write(path, path.relative_to(dist).as_posix())
    report["package"] = {"file": archive.name, "bytes": archive.stat().st_size,
                         "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    relocation = Path(tempfile.mkdtemp(prefix="QuickCap portable 測試 Café 😀 ", dir=os.environ.get("RUNNER_TEMP")))
    require(APP not in relocation.resolve().parents, "Package relocation must be outside the checkout")
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(relocation)
    extracted = relocation / APP_BASENAME
    isolated = environment.copy()
    isolated.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"),
                    PYTHONUTF8="0", PYTHONIOENCODING="cp1252")
    require(not any((Path(p) / "python.exe").is_file() for p in isolated["PATH"].split(os.pathsep)),
            "Isolated PATH unexpectedly contains Python")
    startup = output / "packaged-startup.json"
    run_check("extracted-native-startup-without-python-path",
              [str(extracted / f"{APP_BASENAME}.exe"), "--verify-startup", str(startup)],
              report, isolated, relocation, 60)
    gui = read_report(startup)
    require(gui.get("frozen") is True and gui.get("catalogFields") == 512
            and gui.get("records") == gui.get("activeFields") == 0, "Frozen GUI startup proof is incomplete")
    report["currentStage"] = "extracted-companion-unicode-json-and-no-ocr-without-python-path"
    helper_check = {"check": report["currentStage"], "status": "failed"}
    report["checks"].append(helper_check)
    verify_packaged_helper(extracted, relocation, isolated)
    helper_check["status"] = "passed"
    run_check("packaged-fictional-scans-and-exports", [python, "-B", str(APP / "verify_desktop_bundle.py"),
              str(extracted), "--output", str(output / "packaged-fixtures")], report, isolated, relocation)
    fixtures = read_report(output / "packaged-fixtures/desktop-bundle-results.json")
    require(fixtures.get("documents") == 10 and fixtures.get("extractedMatches") == 60
            and sum(item["cellsMatched"] for item in fixtures["exports"]) == 240, "Packaged fixture totals changed")
    retain_acceptance_summary(output / "packaged-fixtures/desktop-bundle-results.json",
                              output / "reports/packaged-fixture-results.json")
    for script, name in (("verify_pace_flow.py", "pace"), ("verify_custom_masks.py", "custom-masks")):
        run_check("packaged-" + name, [python, "-B", str(APP / "tools" / script), "--bundle", str(extracted),
                  "--output", str(output / ("packaged-" + name))], report, isolated, relocation)
        result_name = "pace-results.json" if name == "pace" else "custom-mask-results.json"
        retain_acceptance_summary(output / ("packaged-" + name) / result_name,
                                  output / "reports" / ("packaged-" + result_name), 9 if name == "pace" else 10)
    report.update(status="passed", relocatedOutsideCheckout=True, pythonAbsentFromPackagedPATH=True,
                  packagedDocuments=10, packagedExtractedFields=60, packagedExportedCells=240, currentStage="complete")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dist-dir", type=Path, required=True)
    args = parser.parse_args()
    output, dist = args.output.resolve(), args.dist_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports = output / "reports"
    reports.mkdir(exist_ok=True)
    report = {"format": "quickcap-windows-release-verification-v1", "status": "failed", "currentStage": "environment-preflight",
              "notice": "Committed and generated fictional acceptance fixtures only. No patient data.", "checks": []}
    try:
        verify(output, dist, report)
    except Exception as error:
        stage = report["currentStage"][:120]
        detail = str(error)[:300] if isinstance(error, VerificationError) or type(error).__name__ == "NoticeError" else "The check raised an exception."
        report.update(status="failed", failureStage=stage, failureType=type(error).__name__, failureDetail=detail,
                      failure="Windows acceptance did not complete. Inspect the job console.")
        if not report["checks"] or report["checks"][-1]["status"] != "failed":
            report["checks"].append({"check": stage, "status": "failed", "kind": "validation",
                                     "failureType": type(error).__name__})
        print(f"{type(error).__name__}: {str(error)[:500]}", file=sys.stderr)
        print(report["failure"], file=sys.stderr)
    finally:
        for name in ("source-startup.json", "packaged-startup.json"):
            path = output / name
            if path.is_file() and path.stat().st_size <= 16 * 1024:
                (reports / name).write_bytes(path.read_bytes())
        (reports / "windows-release-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        lines = [f"{item['check']}: {item['status']}" for item in report["checks"]]
        (reports / "windows-checks.txt").write_text("\n".join(lines + ["Overall: " + report["status"]]) + "\n", encoding="utf-8")
        if report.get("package"):
            info = report["package"]
            (reports / "SHA256SUMS.txt").write_text(f"{info['sha256']}  {info['file']}\n", encoding="ascii")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
