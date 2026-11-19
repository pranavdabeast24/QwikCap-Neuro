"""Run local extraction diagnostics on an explicitly named synthetic PDF folder.

This does not drive the desktop UI, create reviews, approve records or export a
spreadsheet. Answer keys are never opened. Keep diagnostic data outside Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extraction_profiles import canonical_schema, PATIENT_PROFILES
from pipeline import process_document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forms-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(PATIENT_PROFILES), default="pace-printed-v1")
    args = parser.parse_args()
    source, output = args.forms_dir, args.output
    if source.is_symlink() or not source.is_dir():
        parser.error("Name an existing, non-symlink synthetic forms folder.")
    if output.is_symlink() or source.resolve() in output.resolve().parents:
        parser.error("Keep diagnostics outside the input folder; do not use an output symlink.")
    files = sorted(p for p in source.iterdir() if p.suffix.casefold() == ".pdf")
    if not 1 <= len(files) <= 1000 or any(p.is_symlink() or not p.is_file() for p in files):
        parser.error("Use one folder containing 1–1000 regular PDF files.")
    documents = []
    for index, path in enumerate(files, 1):
        if path.stat().st_size > 12 * 1024 * 1024:
            parser.error("A PDF exceeds the app's 12 MiB limit.")
        data = path.read_bytes()
        with tempfile.TemporaryDirectory(prefix="quickcap-pace-diagnostic-") as folder:
            result = process_document(data, path.name, canonical_schema(args.profile), Path(folder), "diagnostic")
        documents.append({"filename": path.name, "sha256": hashlib.sha256(data).hexdigest(),
                          "pageCount": len(result["pages"]),
                          "result": {key: result[key] for key in
                                     ("values", "evidence", "issues", "applicableFields", "sourceContext")}})
        print(f"Extracted {index}/{len(files)} synthetic PDFs locally", flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"format": "quickcap-pace-extraction-diagnostics-v1", "diagnosticOnly": True,
              "desktopUIUsed": False, "answerKeysRead": False, "profile": args.profile, "documents": documents}
    serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    with output.open("x", encoding="utf-8") as stream:
        stream.write(serialized)
    output.chmod(0o600)
    print(json.dumps({"documents": len(documents), "pages": sum(d["pageCount"] for d in documents),
                      "applicableFields": sum(len(d["result"]["applicableFields"]) for d in documents),
                      "blockingIssues": sum(len(d["result"]["sourceContext"]["blockingIssues"]) for d in documents)}))


if __name__ == "__main__":
    main()
