from core.mywork import daily_job

from . import services


@daily_job("payments_daily")
def run(today=None):
    return services.overdue_reminders(today)
