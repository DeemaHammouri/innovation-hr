"""Turning a lead into a client, and the client's portal account."""
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from rest_framework.exceptions import APIException

from accounts.models import Role, User
from accounts.passwords import generate_temporary_password
from audit.models import record

from .models import Client

PORTAL_ROLE = "client"


class LeadConverted(APIException):
    """The lead became a client. Its record is frozen: nothing about it changes any more."""

    status_code = 409
    default_code = "lead_converted"
    default_detail = "This lead is now a client, so it can no longer be changed. Open the client instead."


def is_converted(lead):
    return Client.objects.filter(lead=lead).exists()


def forbid_if_converted(lead):
    if is_converted(lead):
        raise LeadConverted()


def convert_lead(lead, actor):
    """Make the client for an accepted lead (once) and try to open their portal. Never fails because of the email."""
    existing = Client.objects.filter(lead=lead).first()
    if existing:
        return existing
    client = Client.objects.create(
        company_name=lead.company_name, contact_person=lead.contact_name, phone=lead.phone, email=lead.email or "",
        notes=lead.notes, status="prospect", lead=lead, created_by=actor,
    )
    record(actor, client, "created", comment=f"Converted from lead {lead.ref}")
    record(actor, lead, "converted", to_value=f"client {client.pk}")
    create_portal_account(client, actor)
    return client


def create_portal_account(client, actor):
    """Make the portal login with a temporary password and email it. The outcome is kept on the client: sent, no_email, email_in_use, failed.
    Safe to call again after the email on the client was fixed."""
    if client.portal_user_id:
        return client.portal_status
    email = (client.email or "").strip().lower()
    if not email:
        client.portal_status = "no_email"
    elif User.objects.filter(email__iexact=email).exists():
        client.portal_status = "email_in_use"
    else:
        password = generate_temporary_password()
        with transaction.atomic():
            role = Role.objects.get(key=PORTAL_ROLE)
            user = User.objects.create_user(
                email=email, password=password, full_name=client.contact_person or client.company_name, role_ref=role,
                must_change_password=True, preferred_language="ar" if _arabic(client) else "en",
            )
            client.portal_user = user
            client.portal_status = "sent"
        try:
            _welcome(client, email, password)
        except Exception:  # a mail server problem must not undo the conversion; the status tells staff to resend
            client.portal_status = "failed"
    client.save(update_fields=["portal_user", "portal_status", "updated_at"])
    record(actor, client, "portal_account", to_value=client.portal_status)
    return client.portal_status


def _arabic(client):
    return any("؀" <= ch <= "ۿ" for ch in client.company_name)


def _welcome(client, email, password):
    send_mail(
        "Your Innovation client portal / بوابة العميل",
        (
            f"Hello {client.contact_person or client.company_name},\n\n"
            f"Your portal account is ready.\nAddress: {settings.PORTAL_URL}\nEmail: {email}\nTemporary password: {password}\n\n"
            "You will be asked to choose a new password the first time you sign in.\n\n"
            f"مرحبًا {client.contact_person or client.company_name}،\n\n"
            f"حساب البوابة جاهز.\nالرابط: {settings.PORTAL_URL}\nالبريد: {email}\nكلمة المرور المؤقتة: {password}\n\n"
            "سيُطلب منك اختيار كلمة مرور جديدة عند أول دخول.\n"
        ),
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


def ensure_portal(client, actor):
    """Staff action after fixing the email, or when the welcome email did not arrive: open the portal, or give a new temporary password."""
    if not client.portal_user_id:
        return create_portal_account(client, actor)
    user = client.portal_user
    password = generate_temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    user.bump_token_version()  # whatever session they had stops working
    try:
        _welcome(client, user.email, password)
        client.portal_status = "sent"
    except Exception:
        client.portal_status = "failed"
    client.save(update_fields=["portal_status", "updated_at"])
    record(actor, client, "portal_resent", to_value=client.portal_status)
    return client.portal_status
