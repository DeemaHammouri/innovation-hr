"""OpenAPI documentation for the endpoints the generator cannot describe by itself (APIViews and plain ViewSets without a serializer,
actions whose body or answer is not the viewset's serializer, file downloads, serializer methods without a type hint).

DOCUMENTATION ONLY. Everything here is applied with drf-spectacular decorators on the existing classes: no view, serializer or permission
changes behaviour. Each shape below was read from the view that serves it. The module is imported at the bottom of core/apidocs.py,
which the URL conf imports, so the decorators are in place before any schema is generated.
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_field, extend_schema_serializer, extend_schema_view, inline_serializer,
)
from rest_framework import serializers as s

# --------------------------------------------------------------------------------------------------------------------
# small vocabulary
# --------------------------------------------------------------------------------------------------------------------
I, T, B, F = s.IntegerField, s.CharField, s.BooleanField, s.FloatField
DT, D, ANY = s.DateTimeField, s.DateField, s.JSONField


def obj(_name, /, **fields):
    """A documentation-only serializer CLASS (instantiate it to use it as a field)."""
    return type(_name, (s.Serializer,), fields)


def lst(_name, /, **fields):
    """A top-level list response of small objects."""
    return obj(_name, **fields)(many=True)


def many(item, **kw):
    return s.ListField(child=item, **kw)


def rows(_name, /, **fields):
    """A list of small objects."""
    return s.ListField(child=obj(_name, **fields)())


def page(name, item):
    """The StandardPagination envelope."""
    return obj(name, count=I(), next=s.URLField(allow_null=True), previous=s.URLField(allow_null=True), results=item(many=True) if isinstance(item, type) else many(item))


def qp(name, kind=str, desc="", enum=None, required=False):
    kind = OpenApiTypes.DATE if kind is D else kind
    return OpenApiParameter(name, kind, OpenApiParameter.QUERY, description=desc, enum=enum, required=required)


def pp(name="id", desc="Record id."):
    return OpenApiParameter(name, int, OpenApiParameter.PATH, description=desc)


def extend(base, name, **extra):
    """A documentation-only copy of a ModelSerializer with more fields."""
    meta = type("Meta", (base.Meta,), {"fields": list(base.Meta.fields) + list(extra), "read_only_fields": list(base.Meta.fields) + list(extra)})
    return type(name, (base,), {**extra, "Meta": meta})


def doc(cls, **ops):
    """extend_schema_view with the operation names being the view's method / action names."""
    extend_schema_view(**{name: (extend_schema(**kw) if isinstance(kw, dict) else kw) for name, kw in ops.items()})(cls)


def hint(serializer, **types):
    """Give SerializerMethodField methods a response type (documentation only: the function is untouched)."""
    for method, kind in types.items():
        fn = getattr(serializer, method)
        extend_schema_field(kind)(fn)


