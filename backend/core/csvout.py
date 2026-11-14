"""CSV downloads. Cells that a spreadsheet could run as a formula are neutralised; Excel gets a UTF-8 BOM so Arabic opens correctly."""
import csv
import io

from django.http import HttpResponse

DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(DANGEROUS) else text


def csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([cell(h) for h in header])
    for row in rows:
        writer.writerow([cell(c) for c in row])
    res = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    res["Content-Disposition"] = f'attachment; filename="{filename}"'
    res["X-Content-Type-Options"] = "nosniff"
    return res
