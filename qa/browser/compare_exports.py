"""Compares the JSON, CSV, Excel and PDF of one report downloaded by phase4.js. Usage: python compare_exports.py <folder> <lang>"""
import csv, io, json, sys
from openpyxl import load_workbook
from pypdf import PdfReader

folder, lang = sys.argv[1], sys.argv[2]
data = json.load(open(f"{folder}/{lang}-report.json", encoding="utf-8"))
want = []
for s in data["series"]:
    for p in s["points"]:
        want.append((s["key"], p.get("label_en") or p["key"], "" if p["value"] is None else str(p["value"])))

def norm(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v

def same(a, b):
    return [(x, y, norm(z)) for x, y, z in a] == [(x, y, norm(z)) for x, y, z in b]

rows = list(csv.reader(io.StringIO(open(f"{folder}/{lang}-report.csv", encoding="utf-8-sig").read())))[1:]
ok_csv = same([(r[1], r[2], r[3]) for r in rows], want)
ws = load_workbook(f"{folder}/{lang}-report.xlsx").active
ok_xlsx = same([(r[1].value, r[2].value, "" if r[3].value is None else str(r[3].value)) for r in ws.iter_rows(min_row=2)], want)
text = "\n".join(p.extract_text() or "" for p in PdfReader(f"{folder}/{lang}-report.pdf").pages)
nums = [v for _, _, v in want if v != ""]
missing = [v for v in nums if v not in text and f"{float(v):g}" not in text]
print(f"{lang}: {len(want)} values in the JSON")
print(("PASS" if ok_csv else "FAIL"), "CSV carries the same values, in the same order")
print(("PASS" if ok_xlsx else "FAIL"), "Excel carries the same values, in the same order")
print(("PASS" if not missing and want else "FAIL"), "PDF text contains every number" + (f" (missing {missing[:5]})" if missing else ""))
sys.exit(0 if ok_csv and ok_xlsx and not missing and want else 1)
