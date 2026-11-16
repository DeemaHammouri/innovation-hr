"""Objective 14: the quotation state machine, drawn signature with the company stamp, the yearly number, client signing, signed copy."""
import re
import threading
from datetime import date
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connections
from django.test import TransactionTestCase
from rest_framework.exceptions import ValidationError

from accounts.models import DEPARTMENT_NAMES, Department, User
from clients import services as client_services
from clients.models import Client
from core.models import CompanyProfile, YearSequence
from core.testing import ensure_stamp, png_signature
from files.models import Attachment
from notifications.models import Notification
from quotations import services
from quotations.models import Quotation, QuotationLine
from quotations.tests import QCase, line

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def sig():
    return {"signature": png_signature()}


class PortalMixin:
    """A portal login for the client a quotation belongs to (made the way the real conversion makes it)."""

    def portal_user(self, q):
        client = getattr(q.lead, "client", None) or Client.objects.create(lead=q.lead, company_name=q.lead.company_name, email=f"c{q.pk}@client.example", status="prospect", created_by=self.head)
        if not client.portal_user_id:
            client_services.create_portal_account(client, self.head)
            client.refresh_from_db()
            User.objects.filter(pk=client.portal_user_id).update(must_change_password=False)
        return User.objects.get(pk=client.portal_user_id)


class StateMachineTests(PortalMixin, QCase):
    """Every action against every state: only the legal pairs work, everything else is refused whatever the screen showed."""

    # state -> actions that must succeed for the right person
    LEGAL = {
        "requested": {"assign", "start", "cancel"},
        "in_preparation": {"draft", "submit", "cancel"},
        "in_review": {"request-changes", "sign", "cancel"},
        "changes_requested": {"assign", "start", "cancel"},
        "signed": {"send", "cancel"},
        "sent": {"outcome", "signed-copy", "client-sign", "cancel"},
    }
    ACTORS = {"assign": "hr_head", "start": "hr_member", "draft": "hr_member", "submit": "hr_member", "request-changes": "commercial_head", "sign": "commercial_head",
              "send": "commercial_member", "outcome": "commercial_member", "signed-copy": "commercial_member", "cancel": "commercial_head"}

    def attempt(self, q, action):
        if action == "client-sign":
            self.as_user(self.portal_user(q))
            return self.client.post(f"/api/portal/quotations/{q.pk}/sign/", sig(), format="json").status_code
        actor = self.users[self.ACTORS[action]]
        body = {
            "assign": {"assigned_to": self.hr2.pk}, "draft": {"currency": "JOD", "valid_until": self.day(30), "lines": [line()]},
            "request-changes": {"comment": "Lower it"}, "sign": sig(), "outcome": {"outcome": "confirmed"}, "cancel": {"reason": "no"},
        }.get(action, {})
        self.as_user(actor)
        if action == "draft":
            return self.client.put(f"/api/quotations/{q.pk}/draft/", body, format="json").status_code
        if action == "signed-copy":
            return self.client.post(f"/api/quotations/{q.pk}/signed-copy/", {"file": SimpleUploadedFile("c.pdf", PDF, "application/pdf")}, format="multipart").status_code
        return self.client.post(f"/api/quotations/{q.pk}/{action}/", body, format="json").status_code

    def test_every_action_in_every_state(self):
        actions = sorted({a for acts in self.LEGAL.values() for a in acts} | {"outcome", "send", "sign"})
        wrong = []
        for state, legal in self.LEGAL.items():
            for action in actions:
                q = self.quote(state)
                code = self.attempt(q, action)
                ok = code in (200, 201)
                if ok != (action in legal):
                    wrong.append(f"{state} + {action} -> {code} (should {'work' if action in legal else 'be refused'})")
        self.assertEqual(wrong, [], "\n".join(wrong))

    def test_nothing_moves_a_finished_quotation(self):
        for end in ("confirmed", "rejected", "cancelled"):
            q = self.quote("sent")
            self.as_user(self.member)
            if end == "cancelled":
                self.act(self.head, q, "cancel", {"reason": "x"})
            else:
                self.act(self.member, q, "outcome", {"outcome": end, **({"rejection_reason": self.reason.pk} if end == "rejected" else {})})
            q.refresh_from_db()
            self.assertEqual(q.status, end)
            for action in ("start", "submit", "sign", "send", "outcome", "request-changes", "cancel", "assign"):
                actor = self.ACTORS.get(action, "commercial_head")
                self.as_user(self.users[actor])
                self.assertEqual(self.client.post(f"/api/quotations/{q.pk}/{action}/", {"comment": "x", "reason": "x", "outcome": "confirmed", "assigned_to": self.hr2.pk}, format="json").status_code in (400, 403), True, (end, action))


