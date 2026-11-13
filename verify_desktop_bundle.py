"""Exercise real packaged workers with only the bundled fictional fixtures."""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import openpyxl
from desktop_model import DesktopSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.bundle.suffix == ".app":
        runtime = args.bundle / "Contents/Frameworks"
        resources = args.bundle / "Contents/Resources"
    else:
        runtime = args.bundle / "_internal"
        resources = runtime
    helper = runtime / "helpers" / ("FormbridgeWorker.exe" if os.name == "nt" else "FormbridgeWorker")
    if not helper.is_file():
        raise SystemExit("The packaged companion worker is missing.")
    answer_key = json.loads((resources / "samples/answer-key.json").read_text())["records"]
    manifest = json.loads((resources / "spreadsheets/template-manifest.json").read_text())
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"notice": "Generated fictional forms only. No patient data.", "bundle": args.bundle.name,
              "documents": 0, "extractedMatches": 0, "exports": [], "method": "DesktopSession with real packaged companion workers and bundled fixtures"}
    session = DesktopSession()
    session.set_schema(json.loads((resources / "samples/sample-schema.json").read_text()))
    # An empty search path proves the bundled Mac OCR helper needs no Swift CLI.
    environment = {"PATH": ""} if sys.platform == "darwin" else {}
    try:
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", str(runtime), create=True), patch.dict(os.environ, environment):
            for fixture in answer_key:
                item = session.add_document((resources / "samples" / fixture["file"]).read_bytes(), fixture["file"])
                expected = {key: str(value) for key, value in fixture["expected"].items()}
                assert item["values"] == expected, (fixture["file"], item["values"])
                report["documents"] += 1
                report["extractedMatches"] += len(expected)
                session.review_record(item["id"], item["values"], list(expected), "Fictional desktop verifier", True, item["revision"])
            for name in ["redcap", "friendly"]:
                spec = manifest[name]
                session.import_template(resources / "spreadsheets" / spec["filename"])
                session.set_mapping(spec["mappings"], True)
                revision = session.workspace.template["revision"]
                for kind in ["xlsx", "csv"]:
                    target = args.output / f"desktop-filled-{name}.{kind}"
                    data = session.export(kind, target, expected_revision=revision)
                    headers = list(spec["mappings"])
                    fields = list(spec["mappings"].values())
                    if kind == "csv":
                        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig"))))
                        assert rows[0] == headers
                        actual = rows[1:]
                    else:
                        workbook = openpyxl.load_workbook(io.BytesIO(data))
                        sheet = workbook[spec["sheet"]]
                        h = spec["headerRow"]
                        assert [sheet.cell(h, c).value for c in range(1, len(headers) + 1)] == headers
                        actual = [["" if sheet.cell(h + r + 1, c).value is None else str(sheet.cell(h + r + 1, c).value)
                                   for c in range(1, len(headers) + 1)] for r in range(10)]
                    expected_rows = [[str(fixture["expected"][field]) for field in fields] for fixture in answer_key]
                    assert actual == expected_rows
                    report["exports"].append({"file": target.name, "records": 10, "cellsMatched": 60})
            report["status"] = "passed"
            (args.output / "desktop-bundle-results.json").write_text(json.dumps(report, indent=2) + "\n")
    finally:
        session.close()
    print(f"Packaged desktop workers matched {report['extractedMatches']} extracted fields and 240 exported cells.")


if __name__ == "__main__":
    main()
