# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The boundary that keeps the ranking fast and reproducible.

Two properties are worth more than the code that provides them:

* **Scoring cannot query.** Everything a criterion needs is loaded in the
  prefetch phase, for the whole pool at once. A scorer that reaches for
  something it did not prefetch finds nothing - a visible bug - rather than
  issuing one query per candidate and turning a three-second ranking into a
  five-minute one that still returns the right answer.
* **Scoring cannot mutate its input.** The request is copied into a plain dict,
  so a scorer holding it cannot write back to the record it is scoring.
"""
from odoo.tests import tagged

from odoo.addons.aic_hrm_match.models.match_context import MatchContext

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class MatchContextCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.criterion = cls.env['aic.hrm.match.criterion'].create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability',
            'param_json': '{"half_life_days": 540}'})
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Ctx', 'code': 'ctx'})
        cls.line = cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id})
        cls.request = cls.env['aic.hrm.match.request'].create({
            'name': 'Context test',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        cls.slot = cls.env['aic.hrm.match.request.slot'].create({
            'request_id': cls.request.id, 'name': 'Dev',
            'required_hours': 20.0})
        cls.alice = cls._make_employee('Ctx Alice')
        cls.bob = cls._make_employee('Ctx Bob')

    def _context(self):
        return MatchContext(
            self.env, self.request, self.slot, self.line,
            [self.alice.id, self.bob.id], as_of='2026-09-01 00:00:00')

    def test_the_request_is_frozen_into_plain_data(self):
        """A scorer holding a live recordset can write to it, and a scoring
        pass that mutates what it is scoring is not reproducible."""
        context = self._context()
        self.assertIsInstance(context.request, dict)
        self.assertEqual(context.request['reference'], self.request.reference)

    def test_parameters_are_parsed_once_and_read_by_key(self):
        context = self._context()
        self.assertEqual(
            context.param('availability', 'half_life_days'), 540)

    def test_a_missing_parameter_returns_the_default(self):
        """A knob nobody set is a configuration choice, not a broken run."""
        context = self._context()
        self.assertEqual(context.param('availability', 'nope', 7), 7)
        self.assertIsNone(context.param('no_such_criterion', 'nope'))

    def test_evidence_accumulates_per_candidate_and_criterion(self):
        """Collected as the score is produced. An explanation reconstructed
        afterwards is a second implementation of the same logic, and the two
        drift."""
        context = self._context()
        context.add_evidence(self.alice.id, 'availability', '20 free of 20')
        context.add_evidence(self.alice.id, 'availability', 'no leave booked')
        self.assertEqual(
            len(context.evidence[(self.alice.id, 'availability')]), 2)

    def test_evidence_can_point_at_the_record_behind_it(self):
        context = self._context()
        context.add_evidence(self.alice.id, 'availability', 'busy',
                             res_model='project.task', res_id=42)
        entry = context.evidence[(self.alice.id, 'availability')][0]
        self.assertEqual(entry['res_model'], 'project.task')
        self.assertEqual(entry['res_id'], 42)

    def test_rejecting_removes_from_eligible_but_not_from_evaluated(self):
        """Nobody is dropped silently: the run keeps a record for everyone it
        looked at, and an exclusion carries the gate that produced it."""
        context = self._context()
        context.reject(self.bob.id, 'availability', 'no_capacity',
                       '0 h free of 20 h needed')
        self.assertEqual(context.eligible_ids, [self.alice.id])
        self.assertIn(self.bob.id, context.rejected_ids)
        self.assertIn(self.bob.id, context.employee_ids)

    def test_a_rejection_keeps_the_reason_that_produced_it(self):
        context = self._context()
        context.reject(self.bob.id, 'availability', 'no_capacity', '0 of 20')
        reason = context.rejections[self.bob.id][0]
        self.assertEqual(reason['rejection_code'], 'no_capacity')
        self.assertIn('0 of 20', reason['detail'])

    def test_the_scoped_pool_is_what_raw_sql_must_use(self):
        """SQL does not go through record rules. A scorer building its own pool
        would quietly cross a company line, so the pool the caller was allowed
        to see is carried explicitly."""
        context = self._context()
        self.assertEqual(set(context.scoped_ids),
                         {self.alice.id, self.bob.id})
        self.assertTrue(context.allowed_company_ids)

    def test_the_window_comes_from_the_slot(self):
        context = self._context()
        self.assertEqual(context.window,
                         (self.slot.date_start, self.slot.date_end))


@tagged('post_install', '-at_install', 'aic_hrm_match')
class ScorerRegistryCase(MatchCase):
    """Discovery is by naming convention, so adding a criterion is one record
    and one method, with no change to this module."""

    def test_the_registry_lists_what_can_actually_be_scored(self):
        codes = self.env['aic.hrm.match.scorer'].get_scorer_codes()
        self.assertIn('availability', codes)

    def test_an_unknown_code_scores_nothing_rather_than_crashing(self):
        """Reached when a connector is removed after a policy was activated.
        Losing a criterion must degrade the ranking, not abort it mid-run."""
        scorer = self.env['aic.hrm.match.scorer']
        self.assertEqual(scorer.score('no_such_code', None), {})

    def test_prefetching_an_unknown_code_is_a_no_op(self):
        self.env['aic.hrm.match.scorer'].prefetch('no_such_code', None)

    def test_the_availability_scorer_prefetches_then_scores_without_querying(self):
        """The contract every criterion follows: load for the whole pool, then
        score from what was loaded.

        Asserted by counting queries across the scoring phase. A scorer that
        reaches for something it did not prefetch would show up here as one
        query per candidate, which is the difference between a three-second
        ranking and one the planner abandons.
        """
        alice = self._make_employee('Scorer Alice')
        bob = self._make_employee('Scorer Bob')
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Scorer run',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        slot = self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 20.0})
        criterion = self.env['aic.hrm.match.criterion'].create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability'})
        policy = self.env['aic.hrm.match.policy'].create({
            'name': 'Scorer', 'code': 'scorer_policy'})
        line = self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': criterion.id})

        context = MatchContext(self.env, request, slot, line,
                               [alice.id, bob.id],
                               as_of='2026-09-01 00:00:00')
        scorer = self.env['aic.hrm.match.scorer']
        scorer.prefetch('availability', context)
        self.assertIn('availability', context.data)

        self.env.flush_all()
        before = self.env.cr.sql_log_count if hasattr(
            self.env.cr, 'sql_log_count') else None
        scores = scorer.score('availability', context)
        if before is not None:
            self.assertEqual(self.env.cr.sql_log_count, before,
                             'scoring issued a query; everything it needs '
                             'must come from the prefetch phase')

        self.assertEqual(set(scores), {alice.id, bob.id})
        self.assertGreater(scores[alice.id], 0.0)
        self.assertTrue(context.evidence[(alice.id, 'availability')])

    def test_a_criterion_added_by_inheritance_registers_itself(self):
        """The extension contract: a connector defines _score_<code> through
        _inherit and the code becomes available with no change here.

        Attached with setattr rather than self.patch, which can only replace an
        attribute that already exists - and the whole point is that this one
        does not until a connector brings it.
        """
        scorer = self.env['aic.hrm.match.scorer']
        scorer_model = type(scorer)
        name = '_score_invented_by_a_connector'
        setattr(scorer_model, name, lambda self, context: {'ok': 1})
        self.addCleanup(delattr, scorer_model, name)

        self.assertIn('invented_by_a_connector', scorer.get_scorer_codes())
        self.assertEqual(scorer.score('invented_by_a_connector', None),
                         {'ok': 1})