class AssignTests(QCase):
    def test_the_hr_head_hands_it_to_one_person_and_only_they_can_start_it(self):
        q = self.quote("requested")
        res = self.act(self.hr, q, "assign", {"assigned_to": self.hr2.pk})
        self.assertEqual((res.status_code, res.data["assigned_hr_name"]), (200, self.hr2.full_name))
        self.assertTrue(Notification.objects.filter(user=self.hr2, kind="quotation_assigned").exists())
        other = self.make_user("hr3@x.com", "HR", "member")
        self.assertEqual(self.act(other, q, "start").status_code, 403)
        self.assertEqual(self.act(self.hr2, q, "start").status_code, 200)

    def test_without_an_assignment_any_hr_person_may_start_as_before(self):
        q = self.quote("requested")
        self.assertEqual(self.act(self.hr2, q, "start").status_code, 200)

    def test_assignment_needs_the_capability_and_an_hr_person(self):
        q = self.quote("requested")
        for key in ("ceo", "commercial_head", "commercial_member", "hr_member", "operation_head", "marketing"):
            self.assertIn(self.act(self.users[key], q, "assign", {"assigned_to": self.hr2.pk}).status_code, (403, 404), key)
        self.assertEqual(self.act(self.hr, q, "assign", {"assigned_to": self.member.pk}).status_code, 400)

    def test_the_head_can_still_start_an_assigned_one(self):
        q = self.quote("requested")
        self.act(self.hr, q, "assign", {"assigned_to": self.hr2.pk})
        self.assertEqual(self.act(self.hr, q, "start").status_code, 200)


class DraftContentTests(QCase):
    def test_frequency_visits_and_payment_terms_are_saved_and_carried_to_the_next_version(self):
        q = self.quote("requested")
        services.start_preparing(self.hr, q)
        q = Quotation.objects.get(pk=q.pk)
        services.save_draft(self.hr, q, {"currency": "USD", "valid_until": self.day(30), "payment_terms": "50% now, 50% on delivery",
                                         "lines": [line(frequency="monthly", visits="4"), line(description="Audit", frequency="annual")]})
        v = q.versions.get(number=1)
        self.assertEqual((v.currency, v.payment_terms), ("USD", "50% now, 50% on delivery"))
        self.assertEqual([(l.frequency, l.visits) for l in v.lines.all()], [("monthly", 4), ("annual", None)])
        q = services.submit(self.hr, q)
        services.request_changes(self.head, q, "Lower the price")
        services.start_preparing(self.hr, q)
        v2 = q.versions.get(number=2)
        self.assertEqual(v2.payment_terms, "50% now, 50% on delivery")
        self.assertEqual([(l.frequency, l.visits) for l in v2.lines.all()], [("monthly", 4), ("annual", None)])

    def test_bad_values_are_refused(self):
        q = self.quote("in_preparation")
        for bad in ({"frequency": "weekly"}, {"visits": "x"}, {"visits": "-1"}):
            with self.assertRaises(ValidationError):
                services.save_draft(self.hr, q, {"currency": "JOD", "lines": [line(**bad)]})
        with self.assertRaises(ValidationError):
            services.save_draft(self.hr, q, {"currency": "JOD", "payment_terms": "x" * 2001, "lines": [line()]})

    def test_any_currency_code_is_accepted(self):
        q = self.quote("in_preparation")
        for code in ("EUR", "SAR", "AED", "KWD"):
            services.save_draft(self.hr, q, {"currency": code, "lines": [line()]})
            self.assertEqual(q.versions.get(number=1).currency, code)

    def test_returned_notes_are_shown_to_the_preparer(self):
        q = self.quote("in_review")
        self.act(self.head, q, "request-changes", {"comment": "Lower the monthly price"})
        self.as_user(self.hr2)
        data = self.client.get(f"/api/quotations/{q.pk}/").data
        self.assertEqual((data["status"], data["review_comment"]), ("changes_requested", "Lower the monthly price"))
        self.assertTrue(Notification.objects.filter(user=self.hr, kind="returned").exists())


