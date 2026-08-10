# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Three switches on the policy that have to do what they say.

A setting the engine never reads is worse than a missing feature. The form
offers it, the documentation describes it, somebody turns it on and believes
the thing it names is happening - and nothing about the screen tells them
otherwise. For the anonymity switch that is not a gap in a feature list, it is
a privacy claim that is not true.

* ``anonymize_until_decision`` has to actually blind the ranking: no name on
  the candidate row at all, and the mapping behind its own access list.
* ``fairness_mode`` has to move the score visibly, as a separate term, within a
  stated bound.
* ``engine_model`` has to hand the run to the named engine, and refuse to
  quietly fall back to the built-in one when it breaks.
"""
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class PolicySwitchCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.criterion = cls._criterion('availability')
        cls.people = cls.env['hr.employee'].browse()
        for index in range(3):
            cls.people |= cls._make_employee('Switch Subject %d' % index)

    def _policy(self, **values):
        base = {'name': 'Switches', 'code': 'switches', 'sequence': 1,
                'persist_mode': 'full'}
        base.update(values)
        policy = self.env['aic.hrm.match.policy'].create(base)
        self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': self.criterion.id,
            'weight': 1.0})
        policy.action_activate()
        return policy

    def _request(self):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Switch test',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 8.0})
        return request

    # -- anonymity -----------------------------------------------------------

    def test_a_blind_ranking_carries_no_names(self):
        """Not a hidden column - no name on the row at all.

        A field the view hides is still there for RPC, export, pivot and
        developer mode, so hiding it would make the promise true only for
        people who take the screen at its word.
        """
        policy = self._policy(anonymize_until_decision=True)
        run = self.engine.run_match(self._request(), policy=policy)

        self.assertTrue(run.candidate_ids)
        self.assertFalse(run.candidate_ids.employee_id,
                         'a blind run must not put anybody on the candidate')
        for candidate in run.candidate_ids:
            self.assertTrue(candidate.identity_ref)
            self.assertEqual(candidate.display_ref, candidate.identity_ref)

    def test_the_mapping_exists_so_the_run_is_still_auditable(self):
        """Anonymous to the planner, not to the record. A ranking nobody can
        ever resolve is not privacy, it is an unauditable decision."""
        policy = self._policy(anonymize_until_decision=True)
        run = self.engine.run_match(self._request(), policy=policy)
        identities = self.env['aic.hrm.match.identity'].search(
            [('run_id', '=', run.id)])
        self.assertEqual(len(identities), len(run.candidate_ids))
        self.assertEqual(identities.mapped('employee_id.id').__len__(),
                         len(run.candidate_ids))

    def test_a_planner_cannot_read_the_mapping(self):
        """The whole mechanism rests on this. If a planner can open the
        identity table then the anonymity is decorative."""
        policy = self._policy(anonymize_until_decision=True)
        run = self.engine.run_match(self._request(), policy=policy)
        planner = self._make_user('Blind Planner', ['group_match_planner'])
        with self.assertRaises(AccessError):
            self.env['aic.hrm.match.identity'].with_user(planner).search(
                [('run_id', '=', run.id)]).mapped('employee_id')

    def test_an_ordinary_ranking_still_names_people(self):
        """The switch is off by default, and off has to mean off."""
        policy = self._policy(code='named', anonymize_until_decision=False)
        run = self.engine.run_match(self._request(), policy=policy)
        self.assertTrue(run.candidate_ids.employee_id)

    # -- fairness ------------------------------------------------------------

    def test_load_balancing_moves_the_score_and_says_by_how_much(self):
        """Kept as its own term rather than folded into the merit, so a reader
        can see that the ranking was adjusted and by how much."""
        busy = self.people[0]
        capacity = self.env['aic.hrm.match.availability'].get_gross_hours(
            busy, '2026-09-14 00:00:00', '2026-09-18 23:59:59')
        busy.company_id.match_over_allocation_tolerance = 99.0
        self.env['aic.hrm.match.allocation'].create({
            'employee_id': busy.id,
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59',
            'allocated_hours': capacity * 0.5,
            'state': 'confirmed'})

        policy = self._policy(code='fair', fairness_mode='load_balance',
                              fairness_strength=1.0)
        run = self.engine.run_match(self._request(), policy=policy)
        adjusted = run.candidate_ids.filtered('fairness_adjustment')
        self.assertTrue(adjusted, 'load balancing adjusted nobody')
        for candidate in adjusted:
            self.assertNotEqual(candidate.raw_score, candidate.total_score)

    def test_the_adjustment_stays_inside_its_stated_bound(self):
        """An unbounded correction stops being a tie-break and becomes the
        ranking, which is not what the weights say is happening."""
        policy = self._policy(code='fair_capped', fairness_mode='load_balance',
                              fairness_strength=1.0)
        run = self.engine.run_match(self._request(), policy=policy)
        for candidate in run.candidate_ids:
            self.assertLessEqual(abs(candidate.fairness_adjustment), 0.15)

    def test_the_total_never_leaves_zero_to_one(self):
        policy = self._policy(code='fair_clamp', fairness_mode='load_balance',
                              fairness_strength=1.0)
        run = self.engine.run_match(self._request(), policy=policy)
        for candidate in run.candidate_ids:
            self.assertGreaterEqual(candidate.total_score, 0.0)
            self.assertLessEqual(candidate.total_score, 1.0)

    def test_with_fairness_off_the_two_scores_agree(self):
        policy = self._policy(code='no_fair', fairness_mode='off')
        run = self.engine.run_match(self._request(), policy=policy)
        for candidate in run.candidate_ids:
            self.assertAlmostEqual(candidate.fairness_adjustment, 0.0)
            self.assertAlmostEqual(candidate.raw_score, candidate.total_score,
                                   places=6)

    # -- engine swap ---------------------------------------------------------

    def test_the_run_records_which_engine_decided(self):
        """Naming the built-in engine explicitly changes nothing, and the
        snapshot still says who ran. Auditing a ranking starts with knowing
        which code produced it, so that cannot be left implicit."""
        policy = self._policy(code='named_engine',
                              engine_model='aic.hrm.match.engine')
        run = self.engine.run_match(self._request(), policy=policy)
        snapshot = json.loads(run.parameter_snapshot)
        self.assertEqual(snapshot['engine']['ran'], 'aic.hrm.match.engine')
        self.assertEqual(snapshot['engine']['model'], 'aic.hrm.match.engine')
        self.assertFalse(snapshot['engine']['engine_fallback'])

    def test_naming_an_engine_that_does_not_exist_is_refused(self):
        """Fail closed. Silently ranking with the built-in engine would produce
        a staffing decision made by code the policy did not authorise, and
        nothing on screen would say so."""
        policy = self._policy(code='missing_engine',
                              engine_model='aic.hrm.match.engine.nope')
        with self.assertRaises(UserError):
            self.engine.run_match(self._request(), policy=policy)

    def test_a_fallback_is_allowed_only_when_the_policy_says_so(self):
        """And when it happens it goes into the snapshot, so the run records
        that it was not decided by the engine it names."""
        policy = self._policy(code='fallback_ok',
                              engine_model='aic.hrm.match.engine.nope',
                              engine_fallback_allowed=True)
        run = self.engine.run_match(self._request(), policy=policy)
        snapshot = json.loads(run.parameter_snapshot)
        self.assertEqual(run.state, 'computed')
        self.assertTrue(snapshot['engine']['engine_fallback'],
                        'a run that fell back has to say so, or the record '
                        'claims a decision was made by code that never ran')
        self.assertEqual(snapshot['engine']['model'],
                         'aic.hrm.match.engine.nope')
