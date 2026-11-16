"""Excel and PDF versions of a report. Both are written from the same flat rows as the CSV (`series.csv_rows`), so a number can never
differ between the JSON, the CSV, the workbook and the PDF."""
import io

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font

from core.csvout import cell
from documents import model
from documents.pdf import build_pdf

HEADER = ["report", "series", "label", "value", "unit", "based_on_records"]
HEAD_PAIRS = [("Report", "التقرير"), ("Series", "المجموعة"), ("Item", "البند"), ("Value", "القيمة"), ("Unit", "الوحدة"), ("Based on", "عدد السجلات")]
TITLES = {"funnel": ("Funnel report", "تقرير مسار المبيعات"), "revenue": ("Revenue report", "تقرير الإيرادات"), "forecast": ("Forecast report", "تقرير التوقعات"),
          "operations": ("Operations report", "تقرير العمليات"), "hr": ("HR report", "تقرير الموارد البشرية")}


def xlsx_response(filename, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    ws.append(HEADER)
    for c in ws[1]:
        c.font = Font(bold=True)
    for row in rows:
        ws.append([v if isinstance(v, (int, float)) else cell(v) for v in row])
    for r in ws.iter_rows(min_row=2):
        for c in r:
            if isinstance(c.value, str):
                c.data_type = "s"  # text, never a formula
    ws.freeze_panes = "A2"
    for col, width in zip("ABCDEF", (14, 26, 30, 14, 14, 18)):
        ws.column_dimensions[col].width = width
    out = io.BytesIO()
    wb.save(out)
    res = HttpResponse(out.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    res["Content-Disposition"] = f'attachment; filename="{filename}"'
    res["X-Content-Type-Options"] = "nosniff"
    return res


def pdf_response(filename, section, period, rows, lang="en"):
    doc = model.Doc(
        kind="report", title=TITLES.get(section, ("Report", "تقرير")),
        meta=[(("Period", "الفترة"), f"{period['from']} - {period['to']}")],
        blocks=[model.Table(headers=HEAD_PAIRS, rows=[[("" if v is None else str(v)) for v in row] for row in rows], aligns=["start", "start", "start", "end", "start", "end"], widths=[1.2, 2.2, 2.6, 1.2, 1.2, 1.2])],
        filename=filename,
    )
    res = HttpResponse(build_pdf(doc, lang), content_type="application/pdf")
    res["Content-Disposition"] = f'attachment; filename="{filename}"'
    res["X-Content-Type-Options"] = "nosniff"
    return res
