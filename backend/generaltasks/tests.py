"""Objective 22: general tasks. Who may give a task to whom, who sees it, only the assignee finishes it, done late, uploads, alerts and counters."""
from datetime import timedelta
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import Role, User
from audit.models import AuditEntry
from core import mywork
from core.access import content_type_for
from core.roles import ALL_ROLES
from core.testing import RoleCase
from files.models import Attachment
from generaltasks import reminders
from generaltasks.models import GeneralTask
from notifications.models import Notification

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
STAFF = [r for r in ALL_ROLES]


class GCase(RoleCase):
    def setUp(self):
        super().setUp()
        u = self.users
        self.ceo, self.chead, self.cmem, self.hhead, self.hmem, self.ohead, self.omem, self.mkt = (
            u["ceo"], u["commercial_head"], u["commercial_member"], u["hr_head"], u["hr_member"], u["operation_head"], u["operation_member"], u["marketing"],
        )
        self.omem2 = self.make_user("omem2@x.com", "Operation", "member")
        self.today = timezone.localdate()

    def give(self, giver, assignee, title="Prepare the report", days=3, **extra):
        self.as_user(giver)
        body = {"title": title, "assignee": assignee.pk, "deadline": (self.today + timedelta(days=days)).isoformat(), **extra}
        return self.client.post("/api/tasks/", body, format="json")

    def made(self, giver=None, assignee=None, days=3, title="Prepare the report"):
        res = self.give(giver or self.ceo, assignee or self.omem, title=title, days=days)
        self.assertEqual(res.status_code, 201, res.data)
        return GeneralTask.objects.get(pk=res.data["id"])

    def call(self, user, method, path, body=None):
        self.as_user(user)
        return getattr(self.client, method)(path, body or {}, format="json")


