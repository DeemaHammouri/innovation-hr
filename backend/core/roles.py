"""Role keys. The role itself is stored (accounts.Role); this module names the keys and reads the current user's."""
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
    """The key of the user's Role (one of ALL_ROLES, or "super_admin"); None for anonymous users and accounts without a role.
    Use it for labels and identity only. Permission decisions ask for capabilities (accounts.permissions.HasCapability / user.has_capability)."""
    if not user or not user.is_authenticated:
        return None
    return user.role_name


def has_role(user, *keys):
    return role_key(user) in keys
