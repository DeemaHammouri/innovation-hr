"""Objectives 8 and 9: the lead record, phone and email normalisation, database uniqueness, search/filter/order/paginate, Excel and CSV import."""
import io
import threading

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase
from openpyxl import Workbook, load_workbook
from rest_framework.exceptions import ValidationError

from accounts.models import Department, User
from leads import importer, services
from leads.models import ImportBatch, Lead
from leads.normalize import normalize_email, normalize_phone

from .tests import LeadCase


class NormaliseTests(LeadCase):
    CASES = {
        "0797707154": "+962797707154",
        "+962797707154": "+962797707154",
        "+962 79 770 7154": "+962797707154",
        "00962797707154": "+962797707154",
        "962797707154": "+962797707154",
        "٠٧٩٧٧٠٧١٥٤": "+962797707154",  # Arabic-Indic digits
        "(079) 770-7154": "+962797707154",
        "00 44 20 7946 0958": "+442079460958",
        "+44 20 7946 0958": "+442079460958",
        "123456": "",  # too short to be a number
        "": "",
    }

    def test_phone_forms(self):
        for raw, expected in self.CASES.items():
            self.assertEqual(normalize_phone(raw), expected, raw)

    def test_email_is_lowercased_and_trimmed(self):
        self.assertEqual(normalize_email("  Hassan@AlNoor.Example "), "hassan@alnoor.example")

    def test_stored_values_are_normalised(self):
        lead = Lead.objects.create(company_name="A", phone="0797707154", email="Sam@X.COM", created_by=self.mkt)
        lead.refresh_from_db()
        self.assertEqual((lead.phone, lead.phone_key, lead.email, lead.email_key), ("+962797707154", "+962797707154", "sam@x.com", "sam@x.com"))


