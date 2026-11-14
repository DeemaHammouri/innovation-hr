from django.conf import settings
from django.db import models


class Client(models.Model):
    company_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    # Phase 5. Clients that existed before onboarding was built stay "active"; a handover creates them as "onboarding".
    status = models.CharField(max_length=12, choices=[("onboarding", "Onboarding"), ("active", "Active"), ("inactive", "Inactive")], default="active", db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    qa_cadence_days = models.PositiveSmallIntegerField(default=30)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="clients_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]

    def __str__(self):
        return self.company_name