class CapabilityTests(GCase):
    def test_the_new_capabilities_are_held_by_the_right_roles(self):
        def caps(key):
            return set(Role.objects.get(key=key).capabilities.filter(code__startswith="gtask.").values_list("code", flat=True))

        self.assertEqual(caps("ceo"), {"gtask.access", "gtask.assign_any"})
        for head in ("commercial_head", "hr_head", "operation_head"):
            self.assertEqual(caps(head), {"gtask.access", "gtask.assign_team"}, head)
        for member in ("marketing", "commercial_member", "hr_member", "operation_member"):
            self.assertEqual(caps(member), {"gtask.access"}, member)
        self.assertEqual(caps("client"), set())
        self.assertEqual(caps("super_admin"), {"gtask.access", "gtask.assign_team", "gtask.assign_any"})

    def test_a_client_account_cannot_open_tasks(self):
        client_user = User.objects.create_user(email="c@x.com", password="x-pass-123", full_name="C", role_ref=Role.objects.get(key="client"))
        self.client.force_authenticate(client_user)
        for path in ("/api/tasks/", "/api/tasks/counters/", "/api/tasks/assignees/"):
            self.assertEqual(self.client.get(path).status_code, 403, path)

    def test_everyone_signed_in_is_needed(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/tasks/").status_code, 401)


class GivingTests(GCase):
    def test_the_ceo_can_give_a_task_to_anyone_who_works_here(self):
        for key in STAFF:
            if key == "ceo":
                continue
            res = self.give(self.ceo, self.users[key], title=f"For {key}")
            self.assertEqual(res.status_code, 201, (key, res.data))
            self.assertEqual((res.data["assignee"], res.data["assigned_by"], res.data["status"]), (self.users[key].pk, self.ceo.pk, "open"))

    def test_a_head_gives_tasks_inside_their_own_department_only(self):
        self.assertEqual(self.give(self.ohead, self.omem).status_code, 201)
        self.assertEqual(self.give(self.ohead, self.ohead).status_code, 201)  # to themselves
        for other in (self.cmem, self.hmem, self.mkt, self.ceo, self.chead):
            res = self.give(self.ohead, other)
            self.assertEqual((res.status_code, "assignee" in res.data), (400, True), other.email)
        self.assertEqual(GeneralTask.objects.count(), 2)

    def test_a_member_cannot_give_a_task_to_anyone(self):
        for key in ("marketing", "commercial_member", "hr_member", "operation_member"):
            res = self.give(self.users[key], self.users[key])
            self.assertEqual(res.status_code, 403, key)
        self.assertFalse(GeneralTask.objects.exists())

    def test_nobody_can_give_a_task_to_an_inactive_person_or_a_missing_one(self):
        gone = self.make_user("gone@x.com", "Operation", "member")
        User.objects.filter(pk=gone.pk).update(is_active=False)
        self.assertEqual(self.give(self.ceo, gone).status_code, 400)
        self.as_user(self.ceo)
        res = self.client.post("/api/tasks/", {"title": "x", "assignee": 99999, "deadline": self.today.isoformat()}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_title_deadline_and_assignee_are_checked(self):
        self.as_user(self.ceo)
        ok = {"title": "A", "assignee": self.omem.pk, "deadline": self.today.isoformat()}
        for bad, field in (({"title": "  "}, "title"), ({"deadline": ""}, "deadline"), ({"deadline": "not a date"}, "deadline"), ({"deadline": (self.today - timedelta(days=1)).isoformat()}, "deadline"), ({"assignee": None}, "assignee")):
            res = self.client.post("/api/tasks/", {**ok, **bad}, format="json")
            self.assertEqual((res.status_code, field in res.data), (400, True), bad)
        self.assertEqual(self.client.post("/api/tasks/", ok, format="json").status_code, 201)  # today is a valid deadline

    def test_the_picker_lists_only_the_people_the_person_may_choose(self):
        self.as_user(self.ceo)
        ceo_list = {r["id"] for r in self.client.get("/api/tasks/assignees/").data}
        self.assertEqual(ceo_list, {u.pk for u in User.objects.filter(is_active=True, role_ref__capabilities__code="gtask.access").distinct()})
        self.as_user(self.ohead)
        head_list = {r["id"] for r in self.client.get("/api/tasks/assignees/").data}
        self.assertEqual(head_list, {self.ohead.pk, self.omem.pk, self.omem2.pk})
        self.assertNotIn(self.cmem.pk, head_list)
        self.as_user(self.omem)
        self.assertEqual(self.client.get("/api/tasks/assignees/").data, [])

    def test_giving_a_task_notifies_the_assignee_and_writes_the_history(self):
        t = self.made(self.ohead, self.omem)
        note = Notification.objects.get(user=self.omem, kind="gtask_assigned")
        self.assertIn(self.ohead.full_name, note.title)
        self.assertEqual(note.link, f"/tasks?open={t.pk}")
        entry = AuditEntry.objects.get(content_type=content_type_for(GeneralTask), object_id=t.pk)
        self.assertEqual((entry.action, entry.actor_id), ("gtask_created", self.ohead.pk))


class VisibilityTests(GCase):
    def test_who_sees_which_task(self):
        mine = self.made(self.ohead, self.omem, title="Operation task")
        other = self.made(self.chead, self.cmem, title="Commercial task")
        seen = lambda user, path="/api/tasks/?view=team": {r["title"] for r in self.call(user, "get", path).data["results"]}
        self.assertEqual(seen(self.ceo), {"Operation task", "Commercial task"})
        self.assertEqual(seen(self.ohead), {"Operation task"})
        self.assertEqual(seen(self.chead), {"Commercial task"})
        self.assertEqual(seen(self.omem, "/api/tasks/"), {"Operation task"})
        self.assertEqual(seen(self.hmem, "/api/tasks/"), set())
        self.assertEqual(self.call(self.omem, "get", f"/api/tasks/{mine.pk}/").status_code, 200)
        for user in (self.hmem, self.cmem, self.chead, self.hhead, self.mkt):
            self.assertEqual(self.call(user, "get", f"/api/tasks/{mine.pk}/").status_code, 404, user.email)
        self.assertEqual(self.call(self.ohead, "get", f"/api/tasks/{other.pk}/").status_code, 404)

    def test_a_member_never_sees_a_colleagues_task_even_asking_for_the_team_view(self):
        t = self.made(self.ohead, self.omem)
        colleague = self.omem2
        res = self.call(colleague, "get", "/api/tasks/?view=team")
        self.assertEqual(res.data["results"], [])
        self.assertEqual(self.call(colleague, "get", f"/api/tasks/{t.pk}/").status_code, 404)

    def test_the_views_mine_given_and_team(self):
        a = self.made(self.ceo, self.ohead, title="To the head")
        b = self.made(self.ohead, self.omem, title="To the member")
        titles = lambda user, view: {r["title"] for r in self.call(user, "get", f"/api/tasks/?view={view}").data["results"]}
        self.assertEqual(titles(self.ohead, "mine"), {"To the head"})
        self.assertEqual(titles(self.ohead, "given"), {"To the member"})
        self.assertEqual(titles(self.ohead, "team"), {"To the head", "To the member"})
        self.assertEqual(titles(self.omem, "given"), set())
        self.assertTrue(a and b)

    def test_filters(self):
        late = self.made(days=0, title="Today")
        GeneralTask.objects.filter(pk=late.pk).update(deadline=self.today - timedelta(days=2))
        done = self.made(title="Finished")
        self.call(self.omem, "post", f"/api/tasks/{done.pk}/done/")
        titles = lambda q: {r["title"] for r in self.call(self.ceo, "get", f"/api/tasks/?view=team&{q}").data["results"]}
        self.assertEqual(titles("status=open"), {"Today"})
        self.assertEqual(titles("status=done"), {"Finished"})
        self.assertEqual(titles("overdue=1"), {"Today"})
        self.assertEqual(titles(f"assignee={self.omem.pk}"), {"Today", "Finished"})
        self.assertEqual(titles(f"assignee={self.hmem.pk}"), set())


class DoneTests(GCase):
    def test_only_the_assignee_can_mark_a_task_as_done(self):
        t = self.made(self.ceo, self.omem)
        for user in (self.ceo, self.ohead, self.chead, self.hmem):
            res = self.call(user, "post", f"/api/tasks/{t.pk}/done/")
            self.assertIn(res.status_code, (403, 404), user.email)
        t.refresh_from_db()
        self.assertEqual(t.status, "open")
        res = self.call(self.omem, "post", f"/api/tasks/{t.pk}/done/")
        self.assertEqual((res.status_code, res.data["status"], res.data["done_late"]), (200, "done", False))

    def test_the_head_who_gave_the_task_still_cannot_finish_it_for_the_person(self):
        t = self.made(self.ohead, self.omem)
        res = self.call(self.ohead, "post", f"/api/tasks/{t.pk}/done/")
        self.assertEqual(res.status_code, 403)
        self.assertIn("Only the person", res.data["detail"])

    def test_done_on_the_deadline_day_is_on_time_and_after_it_is_late(self):
        on_time = self.made(days=0, title="Same day")
        self.assertFalse(self.call(self.omem, "post", f"/api/tasks/{on_time.pk}/done/").data["done_late"])
        late = self.made(days=1, title="Next day")
        with mock.patch("generaltasks.services.timezone.now", return_value=timezone.now() + timedelta(days=2)):
            res = self.call(self.omem, "post", f"/api/tasks/{late.pk}/done/")
        self.assertEqual((res.status_code, res.data["done_late"]), (200, True))
        self.assertEqual(AuditEntry.objects.filter(content_type=content_type_for(GeneralTask), object_id=late.pk, action="gtask_done_late").count(), 1)
        self.assertEqual(AuditEntry.objects.filter(content_type=content_type_for(GeneralTask), object_id=on_time.pk, action="gtask_done").count(), 1)

    def test_done_twice_is_refused_and_a_done_task_cannot_be_edited(self):
        t = self.made(self.ceo, self.omem)
        self.assertEqual(self.call(self.omem, "post", f"/api/tasks/{t.pk}/done/").status_code, 200)
        self.assertEqual(self.call(self.omem, "post", f"/api/tasks/{t.pk}/done/").status_code, 400)
        self.assertEqual(self.call(self.ceo, "patch", f"/api/tasks/{t.pk}/", {"title": "Changed"}).status_code, 400)

    def test_the_database_refuses_a_done_task_without_a_time_and_a_blank_title(self):
        t = self.made()
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeneralTask.objects.filter(pk=t.pk).update(status="done")
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeneralTask.objects.filter(pk=t.pk).update(title="")
        with self.assertRaises(IntegrityError), transaction.atomic():
            GeneralTask.objects.filter(pk=t.pk).update(done_late=True)  # an open task cannot be "late"

    def test_the_giver_is_told_when_it_is_done_and_whether_it_was_late(self):
        t = self.made(self.ohead, self.omem, days=1)
        with mock.patch("generaltasks.services.timezone.now", return_value=timezone.now() + timedelta(days=3)):
            self.call(self.omem, "post", f"/api/tasks/{t.pk}/done/")
        note = Notification.objects.get(user=self.ohead, kind="gtask_done_late")
        self.assertIn("after the deadline", note.title)
        own = self.made(self.ohead, self.ohead, title="Mine")
        self.call(self.ohead, "post", f"/api/tasks/{own.pk}/done/")
        self.assertFalse(Notification.objects.filter(user=self.ohead, kind="gtask_done").exists())  # nobody is told about their own


class EditingTests(GCase):
    def test_the_giver_and_the_team_head_can_edit_an_open_task_and_nobody_else(self):
        t = self.made(self.ohead, self.omem)
        later = (self.today + timedelta(days=9)).isoformat()
        self.assertEqual(self.call(self.omem, "patch", f"/api/tasks/{t.pk}/", {"deadline": later}).status_code, 403)
        for user in (self.chead, self.hmem):
            self.assertEqual(self.call(user, "patch", f"/api/tasks/{t.pk}/", {"deadline": later}).status_code, 404, user.email)
        res = self.call(self.ohead, "patch", f"/api/tasks/{t.pk}/", {"title": "New title", "deadline": later})
        self.assertEqual((res.status_code, res.data["title"], res.data["deadline"]), (200, "New title", later))
        self.assertEqual(self.call(self.ceo, "patch", f"/api/tasks/{t.pk}/", {"description": "More detail"}).status_code, 200)

    def test_a_deadline_change_is_logged_starts_a_new_alert_round_and_tells_the_assignee(self):
        t = self.made(self.ohead, self.omem)
        later = self.today + timedelta(days=9)
        self.call(self.ohead, "patch", f"/api/tasks/{t.pk}/", {"deadline": later.isoformat()})
        t.refresh_from_db()
        self.assertEqual(t.alert_round, 1)
        e = AuditEntry.objects.get(content_type=content_type_for(GeneralTask), object_id=t.pk, action="gtask_deadline_changed")
        self.assertEqual((e.from_value, e.to_value), ((self.today + timedelta(days=3)).isoformat(), later.isoformat()))
        self.assertTrue(Notification.objects.filter(user=self.omem, kind="gtask_deadline").exists())
        self.call(self.ohead, "patch", f"/api/tasks/{t.pk}/", {"deadline": later.isoformat()})  # the same date again changes nothing
        t.refresh_from_db()
        self.assertEqual(t.alert_round, 1)

    def test_a_past_deadline_and_a_blank_title_are_refused_on_edit(self):
        t = self.made()
        past = (self.today - timedelta(days=1)).isoformat()
        for body, field in (({"deadline": past}, "deadline"), ({"title": " "}, "title"), ({"deadline": "x"}, "deadline")):
            res = self.call(self.ceo, "patch", f"/api/tasks/{t.pk}/", body)
            self.assertEqual((res.status_code, field in res.data), (400, True), body)

    def test_reassigning_follows_the_same_rule_as_giving(self):
        t = self.made(self.ohead, self.omem)
        colleague = self.omem2
        res = self.call(self.ohead, "patch", f"/api/tasks/{t.pk}/", {"assignee": colleague.pk})
        self.assertEqual((res.status_code, res.data["assignee"]), (200, colleague.pk))
        self.assertTrue(Notification.objects.filter(user=colleague, kind="gtask_assigned").exists())
        self.assertEqual(self.call(self.ohead, "patch", f"/api/tasks/{t.pk}/", {"assignee": self.cmem.pk}).status_code, 400)
        self.assertEqual(self.call(self.ceo, "patch", f"/api/tasks/{t.pk}/", {"assignee": self.cmem.pk}).status_code, 200)
        self.assertEqual(self.call(self.omem, "get", f"/api/tasks/{t.pk}/").status_code, 404)  # no longer theirs

    def test_the_flags_the_screen_uses(self):
        t = self.made(self.ohead, self.omem)
        row = lambda user: self.call(user, "get", f"/api/tasks/{t.pk}/").data
        self.assertEqual((row(self.omem)["can_done"], row(self.omem)["can_edit"], row(self.omem)["can_attach"]), (True, False, True))
        self.assertEqual((row(self.ohead)["can_done"], row(self.ohead)["can_edit"], row(self.ohead)["can_attach"]), (False, True, True))
        self.assertEqual((row(self.ceo)["can_done"], row(self.ceo)["can_edit"]), (False, True))


class AlertTests(GCase):
    def test_one_overdue_alert_per_deadline_to_the_assignee_and_the_giver(self):
        t = self.made(self.ohead, self.omem, days=1)
        day = self.today + timedelta(days=2)
        self.assertEqual(reminders.overdue_alerts(self.today + timedelta(days=1)), 0)  # due today is not overdue yet
        self.assertEqual(reminders.overdue_alerts(day), 2)
        self.assertEqual(reminders.overdue_alerts(day), 0)  # repeating the job sends nothing
        self.assertEqual(reminders.overdue_alerts(day + timedelta(days=5)), 0)  # and one alert only, however late it gets
        self.assertTrue(Notification.objects.filter(user=self.omem, kind="gtask_overdue").exists())
        self.assertTrue(Notification.objects.filter(user=self.ohead, kind="gtask_overdue_given").exists())
        self.assertTrue(t)

    def test_changing_the_deadline_re_arms_the_alert(self):
        t = self.made(self.ohead, self.omem, days=1)
        self.assertEqual(reminders.overdue_alerts(self.today + timedelta(days=2)), 2)
        later = self.today + timedelta(days=10)
        self.call(self.ohead, "patch", f"/api/tasks/{t.pk}/", {"deadline": later.isoformat()})
        self.assertEqual(reminders.overdue_alerts(self.today + timedelta(days=5)), 0)  # not overdue under the new deadline
        self.assertEqual(reminders.overdue_alerts(later + timedelta(days=1)), 2)  # overdue again: a new alert
        self.assertEqual(reminders.overdue_alerts(later + timedelta(days=1)), 0)
        self.assertEqual(Notification.objects.filter(user=self.omem, kind="gtask_overdue").count(), 2)

    def test_a_finished_task_is_never_alerted_and_a_task_given_to_oneself_alerts_once(self):
        done = self.made(days=1)
        self.call(self.omem, "post", f"/api/tasks/{done.pk}/done/")
        own = self.made(self.ohead, self.ohead, days=1, title="Mine")
        self.assertEqual(reminders.overdue_alerts(self.today + timedelta(days=3)), 1)
        self.assertEqual(Notification.objects.filter(kind__startswith="gtask_overdue").count(), 1)
        self.assertTrue(own)

    def test_the_command_for_the_scheduler_sends_once_and_is_safe_to_repeat(self):
        from io import StringIO

        from django.core.management import call_command

        t = self.made(self.ohead, self.omem, days=1)
        GeneralTask.objects.filter(pk=t.pk).update(deadline=self.today - timedelta(days=1))
        out = StringIO()
        call_command("general_task_alerts", stdout=out)
        call_command("general_task_alerts", stdout=out)
        self.assertEqual(out.getvalue().splitlines(), ["Task alerts sent: 2.", "Task alerts sent: 0."])

    def test_the_daily_job_is_registered_and_idempotent(self):
        self.made(days=1)
        job = dict(mywork.daily_jobs())["general_tasks_daily"]
        day = self.today + timedelta(days=2)
        self.assertEqual((job(day), job(day)), (2, 0))


class UploadTests(GCase):
    def up(self, user, task, name, content, category=""):
        self.as_user(user)
        return self.client.post(f"/api/files/?target=gtask:{task.pk}", {"file": SimpleUploadedFile(name, content), "category": category}, format="multipart")

    def test_a_real_pdf_is_accepted_and_the_bytes_decide_not_the_name(self):
        t = self.made(self.ohead, self.omem)
        self.assertEqual(self.up(self.omem, t, "report.pdf", PDF).status_code, 201)
        for name, body in (("report.pdf", b"MZ\x90\x00 this is a program"), ("photo.png", PDF), ("sheet.xlsx", b"%PDF-1.4 not a zip"), ("note.pdf", b"")):
            res = self.up(self.omem, t, name, body)
            self.assertEqual(res.status_code, 400, name)
            self.assertIn("file", res.data)
        self.assertEqual(Attachment.objects.filter(content_type=content_type_for(GeneralTask), object_id=t.pk).count(), 1)

    def test_other_extensions_are_refused_even_with_pdf_bytes(self):
        t = self.made()
        for name in ("run.exe", "script.js", "page.html", "archive.zip", "noextension"):
            self.assertEqual(self.up(self.omem, t, name, PDF).status_code, 400, name)

    def test_a_double_extension_and_a_path_in_the_name_are_neutralised(self):
        t = self.made()
        self.assertEqual(self.up(self.omem, t, "report.pdf.exe", PDF).status_code, 400)
        res = self.up(self.omem, t, "../../etc/passwd.pdf", PDF)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Attachment.objects.get(pk=res.data["id"]).original_name, "passwd.pdf")

    def test_an_oversized_file_is_refused(self):
        t = self.made()
        res = self.up(self.omem, t, "big.pdf", PDF + b"0" * (10 * 1024 * 1024))
        self.assertEqual(res.status_code, 400)

    def test_only_people_who_may_see_the_task_can_add_or_read_files(self):
        t = self.made(self.ohead, self.omem)
        self.assertEqual(self.up(self.ohead, t, "a.pdf", PDF).status_code, 201)
        self.assertEqual(self.up(self.ceo, t, "b.pdf", PDF).status_code, 201)
        for user in (self.cmem, self.hmem, self.chead):
            self.assertEqual(self.up(user, t, "x.pdf", PDF).status_code, 404, user.email)
            self.as_user(user)
            self.assertEqual(self.client.get(f"/api/files/?target=gtask:{t.pk}").status_code, 404, user.email)
        self.as_user(self.omem)
        self.assertEqual(self.client.get(f"/api/files/?target=gtask:{t.pk}").data["count"], 2)

    def test_a_finished_task_takes_no_more_files(self):
        t = self.made()
        self.assertEqual(self.up(self.omem, t, "a.pdf", PDF).status_code, 201)
        self.call(self.omem, "post", f"/api/tasks/{t.pk}/done/")
        res = self.up(self.omem, t, "b.pdf", PDF)
        self.assertIn(res.status_code, (400, 403))
        self.assertEqual(Attachment.objects.filter(content_type=content_type_for(GeneralTask), object_id=t.pk).count(), 1)

    def test_the_task_history_is_readable_only_by_those_who_see_the_task(self):
        t = self.made(self.ohead, self.omem)
        self.as_user(self.omem)
        self.assertEqual(self.client.get(f"/api/activity/?target=gtask:{t.pk}").status_code, 200)
        self.as_user(self.cmem)
        self.assertEqual(self.client.get(f"/api/activity/?target=gtask:{t.pk}").status_code, 404)


class CounterTests(GCase):
    def test_counters_for_the_person_and_for_their_team(self):
        late = self.made(self.ohead, self.omem, days=2, title="Late")
        GeneralTask.objects.filter(pk=late.pk).update(deadline=self.today - timedelta(days=1))
        self.made(self.ohead, self.omem, days=0, title="Today")
        self.made(self.ohead, self.omem, days=5, title="Later")
        finished = self.made(self.ohead, self.omem, days=1, title="Finished late")
        with mock.patch("generaltasks.services.timezone.now", return_value=timezone.now() + timedelta(days=3)):
            self.call(self.omem, "post", f"/api/tasks/{finished.pk}/done/")
        done_on_time = self.made(self.ohead, self.omem, days=4, title="Finished")
        self.call(self.omem, "post", f"/api/tasks/{done_on_time.pk}/done/")
        self.made(self.chead, self.cmem, title="Another team")

        mine = self.call(self.omem, "get", "/api/tasks/counters/").data
        self.assertEqual(mine["mine"], {"open": 3, "overdue": 1, "due_today": 1, "done": 2, "done_late": 1})
        self.assertIsNone(mine["team"])
        head = self.call(self.ohead, "get", "/api/tasks/counters/").data
        self.assertEqual(head["team"], {"open": 3, "overdue": 1, "due_today": 1, "done": 2, "done_late": 1})
        self.assertEqual(head["mine"], {"open": 0, "overdue": 0, "due_today": 0, "done": 0, "done_late": 0})
        ceo = self.call(self.ceo, "get", "/api/tasks/counters/").data
        self.assertEqual(ceo["team"]["open"], 4)
        self.assertEqual(ceo["team"]["done"], 2)

    def test_the_counters_match_the_list(self):
        for i in range(3):
            self.made(self.ceo, self.omem, title=f"T{i}", days=i)
        counters = self.call(self.omem, "get", "/api/tasks/counters/").data["mine"]
        listed = self.call(self.omem, "get", "/api/tasks/?status=open").data["count"]
        self.assertEqual(counters["open"], listed)


class MyWorkTests(GCase):
    def test_my_work_lists_my_tasks_that_are_due_today_or_late(self):
        today = self.made(self.ceo, self.omem, days=0, title="Due today")
        late = self.made(self.ceo, self.omem, days=3, title="Late one")
        GeneralTask.objects.filter(pk=late.pk).update(deadline=self.today - timedelta(days=1))
        self.made(self.ceo, self.omem, days=5, title="Far away")
        self.made(self.ceo, self.cmem, days=0, title="Someone else")
        items = mywork.collect(self.omem)
        got = {i["ref"]: i for i in items if i["kind"] == "gtask"}
        self.assertEqual(set(got), {"Due today", "Late one"})
        self.assertTrue(got["Late one"]["overdue"] and not got["Due today"]["overdue"])
        self.assertEqual(got["Due today"]["section"], "tasks")
        self.assertEqual(got["Due today"]["link"], f"/tasks?open={today.pk}")
        self.call(self.omem, "post", f"/api/tasks/{today.pk}/done/")
        self.assertEqual({i["ref"] for i in mywork.collect(self.omem) if i["kind"] == "gtask"}, {"Late one"})
        self.assertEqual([i for i in mywork.collect(self.hmem) if i["kind"] == "gtask"], [])