class LeadFieldsTests(LeadCase):
    def post(self, **over):
        self.as_role("marketing")
        body = {"company_name": "Acme", "contact_name": "Sam", "position": "CFO", "phone": "0797707154", "email": "", "location": "Amman"}
        body.update(over)
        return self.client.post("/api/leads/", body, format="json")

    def test_all_six_fields_are_kept(self):
        res = self.post()
        self.assertEqual(res.status_code, 201, res.data)
        for field, value in (("company_name", "Acme"), ("contact_name", "Sam"), ("position", "CFO"), ("phone", "+962797707154"), ("location", "Amman")):
            self.assertEqual(res.data[field], value)

    def test_phone_or_email_is_required(self):
        res = self.post(phone="", email="")
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.data)
        self.assertEqual(self.post(phone="", email="a@b.example").status_code, 201)

    def test_zero_seven_and_plus_962_are_the_same_lead(self):
        self.assertEqual(self.post(phone="0797707154").status_code, 201)
        second = self.post(company_name="Other", phone="+962797707154")
        self.assertEqual(second.status_code, 400)
        self.assertIn("duplicate", second.data)
        self.assertEqual(self.post(company_name="Third", phone="00962 79 770 7154").status_code, 400)
        self.assertEqual(Lead.objects.count(), 1)

    def test_email_case_does_not_make_a_new_lead(self):
        self.post(phone="", email="Sam@Acme.example")
        self.assertEqual(self.post(company_name="B", phone="", email="sam@ACME.example").status_code, 400)

    def test_editing_into_a_duplicate_is_refused_cleanly(self):
        self.post(phone="0797707154")
        other = self.post(company_name="B", phone="0791111111").data["id"]
        res = self.client.patch(f"/api/leads/{other}/", {"phone": "+962 79 770 7154"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("duplicate", res.data)

    def test_database_itself_refuses_a_second_open_lead(self):
        self.mk(phone="0797707154")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Lead.objects.create(ref="LD-X1", company_name="Dup", phone="0797707154", created_by=self.mkt)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Lead.objects.create(ref="LD-X2", company_name="Dup", phone="", email="A@B.example", created_by=self.mkt)
            Lead.objects.create(ref="LD-X3", company_name="Dup2", phone="", email="a@b.EXAMPLE", created_by=self.mkt)

    def test_an_archived_lead_does_not_hold_the_number(self):
        first = self.mk(phone="0797707154")
        services.archive(self.head, first, "test")
        self.assertEqual(self.post(phone="0797707154").status_code, 201)
        res = self.client.post(f"/api/leads/{first.pk}/restore/")  # the head restores: a clash now
        self.as_role("commercial_head")
        res = self.client.post(f"/api/leads/{first.pk}/restore/")
        self.assertEqual(res.status_code, 400)


class SearchFilterOrderPaginateTests(LeadCase):
    def setUp(self):
        super().setUp()
        self.a = self.mk(company_name="Alpha Trading", contact_name="Hassan", position="Owner", location="Amman", phone="0791000001")
        self.b = self.mk(company_name="Beta Foods", contact_name="Maya", position="Buyer", location="Irbid", phone="0791000002", status="contacted", assigned=self.member)
        self.c = self.mk(company_name="Gamma Tech", contact_name="Omar", position="CTO", location="Aqaba", phone="0791000003", status="rejected", assigned=self.member)
        self.as_role("commercial_head")

    def ids(self, query):
        res = self.client.get(f"/api/leads/?{query}")
        self.assertEqual(res.status_code, 200)
        return [x["id"] for x in res.data["results"]]

    def test_search_covers_every_field_including_a_typed_phone_in_any_form(self):
        self.assertEqual(self.ids("search=alpha"), [self.a.id])
        self.assertEqual(self.ids("search=maya"), [self.b.id])
        self.assertEqual(self.ids("search=cto"), [self.c.id])  # position
        self.assertEqual(self.ids("search=irbid"), [self.b.id])  # location
        self.assertEqual(self.ids("search=0791000002"), [self.b.id])  # typed as 07..., stored as +9627...
        self.assertEqual(self.ids("search=%2B962791000002"), [self.b.id])

    def test_filters(self):
        self.assertEqual(sorted(self.ids("status=contacted,rejected")), sorted([self.b.id, self.c.id]))
        self.assertEqual(self.ids(f"assigned_to={self.member.id}&status=rejected"), [self.c.id])
        self.assertEqual(self.ids("assigned_to=none"), [self.a.id])

    def test_ordering(self):
        self.assertEqual(self.ids("ordering=company_name"), [self.a.id, self.b.id, self.c.id])
        self.assertEqual(self.ids("ordering=-company_name"), [self.c.id, self.b.id, self.a.id])

    def test_pagination(self):
        for i in range(30):
            self.mk(company_name=f"Zed {i:02d}", phone=f"07920000{i:02d}")
        res = self.client.get("/api/leads/?page_size=10&ordering=company_name")
        self.assertEqual((res.data["count"], len(res.data["results"])), (33, 10))
        self.assertTrue(res.data["next"])
        last = self.client.get("/api/leads/?page_size=10&page=4&ordering=company_name")
        self.assertEqual(len(last.data["results"]), 3)


class ConcurrentInsertTests(TransactionTestCase):
    """Two people save the same number at the same moment: one lead, and the loser gets the clean duplicate error."""

    def test_two_simultaneous_inserts_make_one_lead_and_one_clean_error(self):
        dept = Department.objects.create(name="Marketing")
        user = User.objects.create_user("mk@x.com", "pw-pw-pw-pw-1", full_name="Mk", department=dept, role="member")
        barrier = threading.Barrier(2)
        results = []

        def work(name):
            try:
                barrier.wait(timeout=5)
                services.create_lead(user, {"company_name": name, "phone": "0797707154"})
                results.append("created")
            except ValidationError as exc:
                results.append(("clean-error", sorted(exc.detail)))
            except Exception as exc:  # anything else is a failure of the requirement
                results.append(("unexpected", repr(exc)))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=work, args=(n,)) for n in ("First Co", "Second Co")]
        [t.start() for t in threads]
        [t.join(30) for t in threads]
        self.assertEqual(Lead.objects.count(), 1, results)
        self.assertEqual(results.count("created"), 1, results)
        self.assertIn(("clean-error", ["duplicate"]), results)