class SigningTests(QCase):
    def test_signing_needs_a_drawn_signature(self):
        q = self.quote("in_review")
        for body, field in (({}, "signature"), ({"signature": "nonsense"}, "signature"), ({"signature": png_signature(blank=True)}, "signature"),
                            ({"signature": "data:image/jpeg;base64,AAAA"}, "signature")):
            res = self.act(self.head, q, "sign", body)
            self.assertEqual(res.status_code, 400, body)
            self.assertIn(field, res.data)
        q.refresh_from_db()
        self.assertEqual(q.status, "in_review")

    def test_signing_needs_the_company_stamp(self):
        q = self.quote("in_review")
        p = CompanyProfile.get()
        p.stamp.delete(save=True)
        res = self.act(self.head, q, "sign", sig())
        self.assertEqual((res.status_code, "stamp" in res.data), (400, True))
        ensure_stamp()
        self.assertEqual(self.act(self.head, q, "sign", sig()).status_code, 200)

    def test_the_signature_and_a_copy_of_the_stamp_are_kept_with_the_quotation(self):
        q = self.quote("in_review")
        self.act(self.head, q, "sign", sig())
        q.refresh_from_db()
        self.assertTrue(q.signature and q.stamp)
        with q.signature.open("rb") as fh:
            self.assertTrue(fh.read().startswith(b"\x89PNG"))
        before = q.stamp.name
        p = CompanyProfile.get()
        p.stamp.delete(save=True)
        ensure_stamp()
        q.refresh_from_db()
        self.assertEqual(q.stamp.name, before, "a later change of the company stamp must not alter a signed quotation")

    def test_oversized_signature_is_refused(self):
        q = self.quote("in_review")
        self.assertEqual(self.act(self.head, q, "sign", {"signature": "data:image/png;base64," + "A" * 600_000}).status_code, 400)


