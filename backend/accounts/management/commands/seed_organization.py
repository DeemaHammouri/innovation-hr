from django.core.management.base import BaseCommand

from accounts.models import Capability, Department, Role
from accounts.organization import ensure_organization


class Command(BaseCommand):
    help = "Create the five departments, the nine roles and every capability. Safe to run again: it never resets grants you changed."

    def handle(self, *args, **options):
        ensure_organization()
        self.stdout.write(
            f"Organization ready: {Department.objects.count()} departments, {Role.objects.count()} roles, {Capability.objects.count()} capabilities."
        )
