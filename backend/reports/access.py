"""Who can open which report. Reports are read-only views over data other modules own; they add no tables.
Each section is one capability, report.<section>."""

SECTIONS = ("funnel", "revenue", "forecast", "operations", "hr")


def can_open(user, section):
    return section in SECTIONS and user.has_capability(f"report.{section}")


def sections_for(user):
    return [s for s in SECTIONS if can_open(user, s)]