class NumberTests(QCase):
    PATTERN = re.compile(r"^QT/(\d{4})/(\d{1,2})/(\d{4})$")

    def send(self, when=None):
        q = self.quote("signed")
        if when:
            with mock.patch("django.utils.timezone.localdate", return_value=when):
                return services.mark_sent(self.member, q)
        return services.mark_sent(self.member, q)

    def test_the_number_is_issued_only_when_sent(self):
        q = self.quote("signed")
        self.assertIsNone(q.number)
        services.mark_sent(self.member, q)
        q.refresh_from_db()
        m = self.PATTERN.match(q.number)
        self.assertTrue(m, q.number)
        today = __import__("django.utils.timezone", fromlist=["x"]).localdate()
        self.assertEqual((int(m[1]), int(m[2]), int(m[3])), (today.year, today.month, 1))
        self.assertFalse(any(x.number for x in Quotation.objects.exclude(pk=q.pk)))

    def test_numbers_are_sequential_and_month_has_no_leading_zero(self):
        got = [self.send(date(2031, 3, d)).number for d in (1, 15, 31)]
        self.assertEqual(got, ["QT/2031/3/0001", "QT/2031/3/0002", "QT/2031/3/0003"])
        self.assertEqual(self.send(date(2031, 11, 2)).number, "QT/2031/11/0004")

    def test_the_counter_starts_again_each_year(self):
        self.assertEqual(self.send(date(2032, 12, 31)).number, "QT/2032/12/0001")
        self.assertEqual(self.send(date(2033, 1, 1)).number, "QT/2033/1/0001")
        self.assertEqual(self.send(date(2032, 12, 31)).number, "QT/2032/12/0002")

    def test_the_prefix_comes_from_the_company_settings(self):
        CompanyProfile.objects.filter(pk=1).update(quotation_prefix="IAS")
        self.assertTrue(self.send(date(2034, 5, 5)).number.startswith("IAS/2034/5/"))

    def test_a_failed_send_gives_its_number_back_no_gap(self):
        first = self.send(date(2035, 2, 2)).number
        q = self.quote("signed")
        with mock.patch("quotations.services.record", side_effect=RuntimeError("boom")), mock.patch("django.utils.timezone.localdate", return_value=date(2035, 2, 2)):
            with self.assertRaises(RuntimeError):
                services.mark_sent(self.member, q)
        q.refresh_from_db()
        self.assertEqual((q.status, q.number), ("signed", None))
        second = self.send(date(2035, 2, 2)).number
        self.assertEqual((first, second), ("QT/2035/2/0001", "QT/2035/2/0002"))

    def test_the_number_is_unique_in_the_database(self):
        q = self.send(date(2036, 1, 1))
        other = self.quote("signed")
        other.number = q.number
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            other.save()

    def test_the_number_shows_in_the_api_and_the_client_is_told(self):
        q = self.quote("signed")
        client = Client.objects.create(lead=q.lead, company_name="C", email="n@client.example", status="prospect", created_by=self.head)
        client_services.create_portal_account(client, self.head)
        self.as_user(self.member)
        res = self.client.post(f"/api/quotations/{q.pk}/send/", {}, format="json")
        self.assertTrue(self.PATTERN.match(res.data["number"]))
        client.refresh_from_db()
        self.assertTrue(Notification.objects.filter(user=client.portal_user, kind="quotation_sent_client").exists())


class ConcurrentNumberTests(TransactionTestCase):
    """Many people press Send at the same moment: every number is used once, with none missing."""

    def test_parallel_sends_get_distinct_consecutive_numbers(self):
        for n in DEPARTMENT_NAMES:
            Department.objects.create(name=n)
        dept = {d.name: d for d in Department.objects.all()}
        mkt = User.objects.create_user("m@x.com", "pw-pw-pw-pw-1", full_name="M", department=dept["Marketing"], role="member")
        head = User.objects.create_user("h@x.com", "pw-pw-pw-pw-1", full_name="H", department=dept["Commercial"], role="head")
        hr = User.objects.create_user("r@x.com", "pw-pw-pw-pw-1", full_name="R", department=dept["HR"], role="member")
        ensure_stamp()
        from leads.models import Lead

        quotations = []
        for i in range(6):
            lead = Lead.objects.create(ref=f"LD-9{i:03d}", company_name=f"Co {i}", phone=f"0790000{i:03d}", created_by=mkt, status="qualified", assigned_to=head)
            q = services.request_quotation(head, lead)
            q = services.start_preparing(hr, q)
            services.save_draft(hr, q, {"currency": "JOD", "valid_until": "2099-01-01", "lines": [line()]})
            q = services.submit(hr, q)
            quotations.append(services.sign(head, q, png_signature()))
        barrier = threading.Barrier(len(quotations))
        errors = []

        def work(q):
            try:
                barrier.wait(timeout=10)
                services.mark_sent(head, Quotation.objects.get(pk=q.pk))
            except Exception as exc:  # any failure is a failure of the requirement
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=work, args=(q,)) for q in quotations]
        [t.start() for t in threads]
        [t.join(60) for t in threads]
        self.assertEqual(errors, [])
        numbers = sorted(Quotation.objects.values_list("number", flat=True))
        suffixes = sorted(int(n.rsplit("/", 1)[1]) for n in numbers)
        self.assertEqual(len(set(numbers)), 6, numbers)
        self.assertEqual(suffixes, [1, 2, 3, 4, 5, 6], numbers)
        self.assertEqual(YearSequence.objects.get(key="quotation").last, 6)


