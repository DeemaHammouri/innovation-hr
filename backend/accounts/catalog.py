"""The organisation as data: departments, the nine roles and every capability with the roles that hold it by default.

This file is only the SEED. After `seed_organization` has run, the database is the source of truth and the code reads capabilities from
it, so granting one more capability to a role is a data change, never a view change. The grants below reproduce exactly who could do
what before capabilities existed (the permission matrix tests prove it). Super Admin always holds every capability.
"""
ADMINISTRATION = "Administration"
MARKETING = "Marketing"
COMMERCIAL = "Commercial"
HR = "HR"
OPERATION = "Operation"
DEPARTMENT_NAMES = [ADMINISTRATION, MARKETING, COMMERCIAL, HR, OPERATION]

SUPER_ADMIN = "super_admin"

# key: (department or None, is_head, English name, Arabic name)
ROLES = {
    "ceo": (ADMINISTRATION, True, "CEO", "المدير التنفيذي"),
    "marketing": (MARKETING, False, "Marketing", "التسويق"),
    "commercial_head": (COMMERCIAL, True, "Commercial head", "رئيس المبيعات"),
    "commercial_member": (COMMERCIAL, False, "Commercial member", "عضو المبيعات"),
    "hr_head": (HR, True, "HR head", "رئيس الموارد البشرية"),
    "hr_member": (HR, False, "HR member", "عضو الموارد البشرية"),
    "operation_head": (OPERATION, True, "Operation head", "رئيس العمليات"),
    "operation_member": (OPERATION, False, "Operation member", "عضو العمليات"),
    SUPER_ADMIN: (None, False, "Super Admin", "مدير النظام"),
}

_CEO, _MKT = "ceo", "marketing"
_CH, _CM = "commercial_head", "commercial_member"
_HH, _HM = "hr_head", "hr_member"
_OH, _OM = "operation_head", "operation_member"

# code: (description, default roles)
CAPABILITIES = {
    # Leads
    "lead.access": ("Open the leads area", [_CEO, _MKT, _CH, _CM]),
    "lead.view_all": ("See every lead", [_CEO, _CH]),
    "lead.view_assigned": ("See leads assigned to you", [_CM]),
    "lead.view_created": ("See leads you added", [_MKT]),
    "lead.manage": ("Assign, reopen, archive and restore any lead; work the whole pipeline", [_CH]),
    "lead.work_assigned": ("Log contacts and outcomes on leads assigned to you", [_CM]),
    "lead.edit_created": ("Edit and archive your own untouched leads", [_MKT]),
    # Quotations
    "quotation.access": ("Open quotations", [_CEO, _CH, _CM, _HH, _HM]),
    "quotation.view_all": ("See every quotation", [_CEO, _CH, _HH, _HM]),
    "quotation.view_assigned": ("See quotations on leads assigned to you", [_CM]),
    "quotation.prepare": ("Prepare quotations", [_HH, _HM]),
    "quotation.sign": ("Sign or return a quotation", [_CH]),
    # Contracts
    "contract.access": ("Open contracts", [_CEO, _CH, _CM, _HH, _HM, _OH, _OM]),
    "contract.view_all": ("See every contract", [_CEO, _CH, _HH, _HM]),
    "contract.view_assigned": ("See contracts on leads assigned to you", [_CM]),
    "contract.view_handed_over": ("See contracts once handed over", [_OH, _OM]),
    "contract.draft": ("Draft and hand over contracts", [_HH, _HM]),
    "contract.sign": ("Review and sign contracts", [_CEO]),
    # Operation and clients
    "operation.access": ("Open the Operation area", [_CEO, _CH, _CM, _OH, _OM]),
    "operation.work": ("Work on clients, checklists and tasks", [_OH, _OM]),
    "operation.manage": ("Manage the Operation team's work", [_OH]),
    "operation.view_all_clients": ("See every client in Operation", [_CEO, _OH, _OM]),
    "operation.view_own_deals": ("See clients from your own deals", [_CH, _CM]),
    "client.manage": ("Create and edit clients", [_CEO, _OH]),
    # Payments
    "payment.manage": ("Schedule and record payments", [_CH]),
    "payment.view": ("See payments", [_CEO, _CH]),
    # Reports
    "report.funnel": ("Sales funnel report", [_CEO, _CH, _MKT]),
    "report.revenue": ("Revenue report", [_CEO, _CH]),
    "report.forecast": ("Forecast report", [_CEO, _CH]),
    "report.operations": ("Operations report", [_CEO, _OH]),
    "report.hr": ("HR report", [_CEO, _HH]),
    # HR
    "hr.staff": ("HR work: people, leave and attendance administration", [_HH, _HM]),
    "hr.manage": ("Decide leave and run payroll as the HR head", [_HH]),
    "hr.attendance_all": ("See everyone's attendance and leave", [_CEO, _HH, _HM]),
    "hr.leave_request": ("Request leave", [_MKT, _CH, _CM, _HH, _HM, _OH, _OM]),
    "hr.leave_decide_hr_head": ("Decide the HR head's leave", [_CEO]),
    "hr.payroll_view": ("See salaries and payroll", [_CEO, _HH]),
    "hr.payroll_approve": ("Approve and reopen payroll runs", [_CEO]),
    # Administration
    "settings.manage": ("Change company settings and lookups", [_CEO]),
    "user.manage": ("Create and manage user accounts", [_CEO]),
}
