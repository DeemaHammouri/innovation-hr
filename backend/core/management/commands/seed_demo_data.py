"""
DEMO DATA, FOR DEVELOPMENT ONLY.

Creates one demo user per role and sample records for every module built so far, so every screen has something to show.
It refuses to run when DEBUG is off or DJANGO_ENV=production, and it never touches records that are not marked demo.
Safe to run twice: people are found by email and leads by company name.

    python manage.py seed_demo_data

Demo password for every demo user: Demo-12345
"""
import os
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import ADMINISTRATION, Department, User
from core.models import CompanyProfile

PASSWORD = "Demo-12345"
PEOPLE = [
    ("ceo", "Demo CEO", "Administration", "head", "en"),
    ("marketing", "Demo Marketing", "Marketing", "member", "en"),
    ("commercial.head", "Demo Commercial Head", "Commercial", "head", "en"),
    ("commercial.member", "Demo Commercial Member", "Commercial", "member", "ar"),
    ("hr.head", "Demo HR Head", "HR", "head", "en"),
    ("hr.member", "Demo HR Member", "HR", "member", "en"),
    ("operation.head", "Demo Operation Head", "Operation", "head", "en"),
    ("operation.member", "Demo Operation Member", "Operation", "member", "ar"),
]
LEADS = [
    ("Al Noor Logistics", "Hassan Ali", "0790001001", "hassan@alnoor.demo", "Trade fair", "new", False),
    ("Cedar Foods", "Maya Fares", "0790001002", "", "Referral", "new", True),
    ("شركة الأفق للمقاولات", "خالد العتيبي", "0790001003", "khalid@ufuq.demo", "Website", "contacted", True),
    ("Blue Harbor Group", "Daniel Wright", "0790001004", "daniel@blueharbor.demo", "LinkedIn", "waiting", True),
    ("Summit Dental Clinic", "Lina Aziz", "0790001005", "", "Referral", "waiting-overdue", True),
    ("Desert Rose Hotel", "Omar Saleh", "0790001006", "omar@desertrose.demo", "Trade fair", "qualified", True),
    ("Olive Tree Bakery", "Rana Haddad", "0790001007", "", "Walk-in", "rejected", True),
]


