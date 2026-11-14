import os

from django.core.management.base import BaseCommand, CommandError

from accounts.models import ADMINISTRATION, DEPARTMENT_NAMES, Department, User


class Command(BaseCommand):
    help = "Create the departments and the CEO account (env: CEO_EMAIL, CEO_PASSWORD, optional CEO_NAME)."

    def handle(self, *args, **options):
        for name in DEPARTMENT_NAMES:
            Department.objects.get_or_create(name=name)
        self.stdout.write("Departments ready.")

        email = os.environ.get("CEO_EMAIL")
        password = os.environ.get("CEO_PASSWORD")
        if not email or not password:
            raise CommandError("Set CEO_EMAIL and CEO_PASSWORD to create the CEO account.")
        admin_dept = Department.objects.get(name=ADMINISTRATION)
        if User.objects.filter(department=admin_dept).exists():
            self.stdout.write("The CEO already exists. Nothing to do.")
            return
        User.objects.create_user(
            email=email,
            password=password,
            full_name=os.environ.get("CEO_NAME", "CEO"),
            department=admin_dept,
            role=User.Role.HEAD,
        )
        self.stdout.write(self.style.SUCCESS(f"CEO created: {email.lower()}"))