class ClientSigningTests(PortalMixin, QCase):
    """The portal side, and the signed copy staff upload."""

    def sent(self):
        q = self.quote("sent")
        return Quotation.objects.get(pk=q.pk)

    def portal_get(self, q, path=""):
        self.as_user(self.portal_user(q))
        return self.client.get(f"/api/portal/quotations/{path}")

    def test_the_client_sees_their_sent_quotation_without_internal_notes(self):
        q = self.sent()
        data = self.portal_get(q).data
        self.assertEqual([x["id"] for x in data], [q.pk])
        self.assertEqual(set(data[0]), {"id", "number", "status", "company", "sent_at", "client_signed_at", "client_signed_via", "version", "can_sign"})
        self.assertEqual(data[0]["version"]["lines"][0]["description"], "Monthly bookkeeping")
        self.assertNotIn("review_comment", str(data))

    def test_a_client_never_sees_a_quotation_that_is_not_sent_or_belongs_to_someone_else(self):
        draft = self.quote("in_review")
        other = self.sent()
        mine = self.sent()
        self.assertEqual(self.portal_get(draft).data, [])
        self.assertEqual([x["id"] for x in self.portal_get(mine).data], [mine.pk])
        self.as_user(self.portal_user(mine))
        self.assertEqual(self.client.get(f"/api/portal/quotations/{other.pk}/").status_code, 404)
        self.assertEqual(self.client.post(f"/api/portal/quotations/{other.pk}/sign/", sig(), format="json").status_code, 404)
        self.assertEqual(self.client.post(f"/api/portal/quotations/{draft.pk}/sign/", sig(), format="json").status_code, 404)

    def test_the_client_signs_with_a_drawn_signature(self):
        q = self.sent()
        res = self.portal_post_(q, sig())
        self.assertEqual(res.status_code, 200, res.data)
        q.refresh_from_db()
        self.assertEqual((q.status, q.client_signed_via, bool(q.client_signature), q.client_signed_by.email), ("confirmed", "portal", True, f"c{q.pk}@client.example"))
        self.assertIn("client_signed", self.actions(q))
        self.assertTrue(Notification.objects.filter(user=self.head, kind="quotation_confirmed").exists())

    def portal_post_(self, q, body):
        self.as_user(self.portal_user(q))
        return self.client.post(f"/api/portal/quotations/{q.pk}/sign/", body, format="json")

    def test_signing_twice_or_with_a_blank_pad_is_refused(self):
        q = self.sent()
        self.assertEqual(self.portal_post_(q, {"signature": png_signature(blank=True)}).status_code, 400)
        self.assertEqual(self.portal_post_(q, sig()).status_code, 200)
        self.assertEqual(self.portal_post_(q, sig()).status_code, 400)  # already signed

    def test_staff_cannot_use_the_portal_and_clients_cannot_use_staff_actions(self):
        q = self.sent()
        for key in ("ceo", "commercial_head", "commercial_member", "hr_head"):
            self.as_role(key)
            self.assertEqual(self.client.post(f"/api/portal/quotations/{q.pk}/sign/", sig(), format="json").status_code, 403, key)
        self.as_user(self.portal_user(q))
        for name in ("send", "sign", "outcome", "cancel", "start"):
            self.assertEqual(self.client.post(f"/api/quotations/{q.pk}/{name}/", sig(), format="json").status_code, 403, name)

    def test_a_signed_copy_uploaded_by_staff_is_the_document_of_record(self):
        q = self.sent()
        self.as_user(self.member)
        res = self.client.post(f"/api/quotations/{q.pk}/signed-copy/", {"file": SimpleUploadedFile("signed.pdf", PDF, "application/pdf")}, format="multipart")
        self.assertEqual((res.status_code, res.data["status"], res.data["client_signed_via"], res.data["has_signed_copy"]), (200, "confirmed", "upload", True))
        att = Attachment.objects.get(object_id=q.pk, category="client_signed_copy")
        self.assertEqual((att.original_name, att.content_type_header), ("signed.pdf", "application/pdf"))
        again = self.client.post(f"/api/quotations/{q.pk}/signed-copy/", {"file": SimpleUploadedFile("signed2.pdf", PDF, "application/pdf")}, format="multipart")
        self.assertEqual(again.status_code, 200)  # a better scan may replace it
        self.assertEqual(Attachment.objects.filter(object_id=q.pk, category="client_signed_copy").count(), 2)

    def test_bad_or_misplaced_copies_are_refused(self):
        q = self.sent()
        self.as_user(self.member)
        url = f"/api/quotations/{q.pk}/signed-copy/"
        for f in (SimpleUploadedFile("x.pdf", b"not a pdf", "application/pdf"), SimpleUploadedFile("x.exe", b"MZ", "application/octet-stream"),
                  SimpleUploadedFile("x.docx", b"PK\x03\x04", "application/zip"), SimpleUploadedFile("x.pdf", b"", "application/pdf")):
            self.assertEqual(self.client.post(url, {"file": f}, format="multipart").status_code, 400, f.name)
        self.assertEqual(self.client.post(url, {}, format="multipart").status_code, 400)
        self.as_user(self.member2)
        self.assertEqual(self.client.post(url, {"file": SimpleUploadedFile("x.pdf", PDF, "application/pdf")}, format="multipart").status_code, 404)
        q.refresh_from_db()
        self.assertEqual(q.status, "sent")

    def test_after_the_client_signed_on_the_portal_no_copy_replaces_it(self):
        q = self.sent()
        self.portal_post_(q, sig())
        self.as_user(self.member)
        res = self.client.post(f"/api/quotations/{q.pk}/signed-copy/", {"file": SimpleUploadedFile("x.pdf", PDF, "application/pdf")}, format="multipart")
        self.assertEqual(res.status_code, 400)  # the client's own signature stands


