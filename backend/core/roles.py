"""The eight business roles, derived from department + head/member. Nothing here is stored."""
from accounts.models import ADMINISTRATION, MARKETING, OPERATION

CEO = "ceo"
MARKETING_USER = "marketing"
COMMERCIAL_HEAD = "commercial_head"
COMMERCIAL_MEMBER = "commercial_member"
HR_HEAD = "hr_head"
HR_MEMBER = "hr_member"
OPERATION_HEAD = "operation_head"
OPERATION_MEMBER = "operation_member"

ALL_ROLES = [CEO, MARKETING_USER, COMMERCIAL_HEAD, COMMERCIAL_MEMBER, HR_HEAD, HR_MEMBER, OPERATION_HEAD, OPERATION_MEMBER]


def role_key(user):
    """One of ALL_ROLES, or None for anonymous users and developer superusers without a department."""
    if not user or not user.is_authenticated or not user.department_id:
        return None
    dept = user.department.name
    head = user.role == "head"
    if dept == ADMINISTRATION:
        return CEO if head else None
    if dept == MARKETING:
        return MARKETING_USER
    if dept == "Commercial":
        return COMMERCIAL_HEAD if head else COMMERCIAL_MEMBER
    if dept == "HR":
        return HR_HEAD if head else HR_MEMBER
    if dept == OPERATION:
        return OPERATION_HEAD if head else OPERATION_MEMBER
    return None


def has_role(user, *keys):
    return role_key(user) in keys