class Command(BaseCommand):
    help = "Create demo users and sample data (development only)."

    def handle(self, *args, **options):
        if not settings.DEBUG or os.environ.get("DJANGO_ENV", "").lower() == "production":
            raise CommandError("seed_demo_data is for development only. It refuses to run when DEBUG is off.")
        for name in ("Administration", "Marketing", "Commercial", "HR", "Operation"):
            Department.objects.get_or_create(name=name)
        users = self.people()
        self.leads(users)
        self.quotations(users)
        self.contracts(users)
        self.operation(users)
        self.payments_and_hr(users)
        self.stdout.write(self.style.SUCCESS(f"Demo data ready. Sign in as <name>@demo.test with the password {PASSWORD}"))
        for key, *_ in PEOPLE:
            self.stdout.write(f"  {key}@demo.test")
        self.stdout.write("A seat that was already taken keeps its real person; the demo records are attached to them.")

    def people(self):
        out = {}
        for key, full_name, dept, role, lang in PEOPLE:
            email = f"{key}@demo.test"
            user = User.objects.filter(email=email).first()
            if user is None:
                department = Department.objects.get(name=dept)
                # Administration and Marketing have one seat, and every department has one head. If the seat is taken
                # (by a real person in a dev database), the demo data is attached to them instead of adding a second.
                taken = User.objects.filter(department=department, is_active=True)
                if dept in (ADMINISTRATION, "Marketing"):
                    taken = taken
                elif role == "head":
                    taken = taken.filter(is_dept_head=True)
                else:
                    taken = User.objects.none()
                if taken.exists():
                    out[key] = taken.first()
                    continue
                user = User.objects.create_user(email=email, password=PASSWORD, full_name=full_name, department=department, role=role, preferred_language=lang)
            out[key] = user
        return out

    def leads(self, users):
        from leads import services
        from leads.models import Lead
        from lookups.models import RejectionReason

        marketing, head, member = users["marketing"], users["commercial.head"], users["commercial.member"]
        reason = RejectionReason.objects.filter(is_active=True).first()
        today = timezone.localdate()
        made = 0
        for company, contact, phone, email, source, state, assign in LEADS:
            if Lead.objects.filter(company_name=company).exists():
                continue
            lead = services.create_lead(marketing, {"company_name": company, "contact_name": contact, "phone": phone, "email": email, "source": source, "notes": ""})
            if assign:
                lead = services.assign(head, lead, member)
            if state == "contacted":
                services.log_interaction(member, lead, type="call", notes="Introduced our services. They will review.")
            elif state == "waiting":
                services.log_interaction(member, lead, type="meeting", notes="Met at their office.", outcome="waiting", next_follow_up=today + timedelta(days=5))
            elif state == "waiting-overdue":
                services.log_interaction(member, lead, type="call", notes="Asked to call back.", outcome="waiting", next_follow_up=today + timedelta(days=1))
                Lead.objects.filter(pk=lead.pk).update(next_follow_up=today - timedelta(days=3))
            elif state == "qualified":
                services.log_interaction(member, lead, type="whatsapp", notes="Happy to receive a quotation.", outcome="accepted")
            elif state == "rejected":
                services.log_interaction(member, lead, type="call", notes="Not interested right now.", outcome="rejected", reason_id=reason.pk if reason else None, note="Already works with another provider.")
            made += 1
        self.stdout.write(f"Leads: {made} added.")

    def quotations(self, users):
        """Two demo quotations on qualified leads: one waiting for HR, one signed and sent. Skipped if any already exist."""
        from datetime import date, timedelta

        from leads.models import Lead
        from quotations import services
        from quotations.models import Quotation

        if Quotation.objects.exists():
            self.stdout.write("Quotations: already there.")
            return
        qualified = list(Lead.objects.filter(status="qualified", archived_at=None, skipped_quotation_at=None)[:2])
        head, hr = users["commercial.head"], users["hr.head"]
        for i, lead in enumerate(qualified):
            q = services.request_quotation(lead.assigned_to or head, lead, "Demo: monthly accounting plan")
            if i == 0:
                continue
            q = services.start_preparing(hr, q)
            services.save_draft(hr, q, {"currency": "JOD", "valid_until": (date.today() + timedelta(days=30)).isoformat(), "notes": "Demo quotation", "lines": [
                {"description": "Monthly bookkeeping", "quantity": "1", "unit_price": "250", "discount_percent": "0", "tax_percent": "16"},
                {"description": "Payroll processing", "quantity": "1", "unit_price": "120", "discount_percent": "10", "tax_percent": "16"}]})
            q = services.submit(hr, q)
            if not CompanyProfile.get().stamp:
                continue  # signing needs the company stamp (the CEO uploads it first); the quotation stays submitted for review
            from core.testing import png_signature

            q = services.sign(head, q, png_signature())
            services.mark_sent(lead.assigned_to or head, q)
        self.stdout.write(f"Quotations: {len(qualified)} added.")

    def contracts(self, users):
        """One demo contract requested on a lead whose quotation is signed and sent (confirmed here), waiting for HR."""
        from django.utils import timezone

        from contracts import services
        from contracts.models import Contract
        from quotations.models import Quotation

        if Contract.objects.exists():
            self.stdout.write("Contracts: already there.")
            return
        q = Quotation.objects.filter(status="sent").select_related("lead").first()
        if q is None:
            return
        Quotation.objects.filter(pk=q.pk).update(status="confirmed", outcome_at=timezone.now())
        services.request_contract(q.lead.assigned_to or users["commercial.head"], q.lead, "Demo: standard 12 month terms")
        self.stdout.write("Contracts: 1 added.")

    def operation(self, users):
        """One demo client mid-onboarding (two of its documents verified) with a weekly task. Skipped if one exists."""
        from clients.models import Client
        from lookups.models import ChecklistTemplateItem
        from operations import services
        from operations.models import ChecklistItem

        name = "Demo Onboarding Co"
        if Client.objects.filter(company_name=name).exists():
            self.stdout.write("Operation: already there.")
            return
        head = users["operation.head"]
        client = Client.objects.create(company_name=name, contact_person="Demo Contact", phone="0790002001", status="onboarding", created_by=head, notes="Demo client for the Operation screens.")
        for pos, t in enumerate(ChecklistTemplateItem.objects.filter(is_active=True)):
            ChecklistItem.objects.create(client=client, template_item=t, name_en=t.name_en, name_ar=t.name_ar, required=t.required, position=pos)
        services.create_recurring(head, client, {"title": "Weekly bank reconciliation", "frequency": "weekly", "start_date": timezone.localdate().isoformat(), "assignee": users["operation.member"].pk})
        self.stdout.write("Operation: 1 client added.")

    def payments_and_hr(self, users):
        """A demo payment schedule with one payment, two leave requests and demo salaries. Each part is skipped if it exists."""
        from clients.models import Client
        from hr import leave, payroll
        from hr.models import EmployeeSalary, LeaveRequest, LeaveType
        from payments import services as pay
        from payments.models import Instalment

        today = timezone.localdate()
        client = Client.objects.filter(company_name="Demo Onboarding Co").first()
        if client and not Instalment.objects.filter(client=client).exists():
            rows = [{"due_date": (today - timedelta(days=15)).isoformat(), "amount": "400.00"}, {"due_date": (today + timedelta(days=15)).isoformat(), "amount": "400.00"}]
            pay.create_schedule(users["commercial.head"], client, {"currency": "JOD", "instalments": rows})
            first = Instalment.objects.filter(client=client).order_by("number").first()
            pay.record_payment(users["commercial.head"], first, {"amount": "150.00", "received_on": today.isoformat(), "method": "bank_transfer", "reference": "DEMO-001"})
            self.stdout.write("Payments: 1 schedule added.")
        annual = LeaveType.objects.filter(is_active=True).order_by("sort_order", "id").first()
        member = users["hr.member"]
        if annual and not LeaveRequest.objects.filter(user=member).exists():
            start = today + timedelta(days=7)
            while start.weekday() in (4, 5):
                start += timedelta(days=1)
            req = leave.request_leave(member, {"leave_type": annual.pk, "start_date": start.isoformat(), "end_date": start.isoformat(), "reason": "Demo request"})
            self.stdout.write("Leave: 1 request added (waiting for the HR head).")
        for key, amount in (("hr.head", "1500.00"), ("hr.member", "800.00"), ("operation.head", "1400.00"), ("operation.member", "700.00")):
            if not EmployeeSalary.objects.filter(user=users[key]).exists():
                payroll.set_salary(users["hr.head"], users[key], {"base_salary": amount, "currency": "JOD"})
        self.stdout.write("Salaries: demo values set (visible only to the CEO and the HR head).")
