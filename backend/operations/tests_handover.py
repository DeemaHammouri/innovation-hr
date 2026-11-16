"""Objective 18: handover from Commercial to Operation (accept, return, escalate) and the Project that accepting creates."""
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.models import AuditEntry
from core.access import content_type_for
from notifications.models import Notification
from operations import handover as svc
from operations.models import Handover, Project
from operations.tests import OCase

H = Handover.Status


class HCase(OCase):
    def new(self, name="Brand New Co", owner=None):
        """A real signed contract handed over by HR: that is what creates the handover."""
        from django.core.files.base import ContentFile

        from contracts import services as contract_services
        from contracts.models import Contract
        from files.models import Attachment
        from leads.models import Lead
        from operations.tests import PDF

        self.seq = getattr(self, "seq", 0) + 1
        n = self.seq
        lead = Lead.objects.create(
            ref=f"LD-5{n:03d}", company_name=name, contact_name="Sam", phone=f"07500{n:05d}", email=f"s{n}@x.com", created_by=self.mkt, status="qualified",
            assigned_to=owner or self.cmem, skipped_quotation_at=timezone.now(),
        )
        c = contract_services.request_contract(owner or self.cmem, lead)
        Contract.objects.filter(pk=c.pk).update(status="signed", signed_by=self.ceo, signed_at=timezone.now())
        Attachment.objects.create(
            file=ContentFile(PDF, name="f.pdf"), original_name="f.pdf", content_type_header="application/pdf", size=len(PDF), category="final_signed",
            uploaded_by=self.hr, content_type=content_type_for(Contract), object_id=c.pk,
        )
        from contracts import services as cs

        return cs.hand_over(self.hr, Contract.objects.get(pk=c.pk)).handover

    def call(self, user, h, action, body=None):
        self.as_user(user)
        return self.client.post(f"/api/handovers/{h.pk}/{action}/", body or {}, format="json")

    def filled(self, name="Brand New Co", owner=None):
        h = self.new(name, owner)
        res = self.call(self.cmem if owner is None else owner, h, "save", {"services": "Monthly bookkeeping", "scope_notes": "Two visits a month", "contacts": "Sam 0750000001"})
        self.assertEqual(res.status_code, 200, res.data)
        return Handover.objects.get(pk=h.pk)

    def submitted(self, name="Brand New Co"):
        h = self.filled(name)
        res = self.call(self.cmem, h, "submit")
        self.assertEqual(res.status_code, 200, res.data)
        return Handover.objects.get(pk=h.pk)


class CreationTests(HCase):
    def test_marking_a_contract_handed_over_creates_one_draft_for_the_deal_owner(self):
        h = self.new()
        self.assertEqual((h.status, h.prepared_by_id, h.ref[:3]), (H.DRAFT, self.cmem.pk, "HO-"))
        self.assertEqual(Handover.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(user=self.cmem, kind="handover_requested").exists())
        for key in ("operation_head", "operation_member"):
            self.assertFalse(Notification.objects.filter(user=self.users[key]).exists(), "Operation hears nothing until Commercial submits")

    def test_creating_twice_returns_the_same_handover(self):
        h = self.new()
        again = svc.create_for_contract(self.hr, h.contract)
        self.assertEqual(again.pk, h.pk)
        self.assertEqual(Handover.objects.count(), 1)


