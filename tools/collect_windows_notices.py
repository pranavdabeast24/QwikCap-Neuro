"""Retain installed Windows distribution notices and inventory shipped binaries."""
from __future__ import annotations

import argparse
from importlib import metadata
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys

PACKAGES = ("Pillow", "pypdfium2", "reportlab", "pypdf", "openpyxl", "defusedxml",
            "charset-normalizer", "et-xmlfile", "pyinstaller")
NOTICE_NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")
MAX_NOTICE_BYTES = 32 * 1024 * 1024
MAX_NOTICE_FILES = 4096


class NoticeError(RuntimeError):
    pass


def require(value, message):
    if not value:
        raise NoticeError(message)


def file_info(path, relative):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": relative.as_posix(), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def metadata_root(distribution):
    for item in distribution.files or []:
        for index, part in enumerate(item.parts):
            if part.endswith(".dist-info"):
                root = Path(distribution.locate_file(Path(*item.parts[:index + 1])))
                require(root.is_dir() and not root.is_symlink(), "Installed distribution metadata is unavailable")
                return root
    raise NoticeError("Installed distribution has no dist-info record")


def notice_paths(distribution, root):
    paths = set()
    license_tree = root / "licenses"
    if license_tree.exists():
        require(not license_tree.is_symlink(), "Installed license directory cannot be a symbolic link")
        for path in license_tree.rglob("*"):
            require(not path.is_symlink(), "Installed notices cannot contain symbolic links")
            if path.is_file():
                paths.add(path)
    for path in root.iterdir():
        if path.is_file() and path.name.upper().startswith(NOTICE_NAMES):
            paths.add(path)
    for name in distribution.metadata.get_all("License-File", []):
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts, "Invalid installed License-File path")
        candidates = [license_tree / relative, root / relative]
        selected = next((path for path in candidates if path.is_file()), None)
        require(selected is not None, "A declared distribution notice is missing")
        paths.add(selected)
    require(paths, "Installed distribution has no license or notice payload")
    return sorted(paths)


def copy_notice(source, target, notices, inventory):
    require(source.is_file() and not source.is_symlink(), "Required notice is not a regular file")
    require(0 < source.stat().st_size <= MAX_NOTICE_BYTES, "Required notice is empty or oversized")
    require(len(inventory) < MAX_NOTICE_FILES, "Notice inventory exceeded its file limit")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    inventory.append(file_info(target, target.relative_to(notices)))


def collect(bundle: Path) -> dict:
    require(sys.platform == "win32", "Windows notices must be collected on the native build host")
    bundle = Path(bundle).resolve()
    require(bundle.is_dir(), "Built application directory is missing")
    notices = bundle / "THIRD_PARTY_NOTICES"
    require(not notices.exists(), "Notices already exist; use a fresh build directory")
    notices.mkdir()
    notice_inventory = []
    packages = []
    for name in PACKAGES:
        distribution = metadata.distribution(name)
        root = metadata_root(distribution)
        paths = notice_paths(distribution, root)
        if name == "pypdfium2":
            require(any("BUILD_LICENSES" in path.parts for path in paths),
                    "PDFium native build notices are missing")
        for source in paths:
            copy_notice(source, notices / name / source.relative_to(root), notices, notice_inventory)
        packages.append({"name": name, "version": distribution.version, "noticeFiles": len(paths)})

    reportlab = metadata.distribution("reportlab")
    vera = Path(reportlab.locate_file("reportlab/fonts/bitstream-vera-license.txt"))
    copy_notice(vera, notices / "reportlab/bitstream-vera-license.txt", notices, notice_inventory)
    runtime = Path(sys.base_prefix)
    python_license = next((path for path in (runtime / "LICENSE.txt", runtime / "LICENSE") if path.is_file()), None)
    require(python_license is not None, "CPython aggregate runtime license is missing")
    license_text = python_license.read_text(encoding="utf-8", errors="replace").casefold()
    require("tcl" in license_text and "tk" in license_text and "copyright" in license_text,
            "CPython aggregate runtime license does not retain Tcl/Tk notices")
    copy_notice(python_license, notices / "Python" / python_license.name, notices, notice_inventory)
    for folder in (runtime / "tcl", runtime / "DLLs"):
        if folder.is_dir():
            for source in sorted(folder.rglob("*")):
                if source.is_file() and source.name.upper().startswith(NOTICE_NAMES):
                    copy_notice(source, notices / "Python" / source.relative_to(runtime), notices, notice_inventory)

    native = []
    for path in sorted(bundle.rglob("*")):
        require(not path.is_symlink(), "Application inventory cannot contain symbolic links")
        if path.is_file() and path.suffix.casefold() in {".dll", ".pyd", ".exe"}:
            require(len(native) < 10_000, "Native binary inventory exceeded its file limit")
            native.append(file_info(path, path.relative_to(bundle)))
    require(native, "Built application has no native binaries")
    helper = bundle / "_internal/helpers/FormbridgeWorker.exe"
    require(helper.is_file(), "Built console companion is missing")
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(helper))
    embedded = []
    for name, entry in sorted(archive.toc.items()):
        if entry[-1] == "b":
            require(len(embedded) < 10_000 and 0 <= entry[2] <= 512 * 1024 * 1024,
                    "Embedded native binary inventory exceeded its limits")
            data = archive.extract(name)
            require(isinstance(data, bytes), "Embedded native binary could not be read")
            embedded.append({"path": name.replace("\\", "/"), "bytes": len(data),
                             "sha256": hashlib.sha256(data).hexdigest()})
    require(embedded, "Console companion has no embedded native binary inventory")
    manifest = {"format": "quickcap-windows-build-manifest-v1", "sourceCommit": os.environ.get("GITHUB_SHA", "local-uncommitted"),
                "python": platform.python_version(), "platform": platform.platform(), "packages": packages,
                "notices": notice_inventory, "nativeFiles": native,
                "embeddedNativeFiles": {"container": helper.relative_to(bundle).as_posix(), "files": embedded},
                "ocrBundled": False}
    target = bundle / "BUILD_MANIFEST.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"manifestSHA256": hashlib.sha256(target.read_bytes()).hexdigest(), "noticeFiles": len(notice_inventory),
            "nativeFiles": len(native), "embeddedNativeFiles": len(embedded), "packages": packages,
            "python": manifest["python"], "ocrBundled": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(args.bundle), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
