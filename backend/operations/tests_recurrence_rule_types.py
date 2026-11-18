"""P31 on the database: the rule types of the brief create the right tasks on the right dates, once each, and the API validates them.
Weekend is Friday and Saturday. Dates are worked out from the calendar (see tests_recurrence_dayrules for the pure rules)."""
from datetime import date
from unittest import mock

from django.db import IntegrityError, transaction

from lookups.models import Holiday
from operations import services
from operations.models import RecurringTask, TaskInstance
from operations.tests import OCase


def at(day):
    return mock.patch("django.utils.timezone.localdate", return_value=day)


class RuleTypesGenerateTheRightTasks(OCase):
    def rule(self, start, frequency="monthly", **over):
        return RecurringTask.objects.create(
            client=self.mkclient(), title="Rule", frequency=frequency, start_date=start, next_due=start, assignee=self.omem, created_by=self.ohead, **over,
        )

    def made(self, task):
        return list(TaskInstance.objects.filter(recurring=task).order_by("due_date").values_list("due_date", "period"))

    def test_last_working_day_of_each_month(self):
        task = self.rule(date(2026, 10, 1), day_rule="last_workday")
        self.assertEqual(services.generate_due(date(2026, 12, 31)), 3)
        self.assertEqual(self.made(task), [(date(2026, 10, 29), date(2026, 10, 1)), (date(2026, 11, 30), date(2026, 11, 1)), (date(2026, 12, 31), date(2026, 12, 1))])

    def test_first_working_day_skips_a_public_holiday(self):
        Holiday.objects.create(date=date(2026, 12, 1), name_en="Test holiday", name_ar="عطلة")
        task = self.rule(date(2026, 11, 2), day_rule="first_workday")  # November's first working day has passed: the rule begins in December
        self.assertEqual(services.generate_due(date(2026, 12, 1)), 0)  # the 1st is a holiday
        self.assertEqual(services.generate_due(date(2026, 12, 2)), 1)
        self.assertEqual(self.made(task), [(date(2026, 12, 2), date(2026, 12, 1))])

    def test_a_holiday_added_later_moves_only_tasks_not_yet_created(self):
        task = self.rule(date(2026, 11, 2), day_rule="first_workday")
        services.generate_due(date(2026, 12, 2))
        Holiday.objects.create(date=date(2027, 1, 3), name_en="Late holiday", name_ar="عطلة")  # Jan 3 2027 was going to be January's first working day
        services.generate_due(date(2027, 1, 4))
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 12, 1), date(2027, 1, 4)])

    def test_second_tuesday_of_the_month(self):
        task = self.rule(date(2026, 11, 1), day_rule="nth_weekday", nth=2, weekday=1)
        self.assertEqual(services.generate_due(date(2027, 1, 31)), 3)
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 10), date(2026, 12, 8), date(2027, 1, 12)])

    def test_last_thursday_of_each_quarter(self):
        task = self.rule(date(2026, 11, 1), frequency="quarterly", day_rule="nth_weekday", nth=-1, weekday=3)
        services.generate_due(date(2027, 5, 31))
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 26), date(2027, 2, 25), date(2027, 5, 27)])

    def test_every_working_day_makes_no_task_for_friday_or_saturday(self):
        task = self.rule(date(2026, 11, 18), frequency="workdays")  # a Wednesday
        self.assertEqual(services.generate_due(date(2026, 11, 24)), 5)
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 22), date(2026, 11, 23), date(2026, 11, 24)])

    def test_every_working_day_skips_a_public_holiday(self):
        Holiday.objects.create(date=date(2026, 11, 22), name_en="Test holiday", name_ar="عطلة")
        task = self.rule(date(2026, 11, 18), frequency="workdays")
        services.generate_due(date(2026, 11, 24))
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 23), date(2026, 11, 24)])

    def test_repeating_the_run_never_makes_a_second_task(self):
        task = self.rule(date(2026, 10, 1), day_rule="last_workday")
        services.generate_due(date(2026, 12, 31))
        for _ in range(3):
            self.assertEqual(services.generate_due(date(2026, 12, 31)), 0)
        self.assertEqual(len(self.made(task)), 3)


