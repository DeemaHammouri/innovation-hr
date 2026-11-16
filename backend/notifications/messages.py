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
    "handover_requested": {
        "en": ("Fill in the handover for {name}", "{ref}"),
        "ar": ("املأ نموذج التسليم الخاص بـ {name}", "{ref}"),
    },
    "handover_submitted": {
        "en": ("New handover to review: {name}", "{ref}"),
        "ar": ("تسليم جديد بانتظار المراجعة: {name}", "{ref}"),
    },
    "handover_accepted": {
        "en": ("Operation accepted the handover for {name}", "{ref}"),
        "ar": ("قبلت العمليات تسليم {name}", "{ref}"),
    },
    "handover_returned": {
        "en": ("The handover for {name} was returned", "{ref}"),
        "ar": ("أُعيد تسليم {name} للتعديل", "{ref}"),
    },
    "handover_escalated": {
        "en": ("Handover escalated to the CEO: {name}", "{ref}"),
        "ar": ("تم تصعيد تسليم {name} إلى المدير التنفيذي", "{ref}"),
    },
    "kyc_expired": {
        "en": ("Document expired: {ref}", "{name}"),
        "ar": ("انتهت صلاحية مستند: {ref}", "{name}"),
    },
    "kyc_expiring": {
        "en": ("Document expires soon: {ref}", "{name}"),
        "ar": ("مستند تنتهي صلاحيته قريبًا: {ref}", "{name}"),
    },
    "project_assigned": {
        "en": ("You were assigned to a project: {name}", "{ref}"),
        "ar": ("تم تعيينك على مشروع: {name}", "{ref}"),
    },
    "project_unassigned": {
        "en": ("You were taken off a project: {name}", "{ref}"),
        "ar": ("تمت إزالتك من مشروع: {name}", "{ref}"),
    },
    "task_submitted": {
        "en": ("Task submitted for review: {ref}", "{name}"),
        "ar": ("مهمة بانتظار المراجعة: {ref}", "{name}"),
    },
    "task_approved": {
        "en": ("Task approved: {ref}", "{name}"),
        "ar": ("تمت الموافقة على المهمة: {ref}", "{name}"),
    },
    "task_returned": {
        "en": ("Task sent back to you: {ref}", "{name}"),
        "ar": ("أُعيدت إليك المهمة: {ref}", "{name}"),
    },
    "task_escalated": {
        "en": ("Task escalated: {ref}", "{name}"),
        "ar": ("تم تصعيد مهمة: {ref}", "{name}"),
    },
    "deliverable_published": {
        "en": ("A new file is ready for you: {ref}", "{name}"),
        "ar": ("ملف جديد جاهز لك: {ref}", "{name}"),
    },
    "deliverable_acknowledged": {
        "en": ("The client confirmed receiving: {ref}", "{name}"),
        "ar": ("أكد العميل استلام: {ref}", "{name}"),
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
    "urgent_hr": {
        "en": ("Urgent: {ref} is still waiting for you", "{name}: assigned to you more than {minutes} minutes ago and not submitted."),
        "ar": ("عاجل: {ref} ما زال بانتظارك", "{name}: أُسند إليك منذ أكثر من {minutes} دقيقة ولم يُرسل بعد."),
    },
    "urgent_commercial": {
        "en": ("Urgent: {ref} needs your signature", "{name}: submitted more than {minutes} minutes ago and not signed."),
        "ar": ("عاجل: {ref} بانتظار توقيعك", "{name}: أُرسل منذ أكثر من {minutes} دقيقة ولم يُوقَّع بعد."),
    },
    "urgent_appointment": {
        "en": ("Urgent: this appointment is still open", "{name} was due at {when}. Complete it, reschedule it or cancel it."),
        "ar": ("عاجل: الموعد ما زال مفتوحًا", "{name} كان موعده {when}. أنجزه أو أعد جدولته أو ألغِه."),
    },
    "contract_confirmed": {
        "en": ("{ref} was confirmed: you can send it to the client", "{name}"),
        "ar": ("تم تأكيد {ref}: يمكنك إرساله إلى العميل", "{name}"),
    },
    "contract_sent_client": {
        "en": ("A contract is waiting for your signature: {ref}", "{name}"),
        "ar": ("عقد بانتظار توقيعك: {ref}", "{name}"),
    },
    "contract_signed_client": {
        "en": ("Your contract {ref} is signed by the company", "{name}"),
        "ar": ("وقّعت الشركة عقدك {ref}", "{name}"),
    },
    "report_sign": {
        "en": ("A meeting report is ready for you to sign: {ref}", "{name}"),
        "ar": ("تقرير اجتماع بانتظار توقيعك: {ref}", "{name}"),
    },
    "report_approve": {
        "en": ("A meeting report is waiting for your approval: {ref}", "{name}"),
        "ar": ("تقرير اجتماع بانتظار اعتمادك: {ref}", "{name}"),
    },
    "report_approved": {
        "en": ("Meeting report {ref} was approved", "{name}"),
        "ar": ("تم اعتماد تقرير الاجتماع {ref}", "{name}"),
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
    "gtask_assigned": {
        "en": ("{actor} gave you a task: {ref}", "Due {name}"),
        "ar": ("أسند إليك {actor} مهمة: {ref}", "الاستحقاق {name}"),
    },
    "gtask_deadline": {
        "en": ("The deadline changed: {ref}", "New deadline {name}"),
        "ar": ("تغيّر الموعد النهائي: {ref}", "الموعد الجديد {name}"),
    },
    "gtask_done": {
        "en": ("{actor} finished: {ref}", "On time"),
        "ar": ("أنجز {actor} المهمة: {ref}", "ضمن الموعد"),
    },
    "gtask_done_late": {
        "en": ("{actor} finished, after the deadline: {ref}", "Late"),
        "ar": ("أنجز {actor} المهمة بعد الموعد النهائي: {ref}", "متأخرة"),
    },
    "gtask_overdue": {
        "en": ("Your task is overdue: {ref}", "It was due {name}"),
        "ar": ("مهمتك متأخرة: {ref}", "كان موعدها {name}"),
    },
    "gtask_overdue_given": {
        "en": ("A task you gave is overdue: {ref}", "{name}"),
        "ar": ("مهمة أسندتها متأخرة: {ref}", "{name}"),
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