NOTE = obj("NoteBody", note=T(required=False, allow_blank=True))
REASON = obj("ReasonBody", reason=T(required=False, allow_blank=True))
COMMENT = obj("CommentBody", comment=T(required=False, allow_blank=True))
PERSON = obj("PersonRef", id=I(), full_name=T())
PERSON_ROWS = PERSON(many=True)
FMT = [
    qp("fmt", str, "pdf (default) or docx.", ["pdf", "docx"]),
    qp("lang", str, "en, ar or both. Defaults to the signed-in person's language.", ["en", "ar", "both"]),
    qp("generated", str, "1 forces the generated file even when a signed copy exists.", ["1"]),
]
PDF_OR_DOCX = {
    (200, "application/pdf"): OpenApiTypes.BINARY,
    (200, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"): OpenApiTypes.BINARY,
}
CSV = {(200, "text/csv"): OpenApiTypes.BINARY}
PERMS = s.DictField(child=s.BooleanField())
OBJ = OpenApiTypes.OBJECT
STR_LIST = {"type": "array", "items": {"type": "string"}}

# --------------------------------------------------------------------------------------------------------------------
# serializer method fields (type hints)
# --------------------------------------------------------------------------------------------------------------------
def _serializer_hints():
    from accounts import serializers as acc
    from appointments import views as appt
    from audit import tracking
    from contracts import serializers as con
    from generaltasks import views as gt
    from leads import serializers as lead
    from meetings import views as mtg
    from notifications import views as notif
    from operations import handover_api as ho, serializers as op
    from quotations import serializers as quo
    from hr import serializers as hrs
    from payments import serializers as pay

    BOOL, STR, DATE_ = OpenApiTypes.BOOL, OpenApiTypes.STR, OpenApiTypes.DATE
    INT = OpenApiTypes.INT
    ref_obj = {"type": "object", "properties": {"id": {"type": "integer"}, "ref": {"type": "string"}}, "nullable": True}
    ref_status_list = {"type": "array", "items": {"type": "object", "properties": {"id": {"type": "integer"}, "ref": {"type": "string"}, "status": {"type": "string"}}}}
    flags = {"type": "object", "additionalProperties": {"type": "boolean"}}

    hint(acc.UserSerializer, get_role_key=STR, get_capabilities=STR_LIST, get_permissions=flags)
    from accounts.models import User

    extend_schema_field(STR)(User.role.fget)
    hint(tracking.FeedSerializer, get_kind=STR)
    hint(appt.AppointmentSerializer, get_overdue=BOOL, get_permissions=flags | {"description": "What this person may do with the appointment; report_id is the linked report or null."})
    hint(lead.LeadSerializer, get_follow_up_overdue=BOOL, get_first_contact_overdue=BOOL, get_permissions=flags,
         get_quotation={"type": "object", "nullable": True, "description": "The lead's newest quotation: id, ref, status."},
         get_contract={"type": "object", "nullable": True, "description": "The lead's newest contract: id, ref, status."})
    hint(lead.ImportBatchSerializer, get_contacted_count=INT, get_can_undo=BOOL)
    hint(con.ContractSerializer, get_permissions=flags, get_attachable=STR_LIST)
    hint(con.ContractDetailSerializer, get_permissions=flags, get_attachable=STR_LIST)
    hint(ho.HandoverSerializer, get_project=ref_obj, get_permissions=flags)
    hint(ho.ProjectSerializer, get_staff={"type": "array", "items": {"type": "object", "properties": {
        "user": {"type": "integer"}, "name": {"type": "string"}, "role": {"type": "string"}, "since": {"type": "string", "format": "date-time"},
        "ended_at": {"type": "string", "format": "date-time", "nullable": True}, "end_reason": {"type": "string"}}}}, get_can_staff=BOOL)
    hint(mtg.ReportSerializer, get_ref=STR, get_permissions=flags)
    hint(notif.NotificationSerializer, get_read=BOOL)
    for ser in (op.OpClientSerializer, op.OpClientDetailSerializer):
        hint(ser, get_next_qa_due=DATE_, get_qa_overdue=BOOL, get_permissions=flags)
    hint(op.OpClientDetailSerializer, get_checklist=op.ChecklistItemSerializer(many=True), get_recurring_tasks=op.RecurringSerializer(many=True),
         get_handovers=ref_status_list, get_projects=ref_status_list)
    hint(op.TaskSerializer, get_overdue=BOOL, get_can_work=BOOL, get_escalation_level=INT, get_can_review=BOOL, get_can_escalate=BOOL, get_can_complete=BOOL,
         get_can_publish=BOOL, get_deliverables={"type": "array", "items": {"type": "object", "properties": {
             "id": {"type": "integer"}, "title": {"type": "string"}, "published_at": {"type": "string", "format": "date-time", "nullable": True},
             "acknowledged_at": {"type": "string", "format": "date-time", "nullable": True}}}})
    hint(quo.QuotationSerializer, get_latest={"type": "object", "nullable": True, "description": "Newest version: number, is_draft, currency, total, valid_until, count."},
         get_follow_up_overdue=BOOL, get_permissions=flags, get_has_signature=BOOL, get_has_signed_copy=BOOL)
    hint(quo.QuotationDetailSerializer, get_latest={"type": "object", "nullable": True, "description": "Newest version: number, is_draft, currency, total, valid_until, count."},
         get_follow_up_overdue=BOOL, get_permissions=flags, get_has_signature=BOOL, get_has_signed_copy=BOOL)
    hint(quo.VersionSerializer, get_is_draft=BOOL)
    hint(op.ChecklistItemSerializer, get_versions={"type": "array", "items": {"type": "object", "properties": {
        "number": {"type": "integer"}, "filename": {"type": "string"}, "state": {"type": "string"}, "uploaded_by_name": {"type": "string", "nullable": True},
        "uploaded_at": {"type": "string", "format": "date-time"}, "verified_by_name": {"type": "string", "nullable": True}, "verified_at": {"type": "string", "format": "date-time", "nullable": True},
        "expires_on": {"type": "string", "format": "date", "nullable": True}, "attachment": {"type": "integer", "nullable": True}}}})
    hint(pay.InstalmentSerializer, get_status=STR, get_paid=STR, get_balance=STR, get_amount=STR, get_can_edit=BOOL)
    hint(pay.PaymentSerializer, get_amount=STR, get_reversed=BOOL, get_has_receipt=BOOL, get_can_reverse=BOOL)
    hint(hrs.LeaveRequestSerializer, get_can_decide=BOOL, get_can_cancel=BOOL)
    for ser in (hrs.EntrySerializer, hrs.PayslipSerializer):
        hint(ser, get_base_salary=STR, get_allowances=STR, get_deductions=STR)
    hint(hrs.EntrySerializer, get_net=STR)
    hint(hrs.PayslipSerializer, get_net=STR, get_month=STR)
    hint(hrs.SalarySerializer, get_base_salary=STR)
    hint(hrs.RunSerializer, get_month=STR, get_total_net=STR, get_permissions=flags)
    hint(gt.GeneralTaskSerializer, get_overdue=BOOL, get_can_done=BOOL, get_can_edit=BOOL, get_can_attach=BOOL)
    extend_schema_serializer(component_name="QuotationVersion")(quo.VersionSerializer)
    extend_schema_serializer(component_name="ContractVersion")(con.VersionSerializer)


def _portal_hints():
    from clients import portal

    sub = {"type": "object", "nullable": True}
    hint(portal.PortalQuotationSerializer, get_version={**sub, "description": "The signed version: number, currency, valid_until, payment_terms, notes, subtotal, discount_total, tax_total, total, lines[]."}, get_can_sign=OpenApiTypes.BOOL)
    hint(portal.PortalContractSerializer, get_version={**sub, "description": "The latest sent version: number, title, currency, total, payment_terms, start_date, end_date, body_en, body_ar, services."}, get_can_sign=OpenApiTypes.BOOL)


_serializer_hints()
_portal_hints()

# --------------------------------------------------------------------------------------------------------------------
# accounts
# --------------------------------------------------------------------------------------------------------------------
def _accounts():
    from accounts import views as v
    from accounts.serializers import ChangePasswordSerializer, PreferredLanguageSerializer, UserSerializer, UserWriteSerializer

    login_in = obj("Credentials", identifier=T(help_text="Username or email."), password=T(style={"input_type": "password"}))
    session = obj("SessionResponse", user=UserSerializer())
    doc(v.LoginView, post=dict(operation_id="auth_login", summary="Sign in", request=login_in, responses={200: session}, description="Tokens arrive as HttpOnly cookies (access_token, refresh_token) plus a csrf_token cookie; the body carries only the user. Wrong credentials, an unknown account and a deactivated account all answer 401 with the same message. Too many failures answer 429."))
    doc(v.RefreshView, post=dict(operation_id="auth_refresh", summary="Swap the refresh cookie for a new pair", request=None, responses={200: session}, description="Needs the X-CSRF-Token header. Each refresh token works once."))
    doc(v.LogoutView, post=dict(operation_id="auth_logout", summary="Sign out", request=None, responses={204: None}, description="Retires the refresh token and clears the cookies. Works with an expired access token."))
    doc(v.MeView,
        get=dict(operation_id="auth_me_retrieve", summary="Who is signed in", responses={200: UserSerializer}),
        patch=dict(operation_id="auth_me_partial_update", summary="Change the language preference (the only field read)", request=PreferredLanguageSerializer, responses={200: UserSerializer}))
    doc(v.ChangePasswordView, post=dict(operation_id="auth_change_password", summary="Set a new password", request=ChangePasswordSerializer, responses={200: UserSerializer}, description="Works while a password change is pending. Fresh cookies are issued; every older token stops working."))
    created = extend(UserSerializer, "UserCreated", temporary_password=T(help_text="Shown once, here only.", read_only=True))
    doc(v.UserViewSet,
        create=dict(request=UserWriteSerializer, responses={201: created}),
        partial_update=dict(request=UserWriteSerializer, responses={200: UserSerializer}),
        deactivate=dict(request=None, responses={200: UserSerializer}),
        activate=dict(request=None, responses={200: UserSerializer}),
        reset_password=dict(request=None, responses={200: obj("TemporaryPassword", temporary_password=T())}),
        list=dict(parameters=[qp("department", int, "Department id."), qp("role", str, "Role key."), qp("status", str, "active or inactive.", ["active", "inactive"])]))
    person_login = obj("SignIn", timestamp=DT())
    client_row = obj("RecentClient", id=I(), company_name=T(), contact_person=T(), created_at=DT())
    ceo = obj("DashboardCeo", total_users=I(), active_users=I(), pending_password_users=I(), users_by_department=rows("DepartmentCount", department=T(), count=I()),
              total_clients=I(), recent_clients=client_row(many=True), recent_sign_ins=rows("RecentSignIn", user_id=I(), full_name=T(), timestamp=DT()))
    operation = obj("DashboardOperation", total_clients=I(), clients_this_month=I(), recent_clients=client_row(many=True))
    doc(v.DashboardSummaryView, get=dict(operation_id="dashboard_summary", summary="Home screen numbers", responses={200: obj("DashboardSummary", my_sign_ins=person_login(many=True), ceo=ceo(required=False), operation=operation(required=False))},
        description="`ceo` comes back for people who manage users, `operation` for the Operation head; everyone gets `my_sign_ins`."))


# --------------------------------------------------------------------------------------------------------------------
# audit, company, core, documents, files, comments, notifications
# --------------------------------------------------------------------------------------------------------------------
def _common():
    from audit import tracking
    from clients import views as clients_views
    from comments import views as comments
    from core import company, views as core_views
    from documents import views as documents
    from files import views as files
    from notifications import views as notif

    late_q = rows("LateQuotation", id=I(), ref=T(), company=T(), stage=T(), person=T(allow_null=True), since=DT(), minutes_late=I())
    doc(tracking.TrackingView, get=dict(operation_id="admin_tracking_retrieve", summary="Process tracking", responses={200: obj(
        "Tracking", generated_at=DT(), thresholds=obj("TrackingThresholds", hr=I(), commercial=I(), appointment=I())(),
        changed_today=tracking.FeedSerializer(many=True), late_quotations=late_q,
        missed_appointments=rows("MissedAppointment", id=I(), title=T(), owner=T(), starts_at=DT(), lead=T(allow_null=True)),
        overdue_follow_ups=rows("OverdueFollowUp", id=I(), ref=T(), company=T(), due=D(allow_null=True), owner=T(allow_null=True)),
        pipeline=obj("TrackingPipeline", leads=s.DictField(child=I(), help_text="Open leads by status."), clients=s.DictField(child=I(), help_text="Clients by decision."))(),
        team=rows("TeamActivity", id=I(), name=T(), today=I(), week=I()))}))
    doc(tracking.FeedFiltersView, get=dict(operation_id="admin_activity_filters_retrieve", summary="What the activity feed's filters offer", responses={200: obj(
        "FeedFilters", people=rows("FeedPerson", id=I(), name=T()), actions=many(T()), kinds=rows("FeedKind", key=T(), label=T()))}))

    company_out = obj("CompanyProfile", name_en=T(), name_ar=T(), quotation_prefix=T(), contract_prefix=T(), has_stamp=B(), updated_at=DT())
    patch_json = obj("CompanyPatchJson", name_en=T(required=False), name_ar=T(required=False), quotation_prefix=T(required=False), contract_prefix=T(required=False))
    patch_form = obj("CompanyPatchForm", name_en=T(required=False), name_ar=T(required=False), quotation_prefix=T(required=False), contract_prefix=T(required=False),
                     stamp=s.FileField(required=False, help_text="PNG under 500 KB."))
    doc(company.CompanyView,
        get=dict(operation_id="company_retrieve", responses={200: company_out}),
        patch=dict(operation_id="company_partial_update", request={"application/json": patch_json, "multipart/form-data": patch_form, "application/x-www-form-urlencoded": patch_json}, responses={200: company_out}))
    doc(company.CompanySetupView, get=dict(operation_id="company_setup_retrieve", summary="Is the company ready to sign documents?", responses={200: obj("CompanySetup", has_stamp=B(), can_manage=B())}))
    doc(company.CompanyStampView, get=dict(operation_id="company_stamp_retrieve", summary="The company stamp image", responses={(200, "image/png"): OpenApiTypes.BINARY}))

    doc(core_views.MyWorkView, get=dict(operation_id="my_work_retrieve", summary="Everything waiting on the signed-in person", responses={200: obj(
        "MyWork", role=T(), items=rows("MyWorkItem", kind=T(), section=T(), ref=T(), title=T(), link=T(), due=T(allow_null=True), overdue=B()), total=I(),
        badges=s.DictField(child=I(), help_text="Count of items per section."), unread_notifications=I())}))
    doc(core_views.HealthView, get=dict(operation_id="health_retrieve", summary="Liveness and database check", responses={200: obj("HealthOk", status=T()), 503: obj("HealthDown", status=T())}))

    version_row = rows("DocumentVersion", number=I(), date=DT(), by=T(allow_null=True), total=T(required=False), currency=T(required=False))
    doc(documents.ClientDocumentsView, get=dict(operation_id="documents_retrieve", summary="Documents of a client or lead", parameters=[qp("lead", int, "Lead id."), qp("client", int, "Client id (alternative to lead).")], responses={200: obj(
        "ClientDocuments", lead=I(), company=T(), items=rows("DocumentItem", kind=T(help_text="quotation, contract or meeting_report"), id=I(), ref=T(), status=T(), date=DT(), link=T(), download=T(), versions=version_row))}))

    att = files.AttachmentSerializer
    doc(files.AttachmentListCreateView,
        get=dict(parameters=[qp("target", str, "Parent record as kind:id, e.g. contract:3.", required=True), qp("archived", str, "1 includes archived files.", ["1"])]),
        post=dict(operation_id="files_create", summary="Upload a file to a record", parameters=[qp("target", str, "Parent record as kind:id (or send it in the form).")],
                  request={"multipart/form-data": obj("AttachmentUpload", file=s.FileField(), category=T(required=False), target=T(required=False))}, responses={201: att}))
    doc(files.AttachmentDownloadView, get=dict(operation_id="files_download", summary="Download a file", parameters=[pp("pk", "Attachment id.")], responses={(200, "application/octet-stream"): OpenApiTypes.BINARY},
        description="The content type is the one recorded at upload (pdf, png, jpeg, docx or xlsx). Sent as an attachment, no-store."))
    doc(files.AttachmentArchiveView, post=dict(operation_id="files_archive", summary="Archive a file (files are never deleted)", parameters=[pp("pk", "Attachment id.")], request=obj("ArchiveFileBody", reason=T(required=False)), responses={200: att}))

    doc(comments.CommentListCreateView,
        get=dict(parameters=[qp("target", str, "Record as kind:id.", required=True)]),
        post=dict(parameters=[qp("target", str, "Record as kind:id (or send it in the body).")], request=obj("CommentCreate", body=T(max_length=4000), mentions=many(I(), required=False, help_text="User ids from /mentionable/."), target=T(required=False)), responses={201: comments.CommentSerializer}))
    doc(comments.MentionableView, get=dict(operation_id="mentionable_list", summary="People who can be @mentioned on a record", parameters=[qp("target", str, "Record as kind:id.", required=True)], responses={200: PERSON(many=True)}))

    doc(notif.UnreadCountView, get=dict(operation_id="notifications_unread_count", responses={200: obj("UnreadCount", count=I())}))
    doc(notif.MarkReadView, post=dict(operation_id="notifications_mark_read", parameters=[pp("pk", "Notification id.")], request=None, responses={204: None}))
    doc(notif.MarkAllReadView, post=dict(operation_id="notifications_mark_all_read", request=None, responses={204: None}))
    doc(notif.NotificationListView, get=dict(parameters=[qp("unread", str, "1 returns unread only.", ["1"])]))

    doc(clients_views.ClientViewSet,
        portal=dict(request=None, responses={200: obj("PortalOpened", portal_status=T())}),
        decide=dict(request=obj("ClientDecision", decision=T(help_text="confirm, waiting or rejection"), next_follow_up=D(required=False), note=T(required=False), reason=I(required=False, help_text="Rejection reason id.")),
                    responses={200: obj("ClientDecided", contract=I(allow_null=True))}))


# --------------------------------------------------------------------------------------------------------------------
# reports, search
# --------------------------------------------------------------------------------------------------------------------
def _reports():
    from reports import views as v

    period = [qp("from", D, "First day, ISO date. Default: 90 days before `to` (365 for forecast)."), qp("to", D, "Last day, ISO date. Default: today."), ]
    doc(v.ReportIndex, get=dict(operation_id="reports_list", summary="The report sections this person may open", responses={200: obj("ReportIndex", sections=many(T()))}))
    doc(v.ReportView, get=dict(operation_id="reports_section_retrieve", summary="One report", parameters=[OpenApiParameter("section", str, OpenApiParameter.PATH, description="Section key from /reports/.")] + period,
        responses={200: obj("ReportData", period=obj("ReportPeriod", **{"from": D(), "to": D()})(), )}, description="The body carries `period` plus the series of that section; their keys depend on the section."))
    doc(v.ReportExport, get=dict(operation_id="reports_section_export", summary="Download one report", parameters=[OpenApiParameter("section", str, OpenApiParameter.PATH, description="Section key.")] + period + [
        qp("fmt", str, "csv (default), xlsx or pdf.", ["csv", "xlsx", "pdf"]), qp("lang", str, "pdf only: ar or en.", ["en", "ar"])],
        responses={(200, "text/csv"): OpenApiTypes.BINARY, (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY, (200, "application/pdf"): OpenApiTypes.BINARY}))
    doc(v.SearchView, get=dict(operation_id="search_retrieve", summary="Search leads, quotations, contracts and clients", parameters=[qp("q", str, "At least 2 characters.", required=True)], responses={200: obj(
        "SearchResults", q=T(), results=rows("SearchHit", kind=T(help_text="lead, quotation, contract or client"), id=I(), title=T(), subtitle=T(), href=T()))}))


# --------------------------------------------------------------------------------------------------------------------
# hr
# --------------------------------------------------------------------------------------------------------------------
def _hr():
    from hr import serializers as hs, views as v

    attendance_row = obj("AttendanceRow", user=I(), user_name=T(), department=T(), date=D(), first_in=DT(), last_out=DT(allow_null=True), hours=F(allow_null=True), late=B(), minutes_late=I(), open=B())
    summary = obj("AttendanceSummary", days=I(), late_days=I(), hours=F(), open_days=I())
    month = qp("month", str, "Month as YYYY-MM. Default: this month.")
    csv_note = "CSV download."
    doc(v.AttendanceMineView, get=dict(operation_id="hr_attendance_mine", summary="My attendance for a month", parameters=[month], responses={200: obj(
        "MyAttendance", month=T(), rows=attendance_row(many=True), summary=summary(), work_hours=obj("AttendanceWorkHours", work_start=T(), work_end=T(), grace_minutes=I())())}))
    doc(v.AttendanceMineExportView, get=dict(operation_id="hr_attendance_mine_export", summary="My attendance as CSV", parameters=[month], responses=CSV, description=csv_note))
    flt = [qp("from", D), qp("to", D), qp("user", int, "User id."), qp("department", str, "Department name."), qp("late", str, "1 keeps late days only.", ["1"]), qp("page", int), qp("page_size", int)]
    doc(v.AttendanceReportView, get=dict(operation_id="hr_attendance_report", summary="Attendance of everyone", parameters=flt, responses={200: obj(
        "AttendanceReportPage", count=I(), next=s.URLField(allow_null=True), previous=s.URLField(allow_null=True), results=attendance_row(many=True), summary=summary(),
        range=obj("AttendanceRange", **{"from": D(), "to": D()})())}))
    doc(v.AttendanceReportExportView, get=dict(operation_id="hr_attendance_report_export", summary="Attendance of everyone as CSV", parameters=flt[:5], responses=CSV, description=csv_note))
    doc(v.PeopleView, get=dict(operation_id="hr_people_list", summary="People for the attendance filter", responses={200: lst("HrPerson", id=I(), full_name=T(), department=T())}))

    ltype_in = obj("LeaveTypeInput", name_en=T(required=False), name_ar=T(required=False), paid=B(required=False), annual_days=I(required=False, allow_null=True), is_active=B(required=False))
    doc(v.LeaveTypeViewSet,
        list=dict(parameters=[qp("all", str, "1 includes inactive types (HR head only).", ["1"])], responses={200: hs.LeaveTypeSerializer(many=True)}),
        create=dict(request=ltype_in, responses={201: hs.LeaveTypeSerializer}),
        partial_update=dict(parameters=[pp()], request=ltype_in, responses={200: hs.LeaveTypeSerializer}))
    leave_one = {200: hs.LeaveRequestSerializer}
    doc(v.LeaveViewSet,
        list=dict(parameters=[qp("scope", str, "mine (default), all or decide.", ["mine", "all", "decide"]), qp("status", str, "Comma-separated statuses."), qp("page", int), qp("page_size", int)],
                  responses={200: page("LeaveRequestPage", hs.LeaveRequestSerializer)}),
        create=dict(request=obj("LeaveRequestInput", leave_type=I(), start_date=D(), end_date=D(), reason=T(required=False)), responses={201: hs.LeaveRequestSerializer}),
        approve=dict(parameters=[pp()], request=None, responses=leave_one),
        reject=dict(parameters=[pp()], request=obj("LeaveRejectBody", note=T(required=False)), responses=leave_one),
        cancel=dict(parameters=[pp()], request=None, responses=leave_one),
        balance=dict(parameters=[qp("user", int, "User id (HR and CEO only)."), qp("year", int)], responses={200: obj(
            "LeaveBalance", year=I(), balances=rows("LeaveBalanceRow", leave_type=I(), name_en=T(), name_ar=T(), paid=B(), allowance=I(allow_null=True), used=F(), pending=F(), remaining=F(allow_null=True)))}),
        calendar=dict(parameters=[month], responses={200: obj("LeaveCalendar", month=T(), weekend_days=many(I()), results=hs.LeaveRequestSerializer(many=True))}))
    doc(v.SalaryViewSet,
        list=dict(responses={200: lst("SalaryRow", user=I(), user_name=T(), department=T(), base_salary=T(allow_null=True), currency=T(allow_null=True))}),
        update=dict(parameters=[pp("id", "User id.")], request=obj("SalaryInput", base_salary=T(help_text="Decimal amount."), currency=T(required=False)), responses={200: hs.SalarySerializer}))
    run_in = obj("PayrollRunInput", month=T(help_text="YYYY-MM"))
    run_detail = extend(hs.RunSerializer, "PayrollRunDetail", entries=hs.EntrySerializer(many=True, read_only=True))
    doc(v.RunViewSet,
        list=dict(parameters=[qp("page", int), qp("page_size", int)], responses={200: page("PayrollRunPage", hs.RunSerializer)}),
        create=dict(request=run_in, responses={201: hs.RunSerializer}),
        retrieve=dict(parameters=[pp()], responses={200: run_detail}),
        refresh=dict(parameters=[pp()], request=None, responses={200: run_detail}),
        approve=dict(parameters=[pp()], request=None, responses={200: run_detail}),
        reopen=dict(parameters=[pp()], request=obj("PayrollReopenBody", reason=T()), responses={200: run_detail}),
        pay=dict(parameters=[pp()], request=None, responses={200: run_detail}),
        export=dict(parameters=[pp()], responses=CSV))
    doc(v.EntryViewSet, partial_update=dict(parameters=[pp()], request=obj("PayrollEntryInput", allowances=T(required=False), deductions=T(required=False), note=T(required=False)), responses={200: hs.EntrySerializer}))
    doc(v.PayslipViewSet, list=dict(responses={200: hs.PayslipSerializer(many=True)}), retrieve=dict(parameters=[pp()], responses={200: hs.PayslipSerializer}))


# --------------------------------------------------------------------------------------------------------------------
# leads
# --------------------------------------------------------------------------------------------------------------------
def _leads():
    from leads import serializers as ls, views as v

    lead_fields = dict(company_name=T(), contact_name=T(required=False), position=T(required=False), phone=T(required=False), email=T(required=False), location=T(required=False), source=T(required=False), notes=T(required=False))
    create_in = obj("LeadCreate", **lead_fields, allow_duplicate=B(required=False))
    update_in = obj("LeadUpdate", **{k: type(f)(required=False) for k, f in lead_fields.items()}, updated_at=DT(required=False, help_text="The value last read, for the optimistic-concurrency check."))
    doc(v.LeadViewSet,
        create=dict(request={"application/json": create_in, "application/x-www-form-urlencoded": create_in, "multipart/form-data": create_in}, responses={201: ls.LeadSerializer}),
        partial_update=dict(request={"application/json": update_in, "application/x-www-form-urlencoded": update_in, "multipart/form-data": update_in}, responses={200: ls.LeadSerializer}),
        board=dict(responses={200: obj("LeadBoard", columns=rows("LeadBoardColumn", status=T(), count=I(), results=many(s.DictField(), help_text="Lead objects (same shape as the list rows).")), limit=I())}),
        assignees=dict(responses={200: lst("LeadAssignee", id=I(), full_name=T(), role=T(), open_leads=I())}),
        assign=dict(request=obj("LeadAssignBody", assigned_to=I()), responses={200: ls.LeadSerializer}),
        history=dict(responses={200: ls.StatusChangeSerializer(many=True)}),
        outcome=dict(request=ls.ContactInputSerializer, responses={200: ls.LeadSerializer}),
        reopen=dict(request=NOTE, responses={200: ls.LeadSerializer}),
        skip_quotation=dict(request=NOTE, responses={200: ls.LeadSerializer}),
        archive=dict(request=REASON, responses={200: ls.LeadSerializer}),
        restore=dict(request=None, responses={200: ls.LeadSerializer}),
        import_template=dict(summary="Download the import template", parameters=[qp("file", str, "xlsx (default) or csv.", ["xlsx", "csv"]), qp("lang", str, "en or ar.", ["en", "ar"])],
                             responses={(200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY, (200, "text/csv"): OpenApiTypes.BINARY}),
        import_preview=dict(request={"multipart/form-data": obj("LeadImportFile", file=s.FileField())}, responses={200: obj(
            "LeadImportPreview", file_name=T(), rows=many(s.DictField(), help_text="One object per row: row, the lead fields, state, errors[], duplicate_of, duplicate_in_file."), summary=s.DictField())}),
        import_confirm=dict(request={"multipart/form-data": obj("LeadImportConfirmFile", file=s.FileField())}, responses={201: ls.ImportBatchSerializer}))
    # `interactions` takes GET (list) and POST (log a contact)
    extend_schema_view(interactions=extend_schema(methods=["GET"], responses={200: ls.InteractionSerializer(many=True)}))(v.LeadViewSet)
    extend_schema_view(interactions=extend_schema(methods=["POST"], request=ls.ContactInputSerializer, responses={201: ls.LeadSerializer}))(v.LeadViewSet)
    doc(v.ImportBatchViewSet, undo=dict(request=None, responses={200: ls.ImportBatchSerializer}))

    day = rows("TargetDay", date=D(), count=I(allow_null=True), total=I(allow_null=True), plan=F())
    progress = obj("LeadTargetProgress", id=I(), user=I(allow_null=True), user_name=T(allow_null=True), start_date=D(), end_date=D(), target=I(), set_by=I(), set_by_name=T(),
                   state=T(help_text="upcoming, active or ended"), added=I(), remaining=I(), percent=F(), days_in_range=I(), days_elapsed=I(), days_left=I(), expected_by_today=F(),
                   on_track=B(allow_null=True), required_per_day=F(allow_null=True), days=day)
    dash = obj("LeadsDashboard", today=D(), total=I(), added=obj("LeadsAdded", today=I(), last_7_days=I(), this_month=I())(), contact_rate=F(), acceptance_rate=F(),
               follow_ups=obj("LeadsFollowUps", due_today=I(), overdue=I())(), per_day=rows("LeadsPerDay", date=D(), count=I()), by_status=rows("LeadsByStatus", status=T(), count=I()),
               by_source=rows("LeadsBySource", source=T(), count=I()), top_contributors=rows("LeadsContributor", id=I(allow_null=True), name=T(allow_null=True), count=I()))
    doc(v.DashboardView, get=dict(operation_id="leads_dashboard_retrieve", responses={200: dash}))
    target_in = obj("LeadTargetInput", user=I(required=False, help_text="Marketing employee id (create)."), start_date=D(required=False), end_date=D(required=False), target=I(required=False))
    doc(v.TargetListView,
        get=dict(operation_id="leads_targets_list", parameters=[qp("all", str, "1 adds ended targets.", ["1"]), qp("user", int, "Narrow to one person (managers).")], responses={200: progress(many=True)}),
        post=dict(operation_id="leads_targets_create", request=target_in, responses={201: progress}))
    doc(v.TargetDetailView,
        get=dict(operation_id="leads_targets_retrieve", parameters=[pp("pk", "Target id.")], responses={200: progress}),
        patch=dict(operation_id="leads_targets_partial_update", parameters=[pp("pk", "Target id.")], request=target_in, responses={200: progress}),
        delete=dict(operation_id="leads_targets_destroy", parameters=[pp("pk", "Target id.")], responses={204: None}))
    doc(v.TargetAssigneesView, get=dict(operation_id="leads_target_assignees_list", responses={200: PERSON(many=True)}))


# --------------------------------------------------------------------------------------------------------------------
# quotations, contracts, appointments, meetings
# --------------------------------------------------------------------------------------------------------------------
def _documents():
    from appointments import views as av
    from contracts import serializers as cs, views as cv
    from meetings import views as mv
    from quotations import serializers as qs, views as qv

    line = obj("QuotationLineInput", description=T(), quantity=T(required=False), unit_price=T(required=False), discount_percent=T(required=False), tax_percent=T(required=False),
               service=I(required=False, allow_null=True), frequency=T(required=False), visits=I(required=False, allow_null=True))
    draft = obj("QuotationDraftInput", currency=T(required=False, help_text="Three letters, default JOD."), valid_until=D(required=False), notes=T(required=False), payment_terms=T(required=False), lines=line(many=True, required=False))
    q = qs.QuotationDetailSerializer
    doc(qv.QuotationViewSet,
        create=dict(request=obj("QuotationAsk", lead=I(), note=T(required=False)), responses={201: q}),
        assign=dict(request=obj("QuotationAssign", assigned_to=I()), responses={200: q}),
        hr_people=dict(responses={200: PERSON(many=True)}),
        start=dict(request=None, responses={200: q}),
        draft=dict(request=draft, responses={200: q}),
        submit=dict(request=None, responses={200: q}),
        request_changes=dict(request=COMMENT, responses={200: q}),
        sign=dict(request=obj("QuotationSignBody", signature=T(help_text="Signature as sent by the signing pad (data URL).")), responses={200: q}),
        cancel=dict(request=REASON, responses={200: q}),
        send=dict(request=None, responses={200: q}),
        document=dict(parameters=FMT, responses=PDF_OR_DOCX),
        signed_copy=dict(request={"multipart/form-data": obj("SignedCopyUpload", file=s.FileField())}, responses={200: q}),
        outcome=dict(request=obj("QuotationOutcome", outcome=T(help_text="waiting, rejected or accepted"), next_follow_up=D(required=False), rejection_reason=I(required=False), rejection_note=T(required=False)), responses={200: q}))
    c = cs.ContractDetailSerializer
    doc(cv.ContractViewSet,
        create=dict(request=obj("ContractAsk", lead=I(), note=T(required=False)), responses={201: c}),
        start=dict(request=None, responses={200: c}),
        send=dict(request=NOTE, responses={200: c}),
        draft=dict(request=obj("ContractDraftInput", template=I(required=False), title=T(required=False), body_en=T(required=False), body_ar=T(required=False), payment_terms=T(required=False),
                               start_date=D(required=False), end_date=D(required=False), currency=T(required=False), total=T(required=False)), responses={200: c}),
        commercial_return=dict(request=COMMENT, responses={200: c}),
        confirm=dict(request=None, responses={200: c}),
        send_to_client=dict(request=None, responses={200: c}),
        client_copy=dict(request={"multipart/form-data": obj("ClientCopyUpload", file=s.FileField())}, responses={200: c}),
        document=dict(parameters=FMT, responses=PDF_OR_DOCX),
        approve=dict(request={"application/json": obj("ContractApproveJson", signature=T(required=False)), "multipart/form-data": obj("ContractApproveForm", signature=T(required=False), file=s.FileField(required=False))}, responses={200: c}),
        return_=dict(request=COMMENT, responses={200: c}),
        handover=dict(request=None, responses={200: c}),
        cancel=dict(request=REASON, responses={200: c}))
    appt_in = obj("AppointmentInput", title=T(), type=T(required=False, help_text="meeting (default), follow_up, ..."), starts_at=DT(), ends_at=DT(required=False, allow_null=True), lead=I(required=False, allow_null=True),
                  owner=I(required=False, help_text="Commercial head only."), notes=T(required=False))
    appt_patch = obj("AppointmentPatch", title=T(required=False), type=T(required=False), notes=T(required=False), starts_at=DT(required=False), ends_at=DT(required=False, allow_null=True))
    doc(av.AppointmentViewSet,
        create=dict(request=appt_in), partial_update=dict(request=appt_patch),
        reschedule=dict(request=obj("AppointmentReschedule", starts_at=DT(), ends_at=DT(required=False, allow_null=True))),
        cancel=dict(request=REASON), complete=dict(request=None),
        assignees=dict(responses={200: PERSON(many=True)}),
        list=dict(parameters=[qp("owner", int), qp("scope", str, "mine limits to the signed-in person.", ["mine"]), qp("type", str), qp("status", str), qp("lead", int), qp("from", D), qp("to", D)]))
    report_in = obj("MeetingReportInput", appointment=I(help_text="A completed appointment with a lead."), attendees=T(required=False), summary=T(), decisions=T(required=False), next_steps=T(required=False))
    report_patch = obj("MeetingReportPatch", attendees=T(required=False), summary=T(required=False), decisions=T(required=False), next_steps=T(required=False), held_on=D(required=False))
    doc(mv.MeetingReportViewSet,
        create=dict(request=report_in), partial_update=dict(request=report_patch),
        sign=dict(request=obj("ReportSignBody", signature=T()), ),
        approve=dict(request=None), return_=dict(request=COMMENT),
        document=dict(parameters=FMT[:2], responses=PDF_OR_DOCX),
        list=dict(parameters=[qp("status", str), qp("appointment", int), qp("lead", int)]))


# --------------------------------------------------------------------------------------------------------------------
# operations, handovers, projects, payments, general tasks
# --------------------------------------------------------------------------------------------------------------------
def _operations():
    from generaltasks import views as gv
    from operations import handover_api as hv, monitoring, serializers as os_, views as ov
    from payments import views as pv
    from payments.serializers import InstalmentSerializer, PaymentSerializer

    detail = os_.OpClientDetailSerializer
    doc(ov.OpClientViewSet,
        cadence=dict(request=obj("QaCadenceBody", qa_cadence_days=I(allow_null=True)), responses={200: detail}),
        checklist=dict(request=obj("ChecklistItemInput", name_en=T(), name_ar=T(), required=B(required=False)), responses={200: detail}))
    item = os_.ChecklistItemSerializer
    doc(ov.ChecklistViewSet,
        verify=dict(parameters=[pp()], request=obj("ChecklistVerify", expires_on=D(required=False, allow_null=True)), responses={200: item}),
        reset=dict(parameters=[pp()], request=NOTE, responses={200: item}),
        not_applicable=dict(parameters=[pp()], request=REASON, responses={200: item}),
        required=dict(parameters=[pp()], request=obj("ChecklistRequired", required=B()), responses={200: item}),
        archive=dict(parameters=[pp()], request=None, responses={200: item}))
    recurring_in = obj("RecurringInput", client=I(help_text="Required on create."), title=T(required=False), description=T(required=False), frequency=T(required=False), interval_days=I(required=False, allow_null=True),
                       start_date=D(required=False), assignee=I(required=False, allow_null=True), active=B(required=False))
    doc(ov.RecurringViewSet, create=dict(request=recurring_in), partial_update=dict(request=recurring_in))
    t = os_.TaskSerializer
    body = lambda name, **f: obj(name, **f)
    doc(ov.TaskViewSet,
        list=dict(parameters=[qp("mine", str, "1 keeps the signed-in person's tasks.", ["1"]), qp("overdue", str, "1 keeps overdue active tasks.", ["1"])]),
        complete=dict(request=NOTE, responses={200: t}),
        start=dict(request=None, responses={200: t}),
        progress=dict(request=body("TaskProgressBody", progress=I(), note=T(required=False)), responses={200: t}),
        wait=dict(request=REASON, responses={200: t}), block=dict(request=REASON, responses={200: t}),
        resume=dict(request=None, responses={200: t}),
        submit=dict(request=NOTE, responses={200: t}), approve=dict(request=None, responses={200: t}),
        send_back=dict(request=COMMENT, responses={200: t}), escalate=dict(request=REASON, responses={200: t}),
        publish=dict(request=body("TaskPublishBody", attachment=I(help_text="Attachment id of the deliverable file."), title=T(required=False)), responses={200: t}),
        skip=dict(request=REASON, responses={200: t}))
    doc(ov.AssigneeViewSet, list=dict(operation_id="operation_assignees_list", responses={200: lst("OperationAssignee", id=I(), full_name=T(), is_head=B())}))
    doc(ov.MeetingViewSet, create=dict(request=body("QaMeetingInput", client=I(), held_on=D(), notes=T(required=False), next_date=D(required=False, allow_null=True))))

    count_cols = ("open", "in_progress", "waiting", "blocked", "submitted", "overdue")
    totals = obj("MonitoringTotals", **{k: I() for k in count_cols}, unassigned=I())
    doc(monitoring.MonitoringView, get=dict(operation_id="operation_monitoring_retrieve", responses={200: obj(
        "Monitoring", today=D(), totals=totals(), people=rows("MonitoringPerson", id=I(), name=T(), **{k: I() for k in count_cols}),
        attention=rows("MonitoringTask", id=I(), title=T(), client=I(), client_name=T(), assignee_name=T(allow_null=True), status=T(), due_date=D(), overdue=B(), escalation_level=I()), escalations_open=I())}))

    h = hv.HandoverSerializer
    doc(hv.HandoverViewSet,
        save=dict(request=body("HandoverSaveBody", services=T(required=False), scope_notes=T(required=False), contacts=T(required=False), special_requirements=T(required=False), start_date=D(required=False, allow_null=True)), responses={200: h}),
        submit=dict(request=None, responses={200: h}), accept=dict(request=None, responses={200: h}),
        send_back=dict(request=COMMENT, responses={200: h}), escalate=dict(request=REASON, responses={200: h}))
    p = hv.ProjectSerializer
    doc(hv.ProjectViewSet,
        primary=dict(request=body("ProjectPrimaryBody", user=I(), reason=T(required=False)), responses={200: p}),
        support=dict(request=body("ProjectSupportBody", user=I()), responses={200: p}),
        remove=dict(request=body("ProjectRemoveBody", user=I(), reason=T(required=False)), responses={200: p}))

    money = lambda: T(help_text="Decimal amount as text.")
    totals_p = s.DictField(help_text="total, paid, balance and counts, as the statement computes them.")
    statement = obj("PaymentStatement", client=obj("StatementClient", id=I(), company_name=T())(), currency=T(), totals=totals_p, instalments=InstalmentSerializer(many=True),
                    payments=PaymentSerializer(many=True), permissions=obj("StatementPermissions", can_write=B())())
    doc(pv.OverviewView, get=dict(operation_id="payments_overview", parameters=[qp("search", str), qp("filter", str, "overdue, open or settled.", ["overdue", "open", "settled"]), qp("page", int), qp("page_size", int)],
        responses={200: page("PaymentsOverviewPage", obj("PaymentsOverviewRow", client=I(), company_name=T(), currency=T(), instalments=I(), overdue_count=I(), total=money(), paid=money(), balance=money()))}))
    doc(pv.ClientPaymentsViewSet,
        retrieve=dict(parameters=[pp("id", "Client id.")], responses={200: statement}),
        export=dict(parameters=[pp("id", "Client id.")], responses=CSV),
        schedule=dict(parameters=[pp("id", "Client id.")], request=body("PaymentSchedule", currency=T(required=False), instalments=rows("InstalmentInput", due_date=D(), amount=money(), note=T(required=False))), responses={201: statement}))
    paid = type("PaymentRecorded", (statement,), {"recorded": I(allow_null=True)})
    doc(pv.InstalmentViewSet,
        partial_update=dict(parameters=[pp()], request=body("InstalmentPatch", due_date=D(required=False), amount=money(), note=T(required=False)), responses={200: statement}),
        cancel=dict(parameters=[pp()], request=REASON, responses={200: statement}),
        pay=dict(parameters=[pp()], request=body("PaymentInput", amount=money(), received_on=D(), method=T(required=False), reference=T(required=False), note=T(required=False)), responses={201: paid}))
    doc(pv.PaymentViewSet, reverse=dict(parameters=[pp()], request=REASON, responses={201: statement}))

    doc(gv.GeneralTaskViewSet,
        list=dict(parameters=[qp("view", str, "mine (default), given or all visible.", ["mine", "given", "all"]), qp("status", str, "open or done.", ["open", "done"]), qp("overdue", str, "1 keeps overdue tasks.", ["1"]), qp("assignee", int)]),
        create=dict(request=body("GeneralTaskInput", title=T(), description=T(required=False), assignee=I(), deadline=D())),
        partial_update=dict(request=body("GeneralTaskPatch", title=T(required=False), description=T(required=False), assignee=I(required=False), deadline=D(required=False))),
        done=dict(request=None),
        counters=dict(responses={200: obj("GeneralTaskCounters", mine=obj("TaskCountsMine", open=I(), overdue=I(), due_today=I(), done=I(), done_late=I())(),
                                          team=obj("TaskCountsTeam", open=I(), overdue=I(), due_today=I(), done=I(), done_late=I())(required=False, allow_null=True))}),
        assignees=dict(responses={200: lst("TaskAssignee", id=I(), full_name=T(), department=T(allow_null=True))}))


# --------------------------------------------------------------------------------------------------------------------
# client portal
# --------------------------------------------------------------------------------------------------------------------
def _portal():
    from clients import portal as p

    sign = obj("PortalSignBody", signature=T(help_text="Signature as sent by the signing pad (data URL)."))
    pk = [pp("pk")]
    doc(p.PortalMeView, get=dict(operation_id="portal_me_retrieve", responses={200: obj("PortalMe", client=p.PortalClientSerializer())}))
    doc(p.PortalQuotationListView, get=dict(operation_id="portal_quotations_list", responses={200: p.PortalQuotationSerializer(many=True)}))
    doc(p.PortalQuotationDetailView, get=dict(operation_id="portal_quotations_retrieve", parameters=pk, responses={200: p.PortalQuotationSerializer}))
    doc(p.PortalQuotationDocumentView, get=dict(operation_id="portal_quotations_document", parameters=pk + FMT[:2], responses=PDF_OR_DOCX))
    doc(p.PortalQuotationSignView, post=dict(operation_id="portal_quotations_sign", parameters=pk, request=sign, responses={200: p.PortalQuotationSerializer}))
    doc(p.PortalContractListView, get=dict(operation_id="portal_contracts_list", responses={200: p.PortalContractSerializer(many=True)}))
    doc(p.PortalContractDetailView, get=dict(operation_id="portal_contracts_retrieve", parameters=pk, responses={200: p.PortalContractSerializer}))
    doc(p.PortalContractDocumentView, get=dict(operation_id="portal_contracts_document", parameters=pk + FMT[:2], responses=PDF_OR_DOCX))
    doc(p.PortalContractSignView, post=dict(operation_id="portal_contracts_sign", parameters=pk, request=sign, responses={200: p.PortalContractSerializer}))
    doc(p.PortalDeliverableListView, get=dict(operation_id="portal_deliverables_list", responses={200: p.PortalDeliverableSerializer(many=True)}))
    doc(p.PortalDeliverableDownloadView, get=dict(operation_id="portal_deliverables_download", parameters=pk, responses={(200, "application/octet-stream"): OpenApiTypes.BINARY}))
    doc(p.PortalDeliverableAcknowledgeView, post=dict(operation_id="portal_deliverables_acknowledge", parameters=pk, request=None, responses={200: p.PortalDeliverableSerializer}))


for _fn in (_accounts, _common, _reports, _hr, _leads, _documents, _operations, _portal):
    _fn()
