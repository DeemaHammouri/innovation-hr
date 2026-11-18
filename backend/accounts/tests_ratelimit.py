"""P5: the sign-in counters must be exact under parallel sign-ins, shared between workers, and end with their window."""
import threading
from datetime import timedelta

from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from . import ratelimit
from .models import LoginFailure


class ParallelCountTests(TransactionTestCase):
    """Real threads on real connections (a TestCase would wrap them all in one transaction)."""

    def test_forty_parallel_failures_count_forty_for_the_account_and_the_address(self):
        errors = []

        def fail():
            try:
                ratelimit.record_failure("a@x.com", "1.1.1.1")
            except Exception as exc:  # noqa: BLE001 - reported below with the count
                errors.append(repr(exc))
            finally:
                connections.close_all()

        threads = [threading.Thread(target=fail) for _ in range(40)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(errors, [])
        counts = dict(LoginFailure.objects.values_list("key", "count"))
        self.assertEqual(counts, {"id:a@x.com": 40, "ip:1.1.1.1": 40})

    def test_the_first_failures_of_a_new_key_race_without_losing_one(self):
        """The create-or-increment path: all threads start together on a key that does not exist yet."""
        start = threading.Barrier(12)

        def fail():
            start.wait()
            try:
                ratelimit.record_failure("new@x.com", "2.2.2.2")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=fail) for _ in range(12)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(LoginFailure.objects.get(key="id:new@x.com").count, 12)
        self.assertEqual(LoginFailure.objects.filter(key="id:new@x.com").count(), 1)


class LockoutBehaviourTests(TestCase):
    def test_blocks_at_the_limit_and_not_before(self):
        for _ in range(4):
            ratelimit.record_failure("b@x.com", "3.3.3.3")
        self.assertFalse(ratelimit.blocked("b@x.com", "3.3.3.3"))
        ratelimit.record_failure("b@x.com", "3.3.3.3")
        self.assertTrue(ratelimit.blocked("b@x.com", "3.3.3.3"))
        self.assertFalse(ratelimit.blocked("other@x.com", "9.9.9.9"))  # nobody else is affected

    @override_settings(LOGIN_MAX_FAILS_PER_IP=3)
    def test_the_address_limit_blocks_other_accounts_from_that_address_only(self):
        for i in range(3):
            ratelimit.record_failure(f"n{i}@x.com", "4.4.4.4")
        self.assertTrue(ratelimit.blocked("fresh@x.com", "4.4.4.4"))
        self.assertFalse(ratelimit.blocked("fresh@x.com", "4.4.4.5"))

    def test_the_window_ends_and_the_counter_starts_over(self):
        for _ in range(5):
            ratelimit.record_failure("c@x.com", "5.5.5.5")
        self.assertTrue(ratelimit.blocked("c@x.com", "5.5.5.5"))
        LoginFailure.objects.update(expires_at=timezone.now() - timedelta(seconds=1))  # five minutes have passed
        self.assertFalse(ratelimit.blocked("c@x.com", "5.5.5.5"))
        ratelimit.record_failure("c@x.com", "5.5.5.5")
        self.assertEqual(LoginFailure.objects.get(key="id:c@x.com").count, 1)  # a fresh window, not 6
        self.assertEqual(LoginFailure.objects.filter(key="ip:5.5.5.5").count(), 1)  # and the stale rows are gone

    def test_the_window_does_not_slide(self):
        ratelimit.record_failure("d@x.com", "6.6.6.6")
        first = LoginFailure.objects.get(key="id:d@x.com").expires_at
        ratelimit.record_failure("d@x.com", "6.6.6.6")
        self.assertEqual(LoginFailure.objects.get(key="id:d@x.com").expires_at, first)

    def test_clear_resets_the_account_but_not_the_address(self):
        for _ in range(5):
            ratelimit.record_failure("e@x.com", "7.7.7.7")
        ratelimit.clear("e@x.com")
        self.assertFalse(ratelimit.blocked("e@x.com", "8.8.8.8"))
        self.assertEqual(LoginFailure.objects.get(key="ip:7.7.7.7").count, 5)

    def test_a_long_identifier_cannot_overflow_the_key(self):
        ratelimit.record_failure("x" * 5000, "1.2.3.4")
        self.assertTrue(ratelimit.blocked("x" * 5000, "9.9.9.9") is False)
        self.assertLessEqual(max(len(k) for k in LoginFailure.objects.values_list("key", flat=True)), 300)
