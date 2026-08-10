# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What somebody has actually done, denormalised so the engine can read it fast.

Two criteria depend entirely on this table - "has done similar work" and "has
worked for this customer" - and both are asked for two thousand people at once.
Deriving them live from project.task at ranking time is the difference between a
shortlist that returns and one the planner gives up waiting for.

The identity of a ledger row is the thing most likely to be got wrong. Keying on
``(employee, source, task)`` looks obvious and is not: one person can hold two
roles on the same task, and a timesheet line has no stable task of its own. The
key is the *source record*, which every feeder names for itself.
"""
from psycopg2 import IntegrityError

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class ExperienceIdentityCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Experience = cls.env['aic.hrm.match.experience']
        cls.employee = cls._make_employee('Ex Perience')
        cls.customer = cls.env['res.partner'].create({'name': 'ACME Corp'})

    def _entry(self, **kwargs):
        values = {
            'employee_id': self.employee.id,
            'source': 'allocation',
            'source_key': 'alloc-1',
            'date_start': '2026-01-01',
            'date_end': '2026-03-31',
            'hours': 120.0,
        }
        values.update(kwargs)
        return self.Experience.create(values)

    @mute_logger('odoo.sql_db')
    def test_the_same_source_record_cannot_land_twice(self):
        """The rebuild must be safe to run again. Without this the ledger grows
        every time somebody presses the button."""
        self._entry()
        with self.assertRaises(IntegrityError):
            self._entry()

    def test_one_person_may_hold_two_roles_on_the_same_task(self):
        """Keying on (employee, source, task) would refuse this, and it is a
        perfectly ordinary way to staff a small project."""
        project = self.env['project.project'].create({'name': 'Two hats'})
        task = self.env['project.task'].create(
            {'name': 'Build it', 'project_id': project.id})
        first = self._entry(source_key='alloc-lead', task_id=task.id,
                            role='Tech lead', is_lead_role=True)
        second = self._entry(source_key='alloc-dev', task_id=task.id,
                             role='Developer')
        self.assertNotEqual(first, second)

    def test_two_companies_may_use_the_same_source_key(self):
        """Feeders number their own records; two companies running the same
        connector will produce the same key for different facts."""
        self._entry()
        other = self._entry(company_id=self.other_company.id)
        self.assertTrue(other.id)

    def test_deleting_the_task_keeps_the_experience(self):
        """The ledger is the record that somebody did the work. Tidying up the
        task must not make their history disappear from every future ranking.
        """
        project = self.env['project.project'].create({'name': 'Gone soon'})
        task = self.env['project.task'].create(
            {'name': 'Vanishing', 'project_id': project.id})
        entry = self._entry(task_id=task.id)
        task.unlink()
        self.assertTrue(entry.exists())
        self.assertFalse(entry.task_id)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class ExperienceOutcomeCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Experience = cls.env['aic.hrm.match.experience']
        cls.employee = cls._make_employee('Out Come')

    def _entry(self, **kwargs):
        values = {
            'employee_id': self.employee.id,
            'source': 'allocation',
            'source_key': 'k-%s' % len(self.Experience.search([])),
            'date_start': '2026-01-01',
            'date_end': '2026-03-31',
            'hours': 120.0,
        }
        values.update(kwargs)
        return self.Experience.create(values)

    def test_outcome_is_unknown_rather_than_assumed_good(self):
        """Defaulting an unknown outcome to a number invents an observation.
        The customer-affinity formula drops the term instead."""
        self.assertFalse(self._entry().outcome_score)

    def test_an_outcome_outside_zero_to_one_is_refused(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._entry(outcome_score=1.5)

    def test_an_entry_cannot_end_before_it_starts(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._entry(date_start='2026-03-31', date_end='2026-01-01')

    def test_the_recency_cron_decays_older_work(self):
        """Runs nightly and only feeds sorting and filtering. Being a day out
        of date costs nothing, because nothing that decides anything reads it -
        the engine recomputes decay against the run's frozen moment."""
        recent = self._entry(date_start='2026-08-01', date_end='2026-08-09')
        old = self._entry(date_start='2020-01-01', date_end='2020-03-31')
        self.env['aic.hrm.match.experience']._cron_refresh_recency()
        self.assertGreater(recent.recency_weight, old.recency_weight)

    def test_recency_weight_is_stored_not_computed_from_now(self):
        """A stored value that depends on the current time is stale the moment
        it is written. It is refreshed by cron, and the engine recomputes
        against the run's frozen as_of rather than trusting this."""
        entry = self._entry()
        self.assertIn('recency_weight', entry._fields)
        self.assertFalse(entry._fields['recency_weight'].compute)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CertificationWorkflowCase(MatchCase):
    """Somebody may claim a certificate; only a planner may confirm one."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls._make_employee('Cert Holder')
        cls.user = cls._make_user('Cert Claimer', ['group_match_user'])
        cls.planner = cls._make_user('Cert Verifier', ['group_match_planner'])
        cls.employee.user_id = cls.user
        cls.cert_type, cls.cert_skill, cls.cert_level = cls._make_skill_set(
            'Certifications', 'AWS Solutions Architect', certification=True)

    def _claim(self):
        return self._make_employee_skill(
            self.employee, self.cert_skill,
            valid_from='2026-01-01', valid_to='2027-01-01')

    def test_a_claim_starts_unverified(self):
        self.assertEqual(self._claim().verify_state, 'draft')

    def test_a_person_may_submit_their_own_claim(self):
        line = self._claim()
        line.with_user(self.user).action_submit_for_verification()
        self.assertEqual(line.verify_state, 'submitted')

    def test_a_person_cannot_verify_their_own_claim(self):
        """The whole value of a verified certificate is that somebody else
        checked it. Enforced in write() rather than by a record rule, because a
        rule evaluates the row as it already is and cannot reliably refuse the
        transition into it."""
        from odoo.exceptions import UserError
        line = self._claim()
        line.with_user(self.user).action_submit_for_verification()
        with self.assertRaises(UserError):
            line.with_user(self.user).write({'verify_state': 'verified'})

    def test_a_planner_verifies_and_is_recorded_as_the_verifier(self):
        line = self._claim()
        line.with_user(self.user).action_submit_for_verification()
        line.with_user(self.planner).action_verify()
        self.assertEqual(line.verify_state, 'verified')
        self.assertEqual(line.verified_by_id, self.planner)
        self.assertTrue(line.verified_date)

    def test_the_verifier_cannot_be_forged_through_vals(self):
        """Accepting verified_by_id from the caller would let anybody claim
        somebody else signed off on their certificate."""
        line = self._claim()
        line.with_user(self.user).action_submit_for_verification()
        line.with_user(self.planner).write({
            'verify_state': 'verified',
            'verified_by_id': self.user.id,
        })
        self.assertEqual(line.verified_by_id, self.planner)

    def test_an_impossible_transition_is_refused(self):
        from odoo.exceptions import UserError
        line = self._claim()
        with self.assertRaises(UserError):
            line.with_user(self.planner).write({'verify_state': 'verified'})

    def test_rejecting_a_claim_records_it_rather_than_deleting_it(self):
        line = self._claim()
        line.with_user(self.user).action_submit_for_verification()
        line.with_user(self.planner).action_reject()
        self.assertEqual(line.verify_state, 'rejected')
        self.assertTrue(line.exists())
