"""Everything that sends notifications on a clock, in one place. Safe to run as often as you like: each notification has a dedupe key,
so a second run sends nothing new."""


def process():
    from appointments import reminders as appointment_reminders
    from leads import reminders as lead_reminders

    from . import urgent

    counts = {"leads": lead_reminders.run(), "appointments": appointment_reminders.run(), "urgent": urgent.run()}
    counts["total"] = sum(counts.values())
    return counts
