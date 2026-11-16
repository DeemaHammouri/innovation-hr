"""Objective 21: one set of numbers in JSON, CSV, Excel and PDF; and the activity log of every task step cannot be edited or removed."""
import csv
import io
from datetime import timedelta

from django.utils import timezone
from openpyxl import load_workbook
from pypdf import PdfReader

from audit.models import AuditEntry, ImmutableError
from operations.tests_lifecycle import LCase


def norm(v):
    """Compare numbers as numbers (Excel stores 100.0 as 100), text as text."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


def same(a, b):
    return [(x, y, norm(z)) for x, y, z in a] == [(x, y, norm(z)) for x, y, z in b]


class SameNumbersTests(LCase):
    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        for i in range(3):
            t = self.task(due=today - timedelta(days=i))
            if i == 0:
                self.do(self.omem, t, "start")
                self.do(self.omem, t, "submit")
                self.do(self.ohead, t, "approve")
        self.task(due=today + timedelta(days=4))
        self.as_user(self.ohead)

    def json_rows(self):
        data = self.client.get("/api/reports/operations/").data
        rows = []
        for s in data["series"]:
            for p in s["points"]:
                rows.append((s["key"], p.get("label_en") or p["key"], "" if p["value"] is None else str(p["value"])))
        return rows

    def test_json_csv_excel_and_pdf_carry_the_same_numbers(self):
        want = self.json_rows()
        self.assertTrue(want)
        csv_res = self.client.get("/api/reports/operations/export/")
        self.assertEqual(csv_res.status_code, 200)
        csv_rows = list(csv.reader(io.StringIO(csv_res.content.decode("utf-8-sig"))))[1:]
        self.assertTrue(same([(r[1], r[2], r[3]) for r in csv_rows], want))

        xl = self.client.get("/api/reports/operations/export/?fmt=xlsx")
        self.assertEqual((xl.status_code, xl["Content-Type"].startswith("application/vnd.openxmlformats")), (200, True))
        ws = load_workbook(io.BytesIO(xl.content)).active
        xl_rows = [(r[1].value, r[2].value, "" if r[3].value is None else str(r[3].value)) for r in ws.iter_rows(min_row=2)]
        self.assertTrue(same(xl_rows, want))

        for lang in ("en", "ar"):
            pdf = self.client.get(f"/api/reports/operations/export/?fmt=pdf&lang={lang}")
            self.assertEqual((pdf.status_code, pdf.content[:4]), (200, b"%PDF"))
            text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages)
            for series_key, _, value in want:
                if value != "":
                    self.assertIn(value, text, (lang, series_key))  # the PDF prints the same text the JSON holds

    def test_an_unknown_format_is_refused_and_the_permissions_are_the_same_for_every_format(self):
        self.assertEqual(self.client.get("/api/reports/operations/export/?fmt=exe").status_code, 400)
        for fmt in ("csv", "xlsx", "pdf"):
            self.as_role("operation_member")
            self.assertEqual(self.client.get(f"/api/reports/operations/export/?fmt={fmt}").status_code, 403, fmt)
            self.as_role("commercial_head")
            self.assertEqual(self.client.get(f"/api/reports/operations/export/?fmt={fmt}").status_code, 403, fmt)

    def test_the_task_series_counts_what_the_lifecycle_did(self):
        tasks = next(s for s in self.client.get("/api/reports/operations/").data["series"] if s["key"] == "tasks")
        got = {p["key"]: p["value"] for p in tasks["points"]}
        self.assertEqual((got["done"], got["overdue"], got["open"]), (1, 2, 0))  # the open task is due after the period ends


class ActivityLogTests(LCase):
    def test_every_step_is_written_once_and_cannot_be_changed_or_deleted(self):
        t = self.task()
        before = AuditEntry.objects.count()
        for action, body in (("start", {}), ("escalate", {"reason": "Late"}), ("progress", {"progress": 50}), ("wait", {"reason": "Client"}), ("resume", {}), ("submit", {}), ("return", None), ("approve", None)):
            who = self.ohead if action in ("return", "approve") else self.omem
            if action == "return":
                self.do(who, t, "return", {"comment": "Fix it"})
                self.do(self.omem, t, "submit")
                continue
            self.do(who, t, action, body)
        entries = list(AuditEntry.objects.filter(object_id=t.client_id).order_by("id"))
        actions = [e.action for e in entries]
        for a in ("task_started", "task_progress", "task_waiting", "task_resumed", "task_submitted", "task_returned", "task_approved", "task_escalated"):
            self.assertEqual(actions.count(a) >= 1, True, a)
        self.assertEqual(actions.count("task_started"), 1)  # not duplicated
        self.assertGreater(AuditEntry.objects.count(), before)
        for e in entries:
            e.comment = "edited"
            with self.assertRaises(ImmutableError):
                e.save()
            with self.assertRaises(ImmutableError):
                e.delete()
        with self.assertRaises(ImmutableError):
            AuditEntry.objects.filter(pk__in=[e.pk for e in entries]).update(comment="x")
        with self.assertRaises(ImmutableError):
            AuditEntry.objects.filter(pk__in=[e.pk for e in entries]).delete()

    def test_a_refused_step_writes_nothing(self):
        t = self.task()
        n = AuditEntry.objects.count()
        self.assertEqual(self.do(self.omem, t, "submit").status_code, 400)
        self.assertEqual(self.do(self.omem2, t, "start").status_code, 403)
        self.assertEqual(AuditEntry.objects.count(), n)
