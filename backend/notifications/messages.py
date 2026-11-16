"""
Every notification text, in both languages. A module adds its kinds here.
Placeholders use str.format names: {name}, {ref}, {actor}, {who}.
"""

CATALOG = {
    "assigned": {
        "en": ("{actor} assigned you {ref}", "{name}"),
        "ar": ("قام {actor} بإسنادك إلى {ref}", "{name}"),
    },
    "mention": {
        "en": ("{actor} mentioned you in {ref}", "{name}"),
        "ar": ("أشار إليك {actor} في {ref}", "{name}"),
    },
    "comment": {
        "en": ("{actor} commented on {ref}", "{name}"),
        "ar": ("علّق {actor} على {ref}", "{name}"),
    },
    "request_received": {
        "en": ("New request: {ref}", "{name}"),
        "ar": ("طلب جديد: {ref}", "{name}"),
    },
    "returned": {
        "en": ("{ref} was returned with changes", "{name}"),
        "ar": ("أُعيد {ref} مع طلب تعديلات", "{name}"),
    },
    "approved": {
        "en": ("{ref} was approved", "{name}"),
        "ar": ("تمت الموافقة على {ref}", "{name}"),
    },
    "signed": {
        "en": ("{ref} was signed", "{name}"),
        "ar": ("تم توقيع {ref}", "{name}"),
    },
    "contract_review": {
        "en": ("Contract waiting for your review: {ref}", "{name}"),
        "ar": ("عقد بانتظار مراجعتك: {ref}", "{name}"),
    },
    "contract_handover": {
        "en": ("New contract handed over: {ref}", "{name}"),
        "ar": ("عقد جديد تم تسليمه: {ref}", "{name}"),
    },
    "task_due": {
        "en": ("Task due: {ref}", "{name}"),
        "ar": ("مهمة مستحقة: {ref}", "{name}"),
    },
    "client_active": {
        "en": ("Client is now active: {ref}", "{name}"),
        "ar": ("أصبح العميل نشطًا: {ref}", "{name}"),
    },
    "qa_overdue": {
        "en": ("QA meeting overdue: {ref}", "{name}"),
        "ar": ("اجتماع المتابعة متأخر: {ref}", "{name}"),
    },
    "overdue": {
        "en": ("{ref} is overdue", "{name}"),
        "ar": ("{ref} متأخر عن موعده", "{name}"),
    },
    "leads_new": {
        "en": ("New leads to assign: {count}", "{name}"),
        "ar": ("عملاء محتملون جدد للإسناد: {count}", "{name}"),
    },
    "lead_qualified": {
        "en": ("{actor} qualified {ref}", "{name}"),
        "ar": ("قام {actor} بتأهيل {ref}", "{name}"),
    },
    "lead_rejected": {
        "en": ("{actor} marked {ref} as rejected", "{name}"),
        "ar": ("قام {actor} برفض {ref}", "{name}"),
    },
    "lead_reopened": {
        "en": ("{actor} reopened {ref}", "{name}"),
        "ar": ("أعاد {actor} فتح {ref}", "{name}"),
    },
    "target_assigned": {
        "en": ("{actor} gave you a leads target: {name}", "{when}"),
        "ar": ("حدّد لك {actor} هدفًا للعملاء المحتملين: {name}", "{when}"),
    },
    "appointment_assigned": {
        "en": ("{actor} gave you an appointment", "{name} · {when}"),
        "ar": ("أسند إليك {actor} موعدًا", "{name} · {when}"),
    },
    "appointment_rescheduled": {
        "en": ("{actor} rescheduled an appointment", "{name} · {when}"),
        "ar": ("أعاد {actor} جدولة موعد", "{name} · {when}"),
    },
    "appointment_cancelled": {
        "en": ("{actor} cancelled an appointment", "{name} · {when}"),
        "ar": ("ألغى {actor} موعدًا", "{name} · {when}"),
    },
    "appointment_reminder": {
        "en": ("Coming up: {name}", "{when}"),
        "ar": ("موعد قريب: {name}", "{when}"),
    },
    "followup_overdue": {
        "en": ("Follow-up overdue: {ref}", "{name}"),
        "ar": ("متابعة متأخرة: {ref}", "{name}"),
    },
    "first_contact_overdue": {
        "en": ("{ref} still needs its first contact", "{name}"),
        "ar": ("{ref} ما زال بانتظار أول تواصل", "{name}"),
    },
    "assign_needed": {
        "en": ("{ref} has no one assigned", "{name}"),
        "ar": ("{ref} بلا مسؤول عنه", "{name}"),
    },
    "quotation_review": {
        "en": ("{ref} is ready for your review", "{name}"),
        "ar": ("{ref} جاهز لمراجعتك", "{name}"),
    },
    "quotation_assigned": {
        "en": ("{ref} was handed to you to prepare", "{name}"),
        "ar": ("تم تكليفك بإعداد {ref}", "{name}"),
    },
    "quotation_sent_client": {
        "en": ("A quotation is waiting for your signature: {ref}", "{name}"),
        "ar": ("عرض سعر بانتظار توقيعك: {ref}", "{name}"),
    },
    "quotation_confirmed": {
        "en": ("{actor} confirmed {ref}", "{name}"),
        "ar": ("قام {actor} بتأكيد {ref}", "{name}"),
    },
    "quotation_rejected": {
        "en": ("{actor} marked {ref} as rejected", "{name}"),
        "ar": ("قام {actor} برفض {ref}", "{name}"),
    },
    "leave_requested": {
        "en": ("{actor} requested leave", "{ref} · {name}"),
        "ar": ("طلب {actor} إجازة", "{ref} · {name}"),
    },
    "leave_approved": {
        "en": ("Your leave was approved", "{ref} · {name}"),
        "ar": ("تمت الموافقة على إجازتك", "{ref} · {name}"),
    },
    "leave_rejected": {
        "en": ("Your leave request was declined", "{ref}: {name}"),
        "ar": ("تم رفض طلب إجازتك", "{ref}: {name}"),
    },
    "payroll_approved": {
        "en": ("Payroll {ref} was approved", "You can mark it as paid."),
        "ar": ("تمت الموافقة على رواتب {ref}", "يمكنك تحديدها كمدفوعة."),
    },
    "payroll_reopened": {
        "en": ("Payroll {ref} was sent back to draft", "{name}"),
        "ar": ("أُعيدت رواتب {ref} إلى المسودة", "{name}"),
    },
    "payslip_ready": {
        "en": ("Your payslip for {ref} is ready", "Open Payroll to see it."),
        "ar": ("قسيمة راتبك لشهر {ref} جاهزة", "افتح الرواتب لعرضها."),
    },
    "payment_overdue": {
        "en": ("Payment overdue: {ref}", "{name}"),
        "ar": ("دفعة متأخرة: {ref}", "{name}"),
    },
}


def render(kind, lang, **params):
    entry = CATALOG.get(kind)
    if entry is None:
        return kind, ""
    title, body = entry.get(lang) or entry["en"]
    safe = {k: ("" if v is None else v) for k, v in params.items()}

    class _Blank(dict):
        def __missing__(self, key):
            return ""

    return title.format_map(_Blank(safe)).strip(), body.format_map(_Blank(safe)).strip()
