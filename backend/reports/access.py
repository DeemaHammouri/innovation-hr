"""Who can open which report. Reports are read-only views over data other modules own; they add no tables."""
from core.roles import CEO, COMMERCIAL_HEAD, HR_HEAD, MARKETING_USER, OPERATION_HEAD, role_key

SECTIONS = {
    "funnel": (CEO, COMMERCIAL_HEAD, MARKETING_USER),
    "revenue": (CEO, COMMERCIAL_HEAD),
    "forecast": (CEO, COMMERCIAL_HEAD),
    "operations": (CEO, OPERATION_HEAD),
    "hr": (CEO, HR_HEAD),
}


def can_open(user, section):
    return role_key(user) in SECTIONS.get(section, ())


def sections_for(user):
    return [s for s in SECTIONS if can_open(user, s)]