class WeekendPolicyOnTheDatabase(OCase):
    rule = RuleTypesGenerateTheRightTasks.rule
    made = RuleTypesGenerateTheRightTasks.made

    def test_next_is_the_default_and_moves_to_the_next_working_day(self):
        task = self.rule(date(2026, 11, 20), frequency="weekly")  # Fridays
        self.assertEqual(task.weekend_policy, "next")
        services.generate_due(date(2026, 11, 29))  # the 27th is moved to Sunday the 29th, so nothing is created before that
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 22), date(2026, 11, 29)])

    def test_keep_leaves_the_task_on_the_closed_day(self):
        task = self.rule(date(2026, 11, 20), frequency="weekly", weekend_policy="keep")
        services.generate_due(date(2026, 11, 27))
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 20), date(2026, 11, 27)])

    def test_previous_moves_back_but_never_before_the_start(self):
        task = self.rule(date(2026, 11, 14), frequency="weekly", weekend_policy="previous")  # Saturdays
        services.generate_due(date(2026, 11, 22))
        self.assertEqual([d for d, _ in self.made(task)], [date(2026, 11, 15), date(2026, 11, 19)])  # the first cannot go before the 14th

    def test_skip_makes_no_task_for_a_closed_day_and_moves_on(self):
        task = self.rule(date(2026, 10, 31), weekend_policy="skip")  # monthly from a Saturday
        self.assertEqual(services.generate_due(date(2026, 11, 30)), 1)
        self.assertEqual(self.made(task), [(date(2026, 11, 30), date(2026, 11, 1))])
        task.refresh_from_db()
        self.assertEqual(task.next_due, date(2026, 12, 31))  # the generator moved past the skipped October occurrence

    def test_a_task_moved_into_the_next_month_still_belongs_to_its_own_period(self):
        task = self.rule(date(2026, 10, 31))  # monthly, a Saturday: due Sunday 1 Nov, but it is October's task
        services.generate_due(date(2026, 11, 1))
        self.assertEqual(self.made(task), [(date(2026, 11, 1), date(2026, 10, 1))])


class ValidationAndStorage(OCase):
    def test_the_new_fields_are_stored_and_returned_by_the_api(self):
        with at(date(2026, 6, 1)):
            res = self.recurring(day_rule="nth_weekday", nth=2, weekday=1, weekend_policy="previous", start_date="2026-06-01")
        self.assertEqual(res.status_code, 201, res.data)
        for key, value in (("day_rule", "nth_weekday"), ("nth", 2), ("weekday", 1), ("weekend_policy", "previous"), ("frequency", "monthly")):
            self.assertEqual(res.data[key], value, key)

    def test_a_plain_rule_gets_the_old_behaviour_by_default(self):
        res = self.recurring()
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["day_rule"], res.data["nth"], res.data["weekday"], res.data["weekend_policy"]), ("date", None, None, "next"))

    def test_every_working_day_can_be_created(self):
        self.assertEqual(self.recurring(frequency="workdays").status_code, 201)

    def test_bad_values_are_refused_with_a_clear_field_error(self):
        for body, field in (
            ({"day_rule": "sometimes"}, "day_rule"),
            ({"frequency": "weekly", "day_rule": "first_workday"}, "day_rule"),  # a day of the month means nothing for a weekly rule
            ({"frequency": "workdays", "day_rule": "last_workday"}, "day_rule"),
            ({"day_rule": "nth_weekday", "weekday": 1}, "nth"),
            ({"day_rule": "nth_weekday", "nth": 5, "weekday": 1}, "nth"),
            ({"day_rule": "nth_weekday", "nth": 2}, "weekday"),
            ({"day_rule": "nth_weekday", "nth": 2, "weekday": 7}, "weekday"),
            ({"weekend_policy": "whenever"}, "weekend_policy"),
        ):
            res = self.recurring(**body)
            self.assertEqual(res.status_code, 400, body)
            self.assertIn(field, res.data, body)

    def test_the_database_refuses_an_impossible_combination_even_without_the_api(self):
        client = self.mkclient()
        for over in ({"frequency": "weekly", "day_rule": "first_workday"}, {"day_rule": "nth_weekday"}, {"day_rule": "nth_weekday", "nth": 9, "weekday": 1}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                RecurringTask.objects.create(
                    client=client, title="x", start_date=date(2026, 11, 2), next_due=date(2026, 11, 2), created_by=self.ohead, **{"frequency": "monthly", **over},
                )

    def test_changing_the_day_rule_or_policy_starts_a_new_version_and_touches_no_past_task(self):
        with at(date(2026, 11, 2)):
            res = self.recurring(frequency="weekly", start_date="2026-11-02")
            task = RecurringTask.objects.get(pk=res.data["id"])
            services.generate_due(date(2026, 11, 9))
            old = list(TaskInstance.objects.filter(recurring=task).values_list("pk", "due_date", "rule_version"))
            self.as_user(self.ohead)
            changed = self.client.patch(f"/api/operations/recurring/{task.pk}/", {"weekend_policy": "keep"}, format="json")
            self.assertEqual(changed.status_code, 200, changed.data)
            same = self.client.patch(f"/api/operations/recurring/{task.pk}/", {"weekend_policy": "keep"}, format="json")
            self.assertEqual(same.status_code, 200)
        task.refresh_from_db()
        self.assertEqual((task.version, task.weekend_policy), (2, "keep"))  # one bump, not two: the repeat changed nothing
        self.assertEqual(list(TaskInstance.objects.filter(recurring=task, rule_version=1).values_list("pk", "due_date", "rule_version")), old)

    def test_switching_to_a_day_rule_through_the_api_regenerates_from_today(self):
        with at(date(2026, 11, 2)):
            res = self.recurring(start_date="2026-11-02")
            self.as_user(self.ohead)
            changed = self.client.patch(f"/api/operations/recurring/{res.data['id']}/", {"day_rule": "last_workday"}, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        task = RecurringTask.objects.get(pk=res.data["id"])
        self.assertEqual((task.day_rule, task.version, task.next_due), ("last_workday", 2, date(2026, 11, 30)))
