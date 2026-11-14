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
                    taken = taken.filter(role="head")
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
