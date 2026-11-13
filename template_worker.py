"""Isolated local spreadsheet parsing and export. Never logs file contents."""
import base64
import json
import sys


def main():
    try:
        import templates
        request = json.load(sys.stdin)
        data = base64.b64decode(request["data"], validate=True)
        if request["operation"] == "inspect":
            result = templates.inspect_template(data, request["filename"], sheet=request.get("sheet"), header_row=request.get("headerRow"))
        elif request["operation"] == "fill":
            output = templates.fill_template(data, request["filename"], request["spec"], request["mappings"], request["schema"], request["rows"], export_format=request.get("exportFormat"))
            result = {"data": base64.b64encode(output).decode()}
        else:
            raise ValueError("Unknown template operation.")
        response = {"result": result}
    except ValueError as exc:
        response = {"error": str(exc)[:500]}
    except Exception:
        response = {"error": "The spreadsheet could not be processed safely. Check its format and installed requirements."}
    print(json.dumps(response, ensure_ascii=True))


if __name__ == "__main__":
    main()