class CommercialMemberKeepsTheirRulesTests(QCase):
    def test_the_commercial_member_can_still_send_and_record_the_outcome(self):
        q = self.quote("signed")
        self.assertEqual(self.act(self.member, q, "send").status_code, 200)
        self.assertEqual(self.act(self.member, q, "outcome", {"outcome": "waiting", "next_follow_up": self.day(5)}).status_code, 200)
        self.assertEqual(self.act(self.member, q, "outcome", {"outcome": "confirmed"}).status_code, 200)


class CompanyProfileTests(QCase):
    def test_only_the_ceo_and_super_admin_change_the_company_details(self):
        self.assert_matrix("get", "/api/company/", {"ceo": 200, "*": 403})
        self.assert_matrix("patch", "/api/company/", {"ceo": 200, "*": 403}, data={"quotation_prefix": "ias"})
        self.assertEqual(CompanyProfile.get().quotation_prefix, "IAS")

    def test_prefix_and_stamp_are_validated(self):
        self.as_role("ceo")
        self.assertEqual(self.client.patch("/api/company/", {"quotation_prefix": "bad prefix!"}, format="json").status_code, 400)
        self.assertEqual(self.client.patch("/api/company/", {"stamp": SimpleUploadedFile("s.png", b"not a png", "image/png")}, format="multipart").status_code, 400)
        ok = self.client.patch("/api/company/", {"stamp": SimpleUploadedFile("s.png", __import__("base64").b64decode(png_signature().split(",")[1]), "image/png")}, format="multipart")
        self.assertEqual((ok.status_code, ok.data["has_stamp"]), (200, True))
        self.assertEqual(self.client.get("/api/company/stamp/").status_code, 200)
        self.as_role("commercial_head")
        self.assertEqual(self.client.get("/api/company/stamp/").status_code, 403)