class ListQueryCostTests(LeadCase):
    def test_list_cost_does_not_grow_with_rows(self):
        from django.test.utils import CaptureQueriesContext

        self.as_role("commercial_head")
        self.mk()

        def cost():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.client.get("/api/leads/?page_size=100").status_code, 200)
            return len(ctx)

        few = cost()
        for _ in range(8):
            self.mk()
        self.assertEqual(cost(), few)


def xlsx_bytes(rows, header=("Company", "Name", "Position", "Phone", "Email", "Location", "Source", "Notes")):
    wb = Workbook()
    ws = wb.active
    if header:
        ws.append(list(header))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload(content, name="leads.xlsx"):
    return SimpleUploadedFile(name, content if isinstance(content, bytes) else content.encode("utf-8"))


class ExcelImportTests(LeadCase):
    def preview(self, content, name="leads.xlsx"):
        self.as_role("marketing")
        return self.client.post("/api/leads/import/preview/", {"file": upload(content, name)}, format="multipart")

    def confirm(self, content, name="leads.xlsx"):
        self.as_role("marketing")
        return self.client.post("/api/leads/import/confirm/", {"file": upload(content, name)}, format="multipart")

    def test_both_templates_download_open_and_import(self):
        self.as_role("marketing")
        for lang, first_header in (("en", "Company"), ("ar", "اسم الشركة")):
            res = self.client.get(f"/api/leads/import/template/?lang={lang}")
            self.assertEqual(res.status_code, 200)
            self.assertIn("spreadsheetml", res["Content-Type"])
            wb = load_workbook(io.BytesIO(res.content))
            self.assertEqual(wb.worksheets[0]["A1"].value, first_header)
            self.assertEqual(len(wb.worksheets), 2)  # the data sheet and the instructions
            out = self.preview(res.content)
            self.assertEqual(out.data["summary"], {"total": 2, "ok": 2, "errors": 0, "duplicates": 0}, lang)

    def test_csv_template_still_works_in_both_languages(self):
        self.as_role("marketing")
        for lang in ("en", "ar"):
            body = self.client.get(f"/api/leads/import/template/?file=csv&lang={lang}").content
            self.assertEqual(self.preview(body, "t.csv").data["summary"]["ok"], 2)

    def test_headers_in_english_arabic_or_both(self):
        rows = [("Acme", "Sam", "CFO", "0791000010", "", "Amman", "Fair", "")]
        for header in (
            ("Company", "Name", "Position", "Phone", "Email", "Location", "Source", "Notes"),
            ("اسم الشركة", "الاسم", "المسمى الوظيفي", "الهاتف", "البريد الإلكتروني", "الموقع", "المصدر", "ملاحظات"),
            ("Company / الشركة", "Name / الاسم", "Position / المنصب", "Phone / الجوال", "Email / البريد", "Location / المدينة", "Source / المصدر", "Notes / ملاحظة"),
            ("COMPANY NAME", "contact_name", "Job Title", "Mobile", "E-mail", "City", "source", "notes"),
        ):
            res = self.preview(xlsx_bytes(rows, header))
            self.assertEqual(res.status_code, 200, (header, res.data))
            row = res.data["rows"][0]
            self.assertEqual((row["company_name"], row["position"], row["location"], row["state"]), ("Acme", "CFO", "Amman", "ok"), header)

    def test_numeric_phone_cells_keep_their_digits(self):
        for cell in (791000011, 791000011.0):  # Excel stores a typed number as a number; no ".0" may leak into the phone
            res = self.preview(xlsx_bytes([("Acme", "", "", cell, "", "", "", "")]))
            self.assertEqual((res.data["rows"][0]["phone"], res.data["rows"][0]["state"]), ("791000011", "ok"))

    def test_skips_invalid_and_duplicate_rows_with_a_full_report(self):
        self.mk(phone="0791000020", company_name="Existing")
        rows = [
            ("Good One", "", "", "0791000021", "", "", "", ""),
            ("Bad Phone", "", "", "12", "", "", "", ""),
            ("Dup of DB", "", "", "+962 79 100 0020", "", "", "", ""),
            ("Good Two", "", "", "", "Two@Example.com", "", "", ""),
            ("Dup in file", "", "", "0791000021", "", "", "", ""),
            ("Dup email in file", "", "", "", "two@example.com", "", "", ""),
            ("", "No company", "", "0791000030", "", "", "", ""),
        ]
        res = self.confirm(xlsx_bytes(rows))
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["total_rows"], res.data["imported_count"], res.data["skipped_errors"], res.data["skipped_duplicates"]), (7, 2, 2, 3))
        report = {r["row"]: r for r in res.data["skip_report"]}
        self.assertEqual(sorted(report), [3, 4, 6, 7, 8])  # spreadsheet row numbers
        self.assertEqual(report[4]["state"], "duplicate")
        self.assertTrue(report[4]["duplicate_of"])
        self.assertEqual(report[6]["duplicate_in_file"], 2)
        self.assertEqual(report[7]["duplicate_in_file"], 5)
        self.assertEqual(report[3]["errors"][0]["field"], "phone")
        self.assertEqual(Lead.objects.filter(batch__isnull=False).count(), 2)
        self.assertEqual(Lead.objects.get(email="two@example.com").company_name, "Good Two")
        self.assertEqual(ImportBatch.objects.get().skip_report, res.data["skip_report"])

    def test_a_bad_row_does_not_hide_a_later_good_one(self):
        res = self.preview(xlsx_bytes([("A", "", "", "", "", "", "", ""), ("B", "", "", "0791000040", "", "", "", "")]))
        self.assertEqual([r["state"] for r in res.data["rows"]], ["error", "ok"])

    def test_wrong_type_and_broken_files_get_clear_errors(self):
        self.assertEqual(self.preview(b"%PDF-1.4", "leads.pdf").data["file"], [importer.MSG_EXT])
        self.assertEqual(self.preview(b"not a zip at all", "leads.xlsx").data["file"], [importer.MSG_XLSX])
        renamed = xlsx_bytes([("A", "", "", "0791000050", "", "", "", "")])
        self.assertEqual(self.preview(renamed, "leads.csv").data["file"], [importer.MSG_ENCODING])
        self.assertEqual(self.preview(b"", "leads.xlsx").data["file"], [importer.MSG_XLSX])
        self.assertEqual(self.preview(xlsx_bytes([], header=("Other", "Stuff"))).data["file"], [importer.MSG_COLUMNS])
        self.assertEqual(self.preview(xlsx_bytes([])).data["file"], [importer.MSG_EMPTY])

    def test_size_and_row_limits(self):
        self.assertEqual((importer.MAX_ROWS, importer.MAX_BYTES), (5000, 5 * 1024 * 1024))
        at_limit = xlsx_bytes([(f"Co {i}", "", "", f"07910{i:05d}", "", "", "", "") for i in range(importer.MAX_ROWS)])
        self.assertEqual(self.preview(at_limit).data["summary"]["total"], 5000)
        over = xlsx_bytes([(f"Co {i}", "", "", f"07910{i:05d}", "", "", "", "") for i in range(importer.MAX_ROWS + 1)])
        self.assertEqual(self.preview(over).data["file"], [importer.MSG_ROWS])
        big = SimpleUploadedFile("big.xlsx", b"0" * (importer.MAX_BYTES + 1))
        self.as_role("marketing")
        res = self.client.post("/api/leads/import/preview/", {"file": big}, format="multipart")
        self.assertEqual(res.data["file"], [importer.MSG_SIZE])

    def test_importing_the_same_file_twice_adds_nothing_the_second_time(self):
        content = xlsx_bytes([("Acme", "", "", "0791000060", "", "", "", "")])
        self.assertEqual(self.confirm(content).status_code, 201)
        again = self.confirm(content)
        self.assertEqual(again.status_code, 400)
        self.assertEqual(Lead.objects.count(), 1)

    def test_undone_import_can_be_imported_again(self):
        content = xlsx_bytes([("Acme", "", "", "0791000061", "", "", "", "")])
        batch = self.confirm(content).data["id"]
        self.assertEqual(self.client.post(f"/api/import-batches/{batch}/undo/").status_code, 200)
        self.assertEqual(self.confirm(content).status_code, 201)