class EditingTests(HCase):
    def test_only_the_deal_owner_or_the_commercial_head_can_fill_it_in(self):
        h = self.new()
        body = {"services": "Payroll"}
        self.assertEqual(self.call(self.cmem, h, "save", body).status_code, 200)
        self.assertEqual(self.call(self.chead, h, "save", body).status_code, 200)
        other = self.make_user("cm2@x.com", "Commercial", "member")
        self.assertEqual(self.call(other, h, "save", body).status_code, 404)  # not visible to them at all
        for key in ("ceo", "marketing", "hr_head", "hr_member", "operation_head", "operation_member"):
            self.assertIn(self.call(self.users[key], h, "save", body).status_code, (403, 404), key)

    def test_only_the_named_text_fields_are_read(self):
        h = self.new()
        res = self.call(self.cmem, h, "save", {"services": "Audit", "price": "999", "amount": "5", "status": "accepted", "prepared_by": self.ceo.pk})
        self.assertEqual(res.status_code, 200)
        h.refresh_from_db()
        self.assertEqual((h.services, h.status, h.prepared_by_id), ("Audit", H.DRAFT, self.cmem.pk))
        self.assertNotIn("price", res.data)
        self.assertNotIn("amount", res.data)

    def test_limits_and_dates_are_checked(self):
        h = self.new()
        res = self.call(self.cmem, h, "save", {"services": "x" * 4001, "start_date": "31/12/2026"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(set(res.data), {"services", "start_date"})

    def test_submit_needs_services_and_scope(self):
        h = self.new()
        self.assertEqual(self.call(self.cmem, h, "submit").data["services"][0], svc.MSG_EMPTY)
        self.call(self.cmem, h, "save", {"services": "Audit"})
        self.assertEqual(self.call(self.cmem, h, "submit").data["scope_notes"][0], svc.MSG_EMPTY)

    def test_a_submitted_handover_can_no_longer_be_edited(self):
        h = self.submitted()
        self.assertEqual(self.call(self.cmem, h, "save", {"services": "Changed"}).status_code, 400)
        self.assertEqual(Handover.objects.get(pk=h.pk).services, "Monthly bookkeeping")


class DecisionTests(HCase):
    def test_accepting_creates_exactly_one_project(self):
        h = self.submitted()
        res = self.call(self.ohead, h, "accept")
        self.assertEqual((res.status_code, res.data["status"], res.data["project"]["ref"][:4]), (200, "accepted", "PRJ-"))
        self.assertEqual(Project.objects.count(), 1)
        p = Project.objects.get()
        self.assertEqual((p.handover_id, p.client_id, p.name, p.created_by_id), (h.pk, h.client_id, h.client.company_name, self.ohead.pk))
        self.assertTrue(Notification.objects.filter(user=self.cmem, kind="handover_accepted").exists())
        self.assertEqual(self.call(self.ohead, h, "accept").status_code, 400)  # a second click
        self.assertEqual(Project.objects.count(), 1)

    def test_the_database_itself_refuses_a_second_project(self):
        h = self.submitted()
        self.call(self.ohead, h, "accept")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Project.objects.create(ref="PRJ-9999", client=h.client, handover=h, name="Again", created_by=self.ohead)

    def test_nothing_before_submission_can_be_decided(self):
        h = self.filled()
        for action, body in (("accept", {}), ("return", {"comment": "x"}), ("escalate", {"reason": "x"})):
            self.assertEqual(self.call(self.ohead, h, action, body).status_code, 404, action)  # Operation cannot even see a draft
        self.assertEqual(Project.objects.count(), 0)

    def test_return_needs_a_comment_then_commercial_edits_and_submits_again(self):
        h = self.submitted()
        self.assertEqual(self.call(self.ohead, h, "return", {"comment": " "}).status_code, 400)
        res = self.call(self.ohead, h, "return", {"comment": "Add the contact for payroll"})
        self.assertEqual((res.status_code, res.data["status"]), (200, "returned"))
        self.assertTrue(Notification.objects.filter(user=self.cmem, kind="handover_returned").exists())
        self.assertEqual(self.call(self.cmem, h, "save", {"contacts": "Sam 0750000001, payroll Lina 0750000002"}).status_code, 200)
        res = self.call(self.cmem, h, "submit")
        self.assertEqual((res.status_code, res.data["status"], res.data["decision_comment"]), (200, "submitted", ""))
        self.assertEqual(self.call(self.ohead, h, "accept").status_code, 200)

    def test_escalation_goes_to_the_ceo_who_can_then_accept_or_return(self):
        h = self.submitted()
        self.assertEqual(self.call(self.ohead, h, "escalate", {}).status_code, 400)
        res = self.call(self.ohead, h, "escalate", {"reason": "Start date is before the contract is paid"})
        self.assertEqual((res.status_code, res.data["status"]), (200, "escalated"))
        self.assertTrue(Notification.objects.filter(user=self.ceo, kind="handover_escalated").exists())
        self.assertTrue(Notification.objects.filter(user=self.cmem, kind="handover_escalated").exists())
        self.assertEqual(self.call(self.ohead, h, "escalate", {"reason": "again"}).status_code, 400)  # only from submitted
        res = self.call(self.ceo, h, "accept")
        self.assertEqual((res.status_code, res.data["status"]), (200, "accepted"))
        h2 = self.submitted("Second Co")
        self.call(self.ohead, h2, "escalate", {"reason": "Unclear scope"})
        self.assertEqual(self.call(self.ceo, h2, "return", {"comment": "Clarify the scope"}).data["status"], "returned")

    def test_each_person_may_only_do_their_own_step(self):
        h = self.submitted()
        for key in ("marketing", "hr_head", "hr_member", "commercial_head", "commercial_member"):
            for action, body in (("accept", {}), ("return", {"comment": "x"}), ("escalate", {"reason": "x"})):
                self.assertIn(self.call(self.users[key], h, action, body).status_code, (403, 404), f"{key} {action}")
        self.assertEqual(self.call(self.omem, h, "accept").status_code, 403)  # a member of Operation cannot decide
        self.assertEqual(self.call(self.omem, h, "escalate", {"reason": "x"}).status_code, 403)
        self.assertEqual(self.call(self.ceo, h, "escalate", {"reason": "x"}).status_code, 403)  # escalating is the head's step
        self.assertEqual(Handover.objects.get(pk=h.pk).status, H.SUBMITTED)

    def test_every_step_is_in_the_history(self):
        h = self.submitted()
        self.call(self.ohead, h, "return", {"comment": "More detail"})
        self.call(self.cmem, h, "submit")
        self.call(self.ohead, h, "accept")
        actions = list(AuditEntry.objects.filter(content_type=content_type_for(Handover), object_id=h.pk).order_by("id").values_list("action", flat=True))
        self.assertEqual(actions, ["created", "handover_saved", "handover_submitted", "handover_returned", "handover_submitted", "handover_accepted"])

    def test_every_illegal_transition_is_refused(self):
        legal = {"save": {H.DRAFT, H.RETURNED}, "submit": {H.DRAFT, H.RETURNED}, "accept": {H.SUBMITTED, H.ESCALATED}, "return": {H.SUBMITTED, H.ESCALATED}, "escalate": {H.SUBMITTED}}
        actor = {"save": self.cmem, "submit": self.cmem, "accept": self.ceo, "return": self.ceo, "escalate": self.ohead}
        body = {"save": {"services": "A", "scope_notes": "B"}, "return": {"comment": "c"}, "escalate": {"reason": "r"}}
        for state in H.values:
            for action, allowed in legal.items():
                h = self.new(f"Co {state} {action}")
                Handover.objects.filter(pk=h.pk).update(status=state, services="A", scope_notes="B")
                if state == "accepted":
                    Project.objects.create(ref=f"PRJ-8{h.pk}", client=h.client, handover=h, name="n", created_by=self.ohead)
                res = self.call(actor[action], h, action, body.get(action))
                if state in allowed:
                    self.assertEqual(res.status_code, 200, f"{action} from {state}: {res.data}")
                else:
                    self.assertIn(res.status_code, (400, 404), f"{action} from {state} should be refused, got {res.status_code}")


class VisibilityTests(HCase):
    def ids(self, user):
        self.as_user(user)
        res = self.client.get("/api/handovers/")
        self.assertEqual(res.status_code, 200)
        return {r["id"] for r in res.data["results"]}

    def test_who_sees_which_handover(self):
        draft = self.new("Draft Co")
        sub = self.submitted("Submitted Co")
        other = self.make_user("cm2@x.com", "Commercial", "member")
        self.assertEqual(self.ids(self.ceo), {draft.pk, sub.pk})
        self.assertEqual(self.ids(self.chead), {draft.pk, sub.pk})
        self.assertEqual(self.ids(self.cmem), {draft.pk, sub.pk})
        self.assertEqual(self.ids(other), set())
        self.assertEqual(self.ids(self.ohead), {sub.pk})  # a draft is Commercial's until it is submitted
        self.assertEqual(self.ids(self.omem), {sub.pk})
        for key in ("marketing", "hr_head", "hr_member"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/handovers/").status_code, 403, key)

    def test_a_projects_list_for_the_four_roles_that_may_see_it(self):
        h = self.submitted()
        self.call(self.ohead, h, "accept")
        for key in ("ceo", "commercial_head", "operation_head", "operation_member"):
            self.as_role(key)
            res = self.client.get("/api/projects/")
            self.assertEqual((res.status_code, len(res.data["results"])), (200, 1), key)
            self.assertEqual(set(res.data["results"][0]), {"id", "ref", "name", "status", "client", "client_name", "handover_id", "handover_ref", "start_date", "created_at", "staff", "can_staff"})
        for key in ("marketing", "commercial_member", "hr_head", "hr_member"):
            self.as_role(key)
            self.assertEqual(self.client.get("/api/projects/").status_code, 403, key)

    def test_the_handover_shows_the_client_but_names_no_contract_or_price(self):
        h = self.submitted()
        self.as_user(self.ohead)
        data = self.client.get(f"/api/handovers/{h.pk}/").data
        self.assertEqual(data["client_name"], "Brand New Co")
        self.assertEqual(
            set(data),
            {"id", "ref", "status", "client", "client_name", "contact_person", "phone", "email", "prepared_by_name", "services", "scope_notes", "contacts",
             "special_requirements", "start_date", "submitted_at", "decided_by_name", "decided_at", "decision_comment", "escalated_by_name", "escalated_at",
             "escalation_reason", "project", "permissions", "created_at", "updated_at"},
        )


class MyWorkTests(HCase):
    def kinds(self, user):
        self.as_user(user)
        return sorted(i["kind"] for i in self.client.get("/api/my-work/").data["items"] if i["kind"].startswith("handover"))

    def test_the_right_people_are_asked_at_each_step(self):
        h = self.new()
        self.assertEqual(self.kinds(self.cmem), ["handover_fill"])
        self.assertEqual(self.kinds(self.ohead), [])
        self.call(self.cmem, h, "save", {"services": "A", "scope_notes": "B"})
        self.call(self.cmem, h, "submit")
        self.assertEqual(self.kinds(self.cmem), [])
        self.assertEqual(self.kinds(self.ohead), ["handover_decide"])
        self.assertEqual(self.kinds(self.ceo), ["handover_decide"])
        self.assertEqual(self.kinds(self.omem), [])
