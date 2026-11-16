from django.conf import settings
from django.db import models

from core.fields import UpdatedAtField

from .countries import CODES


class Client(models.Model):
    company_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    # Phase 5. Clients that existed before onboarding was built stay "active"; a handover creates them as "onboarding".
    # "prospect": converted from a lead, no handover yet. Clients that existed before onboarding was built stay "active"; a handover
    # (or the Operation head adding a client by hand) makes "onboarding".
    status = models.CharField(max_length=12, choices=[("prospect", "Prospect"), ("onboarding", "Onboarding"), ("active", "Active"), ("inactive", "Inactive")], default="active", db_index=True)
    lead = models.OneToOneField("leads.Lead", on_delete=models.PROTECT, null=True, blank=True, related_name="client")  # the lead this client came from
    portal_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="portal_client")
    portal_status = models.CharField(max_length=12, blank=True, default="")  # "", "sent", "no_email", "email_in_use", "failed"
    country = models.CharField(max_length=5, default="JO")  # picks the contract template; one of clients.countries.CODES
    # What the client decided after a completed follow-up meeting (set by Commercial): confirm, waiting (a follow-up is scheduled) or rejection.
    decision = models.CharField(max_length=10, blank=True, default="", choices=[("confirm", "Confirm"), ("waiting", "Waiting"), ("rejection", "Rejection")], db_index=True)
    decision_at = models.DateTimeField(null=True, blank=True)
    decision_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    decision_follow_up = models.DateField(null=True, blank=True)
    decision_reason = models.ForeignKey("lookups.RejectionReason", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    decision_note = models.TextField(blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    qa_cadence_days = models.PositiveSmallIntegerField(default=30)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="clients_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = UpdatedAtField()

    class Meta:
        ordering = ["company_name"]
        constraints = [models.CheckConstraint(condition=models.Q(qa_cadence_days__gte=7) & models.Q(qa_cadence_days__lte=365), name="client_qa_cadence_range")]

    def __str__(self):
        return self.company_name
