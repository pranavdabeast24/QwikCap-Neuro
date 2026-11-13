"""Prove real fictional PDF extraction populates real template downloads."""
import base64
import csv
import hashlib
import http.cookiejar
import io
import json
from pathlib import Path
import tempfile
import threading
import urllib.error
import urllib.request

import openpyxl
from server import Server, Workspace

ROOT = Path(__file__).resolve().parent


def main():
    answer_key = json.loads((ROOT / "samples/answer-key.json").read_text())["records"]
    manifest = json.loads((ROOT / "spreadsheets/template-manifest.json").read_text())
    report = {"notice": "Fictional generated forms only. No patient records.", "documents": len(answer_key), "extractedMatches": 0, "extractedFields": 0, "exports": [], "gates": []}
    output_dir = ROOT / "spreadsheets"
    with tempfile.TemporaryDirectory(prefix="formbridge-flow-") as assets:
        workspace = Workspace(assets)
        server = Server(("127.0.0.1", 0), workspace)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        thread.start()
        address = f"http://127.0.0.1:{server.server_port}"
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener.open(address).read()
        state = json.load(opener.open(address + "/api/state"))

        def post(path, payload):
            nonlocal state
            request = urllib.request.Request(address + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", "X-CSRF-Token": state["csrfToken"]})
            state = json.load(opener.open(request, timeout=240))
            return state

        def download(kind):
            return opener.open(address + f"/api/template/export?format={kind}&expectedRevision={state['template']['revision']}", timeout=60).read()

        def blocked(label):
            try:
                download("csv")
            except urllib.error.HTTPError as error:
                assert error.code == 400, (label, error.code)
                report["gates"].append({"case": label, "status": "blocked"})
            else:
                raise AssertionError(label + " incorrectly allowed an export")

        try:
            for item in answer_key:
                data = (ROOT / "samples" / item["file"]).read_bytes()
                post("/api/upload", {"filename": item["file"], "data": base64.b64encode(data).decode()})
                actual = state["records"][-1]["values"]
                expected = {key: str(value) for key, value in item["expected"].items()}
                assert actual == expected, (item["file"], actual, expected)
                report["extractedMatches"] += len(expected)
                report["extractedFields"] += len(expected)

            for index, name in enumerate(("redcap", "friendly", "csv")):
                config = manifest[name]
                post("/api/template/sample", {"name": name})
                assert state["template"]["sheet"] == config["sheet"]
                assert state["template"]["headerRow"] == config["headerRow"]
                assert len(state["templatePreview"]["rows"]) == len(answer_key)
                if index == 0:
                    blocked("unmapped columns")
                post("/api/template/mapping", {"mappings": config["mappings"], "confirmed": False, "expectedRevision": state["template"]["revision"]})
                if index == 0:
                    blocked("unconfirmed column mapping")
                post("/api/template/mapping", {"mappings": config["mappings"], "confirmed": True, "expectedRevision": state["template"]["revision"]})
                if index == 0:
                    blocked("unapproved records")
                    for record in list(state["records"]):
                        post("/api/record", {"id": record["id"], "values": record["values"], "confirmed": [field["name"] for field in state["schema"]], "reviewer": "Fictional verification", "approve": True, "expectedRevision": record["revision"]})
                assert state["templatePreview"]["ready"], state["templatePreview"]["errors"]
                headers = [column["name"] for column in state["template"]["columns"]]
                expected_rows = [{header: str(item["expected"][config["mappings"][header]]) for header in headers} for item in answer_key]
                for row, expected in zip(state["templatePreview"]["rows"], expected_rows):
                    assert row["values"] == expected
                formats = ("xlsx", "csv") if name != "csv" else ("csv",)
                for kind in formats:
                    data = download(kind)
                    if kind == "csv":
                        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
                        assert reader.fieldnames == headers
                        assert list(reader) == expected_rows
                    else:
                        book = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
                        assert book.sheetnames == [config["sheet"]]
                        sheet = book[config["sheet"]]
                        assert [sheet.cell(config["headerRow"], col + 1).value for col in range(len(headers))] == headers
                        for row_index, expected in enumerate(expected_rows, start=config["headerRow"] + 1):
                            actual = {header: "" if sheet.cell(row_index, col + 1).value is None else str(sheet.cell(row_index, col + 1).value) for col, header in enumerate(headers)}
                            assert actual == expected, (name, row_index, actual, expected)
                            assert all(sheet.cell(row_index, col + 1).data_type != "f" for col in range(len(headers)))
                            assert not sheet.row_dimensions[row_index].hidden
                        identifier_index = headers.index(next(header for header, field in config["mappings"].items() if field == "record_id")) + 1
                        assert sheet.cell(config["headerRow"] + 1, identifier_index).data_type == "s"
                        for row in sheet.iter_rows(min_row=config["headerRow"] + len(expected_rows) + 1):
                            assert all(cell.value is None for cell in row)
                        book.close()
                    filename = f"filled-{name}.{kind}"
                    if name != "csv":
                        (output_dir / filename).write_bytes(data)
                    report["exports"].append({"template": config["filename"], "format": kind, "records": len(expected_rows), "cellsCompared": len(expected_rows) * len(headers), "match": True, "sha256": hashlib.sha256(data).hexdigest(), "output": filename if name != "csv" else None})
            report["cellsCompared"] = sum(item["cellsCompared"] for item in report["exports"])
            report["status"] = "passed"
        finally:
            workspace.stop_jobs()
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
    destination = ROOT / "verification/spreadsheet-results.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {report['extractedMatches']}/{report['extractedFields']} extracted fields and {report['cellsCompared']} exported cells across {len(report['exports'])} real downloads.")
    print(f"Saved completed practice workbooks and CSVs in {output_dir}")


if __name__ == "__main__":
    main()
