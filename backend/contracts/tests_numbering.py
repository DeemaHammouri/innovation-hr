import threading

from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import DEPARTMENT_NAMES, Department, User
from contracts import services
from contracts.models import Contract
from core.models import YearSequence
from core.testing import ensure_stamp
from leads.models import Lead


class ConcurrentContractNumberTests(TransactionTestCase):
    """Same design and same requirement as quotation numbering: a row-locked yearly counter, taken in the transaction that sends.

    Run on PostgreSQL (real row locks) with:
        DB_ENGINE=postgres DB_NAME=... DB_USER=... DB_PASSWORD=... DB_HOST=... python manage.py test contracts.tests_numbering
    On SQLite (the default here) writers are serialised by the database, so this proves the logic but not the PostgreSQL locking."""

    def test_parallel_sends_get_distinct_consecutive_numbers(self):
        for n in DEPARTMENT_NAMES:
            Department.objects.create(name=n)
        dept = {d.name: d for d in Department.objects.all()}
        mkt = User.objects.create_user("m@x.com", "pw-pw-pw-pw-1", full_name="M", department=dept["Marketing"], role="member")
        head = User.objects.create_user("h@x.com", "pw-pw-pw-pw-1", full_name="H", department=dept["Commercial"], role="head")
        hr = User.objects.create_user("r@x.com", "pw-pw-pw-pw-1", full_name="R", department=dept["HR"], role="member")
        ensure_stamp()
        contracts = []
        for i in range(6):
            lead = Lead.objects.create(ref=f"LD-8{i:03d}", company_name=f"Co {i}", phone=f"0780000{i:03d}", created_by=mkt, status="qualified", assigned_to=head, skipped_quotation_at=timezone.now())
            c = services.request_contract(head, lead)
            c = services.start_drafting(hr, c)
            services.save_draft(hr, c, {"body_en": "Terms", "body_ar": "الشروط"})
            c = services.send_to_commercial(hr, c)
            contracts.append(services.confirm(head, c))
        barrier = threading.Barrier(len(contracts))
        errors = []

        def work(c):
            try:
                barrier.wait(timeout=10)
                services.send_to_client(hr, Contract.objects.get(pk=c.pk))
            except Exception as exc:  # any failure is a failure of the requirement
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=work, args=(c,)) for c in contracts]
        [t.start() for t in threads]
        [t.join(60) for t in threads]
        self.assertEqual(errors, [])
        numbers = list(Contract.objects.values_list("number", flat=True))
        suffixes = sorted(int(n.rsplit("/", 1)[1]) for n in numbers)
        self.assertEqual(len(set(numbers)), 6, numbers)
        self.assertEqual(suffixes, [1, 2, 3, 4, 5, 6], numbers)
        self.assertEqual(YearSequence.objects.get(key="contract").last, 6)

    def test_a_failed_send_gives_its_number_back(self):
        """The number is taken in the same transaction as the status change, so a send that fails leaves no gap."""
        from unittest import mock

        for n in DEPARTMENT_NAMES:
            Department.objects.create(name=n)
        dept = {d.name: d for d in Department.objects.all()}
        mkt = User.objects.create_user("m2@x.com", "pw-pw-pw-pw-1", full_name="M", department=dept["Marketing"], role="member")
        head = User.objects.create_user("h2@x.com", "pw-pw-pw-pw-1", full_name="H", department=dept["Commercial"], role="head")
        hr = User.objects.create_user("r2@x.com", "pw-pw-pw-pw-1", full_name="R", department=dept["HR"], role="member")
        ensure_stamp()
        lead = Lead.objects.create(ref="LD-8900", company_name="Co", phone="0780009999", created_by=mkt, status="qualified", assigned_to=head, skipped_quotation_at=timezone.now())
        c = services.request_contract(head, lead)
        c = services.start_drafting(hr, c)
        services.save_draft(hr, c, {"body_en": "Terms", "body_ar": "الشروط"})
        c = services.send_to_commercial(hr, c)
        c = services.confirm(head, c)
        with mock.patch("contracts.services.record", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                services.send_to_client(hr, c)
        self.assertFalse(YearSequence.objects.filter(key="contract", last__gt=0).exists())
        self.assertFalse(Contract.objects.get(pk=c.pk).number)
        c = services.send_to_client(hr, Contract.objects.get(pk=c.pk))
        self.assertTrue(c.number.endswith("/0001"))
