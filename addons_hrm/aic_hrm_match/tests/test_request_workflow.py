# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The demand side: what needs staffing, and what each seat requires.

The load-bearing decision here is that a **slot** is the unit of staffing, not
the request. "We need three people" is not one requirement repeated three
times: the seats have different skills, different effort, and filling them all
with the same person is not an answer. Making the slot the unit is what lets
required hours mean something exact and stops one person's capacity being
counted against two seats.

The other decision worth stating: a request outlives the task that prompted it.
Deleting a task must not delete the record of who was considered and why.
"""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class RequestLifecycleCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Request = cls.env['aic.hrm.match.request']
        cls.project = cls.env['project.project'].create({'name': 'ACME Phase 2'})
        cls.task = cls.env['project.task'].create({
            'name': 'Migrate billing API', 'project_id': cls.project.id})

    def _request(self, **kwargs):
        values = {
            'name': 'Staff the migration',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-25 23:59:59',
        }
        values.update(kwargs)
        return self.Request.create(values)

    def test_a_request_gets_a_reference(self):
        """Referenced rather than identified by id: the reference is what the
        tie-break salt is keyed on, and what a planner quotes in a meeting."""
        request = self._request()
        self.assertTrue(request.reference)
        self.assertNotEqual(request.reference, 'New')

    def test_references_are_unique_within_a_company(self):
        first = self._request()
        second = self._request()
        self.assertNotEqual(first.reference, second.reference)

    def test_a_request_starts_in_draft(self):
        self.assertEqual(self._request().state, 'draft')

    def test_the_window_must_be_ordered(self):
        with self.assertRaises(ValidationError):
            self._request(date_start='2026-09-25 00:00:00',
                          date_end='2026-09-14 00:00:00')

    def test_a_request_raised_from_a_task_keeps_the_task_name(self):
        request = self._request(task_id=self.task.id)
        self.assertIn('Migrate billing API', request.task_ref_snapshot)

    def test_deleting_the_task_does_not_delete_the_request(self):
        """The request holds why somebody was chosen. Losing it because a task
        was tidied up destroys the only record of the decision."""
        request = self._request(task_id=self.task.id)
        self.task.unlink()
        self.assertTrue(request.exists())
        self.assertFalse(request.task_id)
        self.assertIn('Migrate billing API', request.task_ref_snapshot)

    def test_a_request_with_decisions_cannot_be_deleted(self):
        """Archiving keeps the audit trail; deleting removes it. Once a
        decision exists the request is evidence, not scratch work."""
        request = self._request()
        request.state = 'decided'
        with self.assertRaises(ValidationError):
            request.unlink()

    def test_a_draft_request_may_still_be_deleted(self):
        request = self._request()
        request.unlink()
        self.assertFalse(request.exists())

    def test_the_customer_follows_the_project(self):
        partner = self.env['res.partner'].create({'name': 'ACME Corp'})
        self.project.partner_id = partner
        request = self._request(project_id=self.project.id)
        self.assertEqual(request.partner_id, partner)

    def test_company_scope_defaults_to_the_requesting_company(self):
        """Cross-company staffing is opt-in. Until somebody turns it on, the
        pool is the company that raised the request."""
        request = self._request()
        self.assertEqual(request.request_company_id, self.company)
        self.assertEqual(request.company_ids, self.company)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class SlotCase(MatchCase):
    """A slot is one seat to fill."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Request = cls.env['aic.hrm.match.request']
        cls.request = cls.Request.create({
            'name': 'Two-person job',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-25 23:59:59',
        })
        cls.skill_type, cls.skill, cls.level = cls._make_skill_set(
            'Backend', 'Python')

    def _slot(self, **kwargs):
        values = {'request_id': self.request.id, 'name': 'Backend developer',
                  'required_hours': 64.0}
        values.update(kwargs)
        return self.env['aic.hrm.match.request.slot'].create(values)

    def test_headcount_is_the_number_of_slots(self):
        """Not a number on the request. Three seats are three records, each
        with its own requirements, or "we need three people" collapses into one
        requirement repeated."""
        self._slot()
        self._slot(name='QA engineer', required_hours=24.0)
        self.assertEqual(self.request.headcount, 2)

    def test_required_hours_belong_to_the_slot(self):
        slot = self._slot()
        self.assertAlmostEqual(slot.required_hours, 64.0)

    def test_required_hours_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._slot(required_hours=-8.0)

    def test_a_slot_cannot_require_a_negative_share_of_time(self):
        with self.assertRaises(ValidationError):
            self._slot(fte_ratio=-0.5)

    def test_a_slot_inherits_the_requests_window(self):
        """Stated once on the request and read from the slot, so a planner
        cannot leave the two disagreeing."""
        slot = self._slot()
        self.assertEqual(slot.date_start, self.request.date_start)
        self.assertEqual(slot.date_end, self.request.date_end)

    def test_deleting_the_request_takes_its_slots(self):
        slot = self._slot()
        self.request.unlink()
        self.assertFalse(slot.exists())

    def test_a_skill_requirement_carries_a_minimum_level(self):
        slot = self._slot()
        line = self.env['aic.hrm.match.request.slot.skill'].create({
            'slot_id': slot.id,
            'skill_id': self.skill.id,
            'min_level_id': self.level.id,
            'requirement': 'mandatory',
        })
        self.assertAlmostEqual(line.min_level_progress, 100.0)

    def test_a_level_must_belong_to_the_skills_own_type(self):
        """A level from another skill type makes the gap meaningless: the two
        scales measure different things."""
        _other_type, other_skill, other_level = self._make_skill_set(
            'Languages', 'French')
        slot = self._slot()
        with self.assertRaises(ValidationError):
            self.env['aic.hrm.match.request.slot.skill'].create({
                'slot_id': slot.id,
                'skill_id': self.skill.id,
                'min_level_id': other_level.id,
                'requirement': 'mandatory',
            })

    def test_the_same_skill_cannot_be_required_twice_on_one_slot(self):
        slot = self._slot()
        values = {'slot_id': slot.id, 'skill_id': self.skill.id,
                  'requirement': 'mandatory'}
        self.env['aic.hrm.match.request.slot.skill'].create(values)
        with self.assertRaises(ValidationError):
            self.env['aic.hrm.match.request.slot.skill'].create(values)

    def test_stretch_is_off_unless_asked_for(self):
        """Relaxing a mandatory requirement has to be a deliberate act on the
        requirement itself, not a side effect of a fairness setting."""
        slot = self._slot()
        line = self.env['aic.hrm.match.request.slot.skill'].create({
            'slot_id': slot.id, 'skill_id': self.skill.id,
            'requirement': 'mandatory'})
        self.assertFalse(line.stretch_allowed)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class StaffingProfileCase(MatchCase):
    """What the engine needs to know about a person beyond their skills."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env['aic.hrm.match.profile']
        cls.employee = cls._make_employee('Pia Profile')

    def test_a_profile_is_created_on_demand(self):
        """Not for all two thousand employees up front: most are never
        candidates, and a table of empty rows is a table nobody maintains."""
        profile = self.Profile._ensure_profiles(self.employee)
        self.assertEqual(profile.employee_id, self.employee)

    def test_ensuring_twice_does_not_duplicate(self):
        first = self.Profile._ensure_profiles(self.employee)
        second = self.Profile._ensure_profiles(self.employee)
        self.assertEqual(first, second)

    def test_ensuring_profiles_for_nobody_returns_nothing(self):
        """An empty pool is an ordinary outcome of a narrow filter, not an
        error, and the engine calls this before it knows the pool is empty."""
        self.assertFalse(
            self.Profile._ensure_profiles(self.env['hr.employee']))

    def test_a_person_is_staffable_by_default(self):
        profile = self.Profile._ensure_profiles(self.employee)
        self.assertTrue(profile.staffable)

    def test_opting_out_is_recorded_with_its_reason(self):
        """Somebody excluded from staffing should be excluded visibly, with a
        reason a planner can read, rather than by quietly deleting their data.
        """
        profile = self.Profile._ensure_profiles(self.employee)
        profile.write({'match_opt_out': True,
                       'opt_out_reason': 'On parental leave until March'})
        self.assertTrue(profile.match_opt_out)
        self.assertIn('parental', profile.opt_out_reason)

    @mute_logger('odoo.sql_db')
    def test_one_profile_per_employee_and_company(self):
        """Refused by the database rather than by a model constraint: profiles
        are created by _ensure_profiles, not typed, so a duplicate is a
        programming error and the index is what actually holds under
        concurrency."""
        self.Profile._ensure_profiles(self.employee)
        with self.assertRaises(IntegrityError):
            self.Profile.create({'employee_id': self.employee.id,
                                 'resource_company_id': self.company.id})

    def test_rates_are_hidden_from_planners(self):
        """Cost is a field-level secret: a record rule cannot hide a column,
        only a row."""
        planner = self._make_user('Rate Blind', ['group_match_planner'])
        profile = self.Profile._ensure_profiles(self.employee)
        fields_for_planner = self.Profile.with_user(planner).fields_get()
        self.assertNotIn('cost_hourly', fields_for_planner)
        self.assertTrue(profile.id)

    def test_an_administrator_sees_the_rates(self):
        admin = self._make_user('Rate Owner', ['group_match_admin'])
        self.assertIn('cost_hourly', self.Profile.with_user(admin).fields_get())


@tagged('post_install', '-at_install', 'aic_hrm_match')
class RequestActionCase(MatchCase):
    """The buttons on the request, and what they are allowed to do.

    Every one of these is reachable from the form header, so a method the view
    names but the model does not have is not a missing feature - Odoo refuses
    to load the view at all, and the whole module fails to install.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.criterion = cls._criterion('availability', category='availability', normalization='ratio')
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Actions', 'code': 'actions_policy', 'is_default': True})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id})
        cls.policy.action_activate()

    def _request(self, with_slot=True):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Buttons',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        if with_slot:
            self.env['aic.hrm.match.request.slot'].create({
                'request_id': request.id, 'name': 'Dev',
                'required_hours': 8.0})
        return request

    def test_ranking_a_draft_request_moves_it_on_and_opens_the_result(self):
        request = self._request()
        action = request.action_rank()
        self.assertEqual(request.state, 'ranked')
        self.assertTrue(request.latest_run_id)
        self.assertEqual(action['res_model'], 'aic.hrm.match.run')
        self.assertEqual(action['res_id'], request.latest_run_id.id)

    def test_re_ranking_leaves_the_earlier_run_readable(self):
        """The button says re-rank, and that has to mean a second run rather
        than the first one being rewritten: a decision taken this morning must
        still be explainable this afternoon."""
        request = self._request()
        request.action_rank()
        first = request.latest_run_id
        request.action_rank()
        self.assertNotEqual(request.latest_run_id, first)
        self.assertEqual(len(request.run_ids), 2)
        self.assertTrue(first.exists())

    def test_ranking_a_request_with_no_slot_says_what_is_missing(self):
        with self.assertRaises(UserError):
            self._request(with_slot=False).action_rank()

    def test_closing_a_staffed_request_ends_it(self):
        request = self._request()
        request.state = 'staffed'
        request.action_close()
        self.assertEqual(request.state, 'closed')

    def test_a_closed_request_cannot_be_re_ranked(self):
        """Ranking a finished request would produce a shortlist for work that
        is over, and the screen gives no hint that is what happened."""
        request = self._request()
        request.state = 'closed'
        with self.assertRaises(UserError):
            request.action_rank()

    def test_closing_something_that_never_started_is_refused(self):
        request = self._request()
        with self.assertRaises(UserError):
            request.action_close()

    def test_cancelling_keeps_the_request_rather_than_deleting_it(self):
        request = self._request()
        request.action_cancel()
        self.assertEqual(request.state, 'cancelled')

    def test_a_decided_request_cannot_be_cancelled_away(self):
        """Cancellation is for work that never happened. Once somebody has
        been assigned, the honest ending is closing it - cancelling would erase
        the reason the request existed from every report that counts it."""
        request = self._request()
        request.state = 'decided'
        with self.assertRaises(UserError):
            request.action_cancel()

    def test_reopening_a_cancelled_request_puts_it_back_in_draft(self):
        request = self._request()
        request.action_cancel()
        request.action_reset_to_draft()
        self.assertEqual(request.state, 'draft')
