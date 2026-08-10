# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Producing a shortlist, and being able to defend it afterwards.

The invariant this file exists to protect is that **nobody is dropped
silently**. Every person the engine looked at keeps a record; every exclusion
keeps the gate that produced it. A ranking that quietly omits people is worse
than no ranking, because it looks complete.

The second theme is reproducibility. A run freezes the moment it was taken and
the parameters it ran under, so "why was she chosen in March" has an answer in
June - even after the weights have moved on.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class RankingCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['aic.hrm.match.run']
        cls.engine = cls.env['aic.hrm.match.engine']

        cls.criterion = cls.env['aic.hrm.match.criterion'].create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability', 'mode': 'both',
            'normalization': 'ratio'})
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Ranking', 'code': 'ranking', 'is_default': True})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id,
            'weight': 1.0})
        cls.policy.action_activate()

        cls.free = cls._make_employee('Fully Free')
        cls.busy = cls._make_employee('Fully Busy')
        cls.half = cls._make_employee('Half Free')

    def _request(self, required_hours=20.0, allow_partial=False):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Rank me',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Developer',
            'required_hours': required_hours,
            'allow_partial_availability': allow_partial})
        return request

    def _fill(self, employee, share):
        """Consume a share of somebody's week."""
        capacity = self.env['aic.hrm.match.availability'].get_gross_hours(
            employee, '2026-09-14 00:00:00', '2026-09-18 23:59:59')
        employee.company_id.match_over_allocation_tolerance = 99.0
        self.env['aic.hrm.match.allocation'].create({
            'employee_id': employee.id,
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59',
            'allocated_hours': capacity * share,
            'state': 'confirmed'})

    # -- the invariant -------------------------------------------------------

    def test_everybody_evaluated_keeps_a_record(self):
        """The invariant. A ranking that quietly omits people is worse than no
        ranking, because it looks complete."""
        self._fill(self.busy, 1.0)
        run = self.engine.run_match(self._request())
        ranked = run.candidate_ids.filtered('eligible')
        excluded = run.candidate_ids.filtered(lambda c: not c.eligible)
        self.assertEqual(len(ranked) + len(excluded), len(run.candidate_ids))
        self.assertEqual(len(run.candidate_ids), run.candidate_count)
        self.assertGreaterEqual(len(run.candidate_ids), 3)

    def test_the_invariant_holds_when_only_the_shortlist_is_detailed(self):
        """persist_mode controls how much presentation detail is kept. It must
        never be able to drop a candidate or a reason."""
        self._fill(self.busy, 1.0)
        for mode in ('full', 'ranked_only'):
            policy = self.policy.action_new_version()
            policy.persist_mode = mode
            policy.top_n = 1
            policy.action_activate()
            run = self.engine.run_match(self._request())
            self.assertEqual(
                len(run.candidate_ids.filtered('eligible'))
                + len(run.candidate_ids.filtered(lambda c: not c.eligible)),
                len(run.candidate_ids), mode)
            self.assertTrue(
                all(c.rejection_code
                    for c in run.candidate_ids if not c.eligible),
                '%s: an exclusion without a reason is a silent drop' % mode)

    def test_an_excluded_candidate_says_why(self):
        self._fill(self.busy, 1.0)
        run = self.engine.run_match(self._request())
        busy = run.candidate_ids.filtered(
            lambda c: c.employee_id == self.busy)
        self.assertTrue(busy)
        self.assertFalse(busy.eligible)
        self.assertTrue(busy.rejection_code)
        self.assertTrue(busy.rejection_detail)

    # -- ordering ------------------------------------------------------------

    def test_a_freer_person_outranks_a_busier_one(self):
        """Relative order, not absolute position: the pool is every employee in
        the company, including whoever the database already had.

        The seat asks for the whole week, so free time is genuinely scarce and
        the three fixtures separate. Partial availability is allowed, which is
        what keeps the busier two on the list to be ranked at all instead of
        being eliminated before the question is asked.
        """
        self._fill(self.half, 0.3)
        self._fill(self.busy, 1.0)
        run = self.engine.run_match(
            self._request(required_hours=40.0, allow_partial=True))
        by_employee = {c.employee_id.id: c for c in run.candidate_ids}

        self.assertLess(by_employee[self.free.id].rank,
                        by_employee[self.half.id].rank)
        self.assertLess(by_employee[self.half.id].rank,
                        by_employee[self.busy.id].rank)
        self.assertGreater(by_employee[self.free.id].total_score,
                           by_employee[self.half.id].total_score)
        self.assertGreater(by_employee[self.half.id].total_score,
                           by_employee[self.busy.id].total_score)

    def test_having_more_than_enough_is_not_worth_more_than_enough(self):
        """Availability saturates at what the seat asks for.

        Someone with a whole week free and someone with a day to spare both
        cover a four-hour job completely, and ranking the first above the
        second would push every request towards the least-loaded person for a
        reason that does not exist. Scarcity is what the criterion measures,
        and above the requirement there is none.
        """
        self._fill(self.half, 0.3)
        run = self.engine.run_match(self._request(required_hours=4.0))
        by_employee = {c.employee_id.id: c for c in run.candidate_ids}
        self.assertAlmostEqual(by_employee[self.free.id].total_score,
                               by_employee[self.half.id].total_score, places=6)

    def test_ranks_are_dense_and_start_at_one(self):
        run = self.engine.run_match(self._request())
        ranked = run.candidate_ids.filtered('eligible').sorted('rank')
        self.assertEqual([c.rank for c in ranked],
                         list(range(1, len(ranked) + 1)))

    def test_excluded_candidates_carry_no_rank(self):
        """A rank is a position in a shortlist. Somebody who is not on it does
        not have one, and giving them a number invites reading it as one."""
        self._fill(self.busy, 1.0)
        run = self.engine.run_match(self._request())
        for candidate in run.candidate_ids.filtered(lambda c: not c.eligible):
            self.assertFalse(candidate.rank)

    # -- reproducibility -----------------------------------------------------

    def test_a_run_freezes_the_moment_it_was_taken(self):
        run = self.engine.run_match(self._request())
        self.assertTrue(run.as_of)
        self.assertTrue(run.parameter_snapshot)

    def test_a_run_records_which_policy_version_produced_it(self):
        """Weights move on. Without the version, a ranking from March cannot be
        explained in June."""
        run = self.engine.run_match(self._request())
        self.assertEqual(run.policy_id, self.policy)
        self.assertEqual(run.policy_version, self.policy.version)

    def test_a_computed_run_cannot_be_edited(self):
        run = self.engine.run_match(self._request())
        with self.assertRaises(UserError):
            run.write({'policy_version': 99})

    def test_re_ranking_creates_a_new_run_rather_than_overwriting(self):
        """Re-running must not rewrite what a decision was based on."""
        request = self._request()
        first = self.engine.run_match(request)
        second = self.engine.run_match(request)
        self.assertNotEqual(first, second)
        self.assertEqual(len(request.run_ids), 2)

    def test_the_latest_run_ignores_a_failed_one(self):
        """max(id) would point the screen at a run that produced nothing."""
        request = self._request()
        good = self.engine.run_match(request)
        failed = self.Run.create({
            'request_id': request.id, 'slot_id': request.slot_ids[0].id,
            'policy_id': self.policy.id, 'state': 'failed'})
        self.assertTrue(failed.id)
        self.assertEqual(request.latest_run_id, good)

    # -- tie-breaking --------------------------------------------------------

    def test_re_ranking_the_same_request_keeps_the_same_order(self):
        """A planner who presses the button twice must not see a different
        winner among people who scored identically."""
        request = self._request()
        first = self.engine.run_match(request)
        second = self.engine.run_match(request)
        self.assertEqual(
            [c.employee_id.id for c in
             first.candidate_ids.filtered('eligible').sorted('rank')],
            [c.employee_id.id for c in
             second.candidate_ids.filtered('eligible').sorted('rank')])

    def test_two_requests_do_not_always_pick_the_same_person(self):
        """Sorting ties by employee id means the lowest id wins every tie
        forever - a bias that compounds for years and appears in no report."""
        orders = set()
        for _ in range(6):
            run = self.engine.run_match(self._request())
            orders.add(tuple(
                c.employee_id.id for c in
                run.candidate_ids.filtered('eligible').sorted('rank')))
        self.assertGreater(
            len(orders), 1,
            'every request produced the same order; the tie-break is not '
            'varying between requests')

    # -- explanation ---------------------------------------------------------

    def test_a_candidate_keeps_the_breakdown_behind_its_score(self):
        run = self.engine.run_match(self._request())
        top = run.candidate_ids.filtered('eligible').sorted('rank')[0]
        self.assertTrue(top.score_line_ids)
        line = top.score_line_ids[0]
        self.assertEqual(line.criterion_code, 'availability')
        self.assertTrue(line.evidence_ids)

    def test_a_score_line_keeps_its_criterion_even_if_the_criterion_goes(self):
        """Uninstalling a connector must not erase the record of what a past
        ranking was configured with."""
        run = self.engine.run_match(self._request())
        line = run.candidate_ids.filtered('eligible')[0].score_line_ids[0]
        self.assertEqual(line.criterion_code, 'availability')
        self.assertTrue(line.criterion_name)

    def test_the_total_is_the_weighted_sum_of_its_parts(self):
        """The number on the shortlist has to be the one the breakdown adds up
        to, or the explanation is decoration."""
        run = self.engine.run_match(self._request())
        for candidate in run.candidate_ids.filtered('eligible'):
            expected = sum(candidate.score_line_ids.mapped('weighted_score'))
            weights = sum(
                line.weight for line in candidate.score_line_ids
                if not line.is_missing)
            if weights:
                self.assertAlmostEqual(candidate.raw_score, expected / weights,
                                       places=4)

    def test_a_candidate_reads_as_a_person_or_as_a_reference(self):
        """The opaque reference is always present, so a screen never has a blank
        row to show when the run is anonymised. Whether the name appears is the
        policy's decision, not the view's."""
        run = self.engine.run_match(self._request())
        candidate = run.candidate_ids[0]
        self.assertEqual(candidate.display_ref,
                         candidate.employee_id.display_name)

        anonymous = candidate.copy({'employee_id': False})
        self.assertEqual(anonymous.display_ref, anonymous.identity_ref)
        self.assertTrue(anonymous.identity_ref)

    def test_scores_stay_inside_zero_and_one(self):
        run = self.engine.run_match(self._request())
        for candidate in run.candidate_ids:
            self.assertGreaterEqual(candidate.total_score, 0.0)
            self.assertLessEqual(candidate.total_score, 1.0)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class HardGateCase(MatchCase):
    """Who is removed before scoring, and whether they say why.

    Each of these is a rule that takes a person off the list entirely, so an
    untested one is a person disappearing for a reason nobody wrote down.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.criterion = cls.env['aic.hrm.match.criterion'].create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability', 'mode': 'both',
            'normalization': 'ratio'})
        cls.policy = cls.env['aic.hrm.match.policy'].create({
            'name': 'Gates', 'code': 'gates', 'is_default': True})
        cls.env['aic.hrm.match.policy.line'].create({
            'policy_id': cls.policy.id, 'criterion_id': cls.criterion.id,
            'weight': 1.0})
        cls.policy.action_activate()
        cls.employee = cls._make_employee('Gated Person')

    def _request(self, **slot_values):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Gate me',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        values = {'request_id': request.id, 'name': 'Dev',
                  'required_hours': 8.0}
        values.update(slot_values)
        self.env['aic.hrm.match.request.slot'].create(values)
        return request

    def _profile(self):
        return self.env['aic.hrm.match.profile']._ensure_profiles(
            self.employee)

    def _candidate(self, request=None):
        run = self.engine.run_match(request or self._request())
        return run.candidate_ids.filtered(
            lambda c: c.employee_id == self.employee)

    def test_somebody_not_staffable_is_removed_with_that_reason(self):
        self._profile().staffable = False
        candidate = self._candidate()
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'not_staffable')

    def test_opting_out_removes_you_and_keeps_your_words(self):
        """The reason is the person's own, so it is shown rather than replaced
        by a generic one."""
        profile = self._profile()
        profile.write({'match_opt_out': True,
                       'opt_out_reason': 'On parental leave until March.'})
        candidate = self._candidate()
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'opted_out')
        self.assertIn('parental leave', candidate.rejection_detail)

    def test_opting_out_without_a_reason_still_says_what_happened(self):
        self._profile().match_opt_out = True
        candidate = self._candidate()
        self.assertEqual(candidate.rejection_code, 'opted_out')
        self.assertTrue(candidate.rejection_detail)

    def test_somebody_who_starts_after_the_work_does_is_removed(self):
        """A start date inside the window is a different case and stays on the
        list; only starting after the work begins is disqualifying."""
        self._profile().available_from = '2026-10-01'
        candidate = self._candidate()
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'available_later')
        self.assertIn('2026-10-01', candidate.rejection_detail)

    def test_a_start_date_in_the_past_does_not_remove_anybody(self):
        self._profile().available_from = '2026-01-01'
        self.assertTrue(self._candidate().eligible)

    def test_a_slot_measured_in_fte_still_has_a_requirement(self):
        """required_hours is optional; a seat can ask for half a person's week
        instead. The gate has to derive the same kind of number either way, or
        an FTE slot silently demands nothing and excludes nobody."""
        request = self._request(required_hours=0.0, fte_ratio=1.0)
        self.env['aic.hrm.match.allocation'].create({
            'employee_id': self.employee.id,
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59',
            'allocated_hours': 40.0, 'state': 'confirmed'})
        candidate = self._candidate(request)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'no_capacity')


@tagged('post_install', '-at_install', 'aic_hrm_match')
class MissingDataCase(MatchCase):
    """A gap in the HR record is not a bad score.

    Scoring an unknown as zero turns "nobody filled this in" into a permanent
    disadvantage for the person it was not filled in for, and the person least
    likely to notice is the one it happens to.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']
        cls.scorer_model = type(cls.env['aic.hrm.match.scorer'])

    def _policy_with(self, code, **criterion_values):
        values = {'code': code, 'name': code.replace('_', ' ').title(),
                  'category': 'availability'}
        values.update(criterion_values)
        criterion = self.env['aic.hrm.match.criterion'].create(values)
        policy = self.env['aic.hrm.match.policy'].create({
            'name': code, 'code': code, 'is_default': True,
            # These cases read the breakdown of people who are deliberately at
            # the bottom, and the default mode keeps presentation lines only
            # for the shortlist. Without this the assertions would pass or fail
            # depending on how many employees the database already had.
            'persist_mode': 'full'})
        self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': criterion.id,
            'weight': 1.0})
        policy.action_activate()
        return policy

    def _register(self, code, scores):
        """Attach a scorer for the duration of one test.

        setattr rather than self.patch, which can only replace an attribute
        that already exists - and a criterion nobody has implemented yet is
        exactly the case under test.
        """
        name = '_score_%s' % code
        setattr(self.scorer_model, name, lambda self, ctx: dict(scores))
        self.addCleanup(delattr, self.scorer_model, name)

    def _request(self):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Missing data',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Dev', 'required_hours': 8.0})
        return request

    def test_a_criterion_with_nothing_to_say_drops_out_of_the_average(self):
        """Not 0.5, not 0: the weight leaves both sides of the fraction, so the
        remaining criteria decide the score between themselves."""
        known = self._make_employee('Has Data')
        unknown = self._make_employee('No Data')
        self._register('invented', {known.id: 1.0, unknown.id: None})
        self._policy_with('invented', normalization='none')

        run = self.engine.run_match(self._request())
        by_employee = {c.employee_id.id: c for c in run.candidate_ids}
        line = by_employee[unknown.id].score_line_ids.filtered(
            lambda l: l.criterion_code == 'invented')
        self.assertTrue(line.is_missing)
        self.assertEqual(by_employee[unknown.id].raw_score, 0.0,
                         'with no criterion left there is nothing to average, '
                         'which is not the same as scoring zero')
        self.assertTrue(by_employee[unknown.id].low_confidence)
        self.assertFalse(by_employee[known.id].low_confidence)

    def test_a_pool_with_no_spread_scores_everybody_the_same(self):
        """min-max normalisation divides by the spread. When everyone is equal
        there is none, and the honest answer is that the criterion does not
        separate them - not a division by zero, and not an arbitrary winner."""
        first = self._make_employee('Same One')
        second = self._make_employee('Same Two')
        self._register('flat', {first.id: 7.0, second.id: 7.0})
        self._policy_with('flat', normalization='minmax')

        run = self.engine.run_match(self._request())
        scores = {c.employee_id.id: c.total_score for c in run.candidate_ids}
        self.assertAlmostEqual(scores[first.id], 0.5, places=6)
        self.assertAlmostEqual(scores[second.id], 0.5, places=6)

    def test_a_criterion_that_cannot_be_normalised_contributes_nothing(self):
        """A saturation of zero makes a ratio undefined. One misconfigured
        criterion must degrade the ranking, not abort a staffing round."""
        employee = self._make_employee('Bad Config')
        self._register('broken', {employee.id: 5.0})
        self._policy_with('broken', normalization='log', saturation_value=0.0)

        run = self.engine.run_match(self._request())
        candidate = run.candidate_ids.filtered(
            lambda c: c.employee_id == employee)
        self.assertEqual(run.state, 'computed')
        self.assertTrue(
            candidate.score_line_ids.filtered(
                lambda l: l.criterion_code == 'broken').is_missing)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CriterionGateCase(MissingDataCase):
    """An eliminating criterion has to eliminate.

    Availability brings its own check, because "no free hours" is a fact about
    the calendar rather than a low score. Every other eliminating criterion is
    a threshold on the normalised score, and if that threshold is never applied
    the criterion is configured to remove people and removes nobody - a gate
    that fails open, which is the one failure mode this design refuses.
    """

    def test_a_criterion_set_to_eliminate_removes_who_it_says_it_will(self):
        strong = self._make_employee('Above The Bar')
        weak = self._make_employee('Below The Bar')
        self._register('clearance', {strong.id: 1.0, weak.id: 0.2})
        self._policy_with('clearance', normalization='none', mode='hard',
                          threshold=0.5)

        run = self.engine.run_match(self._request())
        by_employee = {c.employee_id.id: c for c in run.candidate_ids}
        self.assertTrue(by_employee[strong.id].eligible)
        self.assertFalse(by_employee[weak.id].eligible)
        self.assertEqual(by_employee[weak.id].rejection_code,
                         'criterion_threshold')
        self.assertIn('0.2', by_employee[weak.id].rejection_detail)

    def test_a_criterion_that_only_ranks_never_removes_anybody(self):
        """The same low score, with the criterion left as ranking only. Being
        weak on one count is not the same as being disqualified, and a soft
        criterion that quietly eliminated would make the weights a lie."""
        weak = self._make_employee('Merely Weak')
        self._register('preference', {weak.id: 0.1})
        self._policy_with('preference', normalization='none', mode='soft',
                          threshold=0.5)

        run = self.engine.run_match(self._request())
        candidate = run.candidate_ids.filtered(
            lambda c: c.employee_id == weak)
        self.assertTrue(candidate.eligible)

    def test_a_policy_can_raise_the_bar_without_touching_the_criterion(self):
        """The threshold is a policy decision, so a stricter round overrides it
        on its own line rather than editing a catalogue entry that other
        policies share."""
        employee = self._make_employee('Caught By Override')
        self._register('clearance', {employee.id: 0.6})
        policy = self._policy_with('clearance', normalization='none',
                                   mode='hard', threshold=0.5)
        stricter = policy.action_new_version()
        stricter.line_ids.threshold_override = 0.9
        stricter.action_activate()

        run = self.engine.run_match(self._request())
        candidate = run.candidate_ids.filtered(
            lambda c: c.employee_id == employee)
        self.assertFalse(candidate.eligible)
        self.assertEqual(candidate.rejection_code, 'criterion_threshold')

    def test_a_policy_can_make_a_ranking_criterion_eliminate(self):
        employee = self._make_employee('Caught By Mode')
        self._register('preference', {employee.id: 0.1})
        policy = self._policy_with('preference', normalization='none',
                                   mode='soft', threshold=0.5)
        stricter = policy.action_new_version()
        stricter.line_ids.mode_override = 'hard'
        stricter.action_activate()

        run = self.engine.run_match(self._request())
        self.assertFalse(
            run.candidate_ids.filtered(
                lambda c: c.employee_id == employee).eligible)

    def test_missing_data_is_not_treated_as_failing_the_gate(self):
        """No data is not a low score, so it cannot trip a threshold. Removing
        somebody for a field nobody filled in is the same mistake as scoring
        them zero for it, made irreversible."""
        unknown = self._make_employee('Unrecorded')
        self._register('clearance', {unknown.id: None})
        self._policy_with('clearance', normalization='none', mode='hard',
                          threshold=0.5)

        run = self.engine.run_match(self._request())
        candidate = run.candidate_ids.filtered(
            lambda c: c.employee_id == unknown)
        self.assertTrue(candidate.eligible)
        self.assertTrue(candidate.low_confidence)

    def test_rank_normalisation_spreads_the_pool_instead_of_flattening_it(self):
        """Rank normalisation exists for criteria where the ordering can be
        trusted and the magnitude cannot. Returning the same middling score to
        everybody would make such a criterion carry weight and say nothing,
        which is worse than leaving it out - the weights would still add up."""
        best = self._make_employee('Rank Best')
        middle = self._make_employee('Rank Middle')
        worst = self._make_employee('Rank Worst')
        self._register('reputation',
                       {best.id: 100.0, middle.id: 10.0, worst.id: 1.0})
        self._policy_with('reputation', normalization='rank')

        run = self.engine.run_match(self._request())
        scores = {c.employee_id.id: c.total_score for c in run.candidate_ids}
        self.assertGreater(scores[best.id], scores[middle.id])
        self.assertGreater(scores[middle.id], scores[worst.id])

    def test_every_reason_the_engine_gives_is_one_the_screen_can_group_by(self):
        """The excluded tab groups by this list. A code the engine emits but
        the list does not know reads as an empty group header, so the two must
        not drift apart - and nothing else checks them against each other,
        because Odoo only evaluates the selection when a view asks for it.
        """
        codes = {
            code for code, _label in
            self.env['aic.hrm.match.candidate']._selection_rejection_code()}
        emitted = {'no_capacity', 'not_staffable', 'opted_out',
                   'available_later', 'criterion_threshold'}
        self.assertLessEqual(emitted, codes)

    def test_a_connector_that_reports_on_fewer_people_does_not_zero_the_rest(self):
        """A replaced availability service is free to answer for only the
        people it knows about. The ones it says nothing about have no data,
        which is not the same as having no time - scoring them zero would bury
        them under everyone the connector happened to cover."""
        known = self._make_employee('Covered')
        unknown = self._make_employee('Not Covered')
        availability = self.env['aic.hrm.match.availability']
        original = type(availability).get_breakdown_batch
        self.patch(
            type(availability), 'get_breakdown_batch',
            lambda self, employees, start, end: {
                employee_id: value
                for employee_id, value in original(
                    self, employees, start, end).items()
                if employee_id != unknown.id})

        criterion = self.env['aic.hrm.match.criterion'].create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability', 'normalization': 'ratio'})
        policy = self.env['aic.hrm.match.policy'].create({
            'name': 'Partial', 'code': 'partial_cover', 'is_default': True,
            # Full detail on purpose: the default keeps presentation lines only
            # for the shortlist, and somebody the connector said nothing about
            # ranks last by construction.
            'persist_mode': 'full'})
        self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': criterion.id})
        policy.action_activate()

        run = self.engine.run_match(self._request())
        by_employee = {c.employee_id.id: c for c in run.candidate_ids}
        self.assertTrue(by_employee[unknown.id].low_confidence)
        self.assertTrue(
            by_employee[unknown.id].score_line_ids.filtered(
                lambda l: l.criterion_code == 'availability').is_missing)
        self.assertFalse(by_employee[known.id].low_confidence)

    def test_rank_normalisation_gives_tied_values_the_same_score(self):
        """Ties share a midrank. Breaking them by list order would make the
        score depend on the order Postgres returned the rows in."""
        first = self._make_employee('Tied One')
        second = self._make_employee('Tied Two')
        self._register('reputation', {first.id: 5.0, second.id: 5.0})
        self._policy_with('reputation', normalization='rank')

        run = self.engine.run_match(self._request())
        scores = {c.employee_id.id: c.total_score for c in run.candidate_ids}
        self.assertAlmostEqual(scores[first.id], scores[second.id], places=6)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class RankingGuardCase(MatchCase):
    """What the engine refuses to do."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env['aic.hrm.match.engine']

    def _request(self, with_slot=True):
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Guard', 'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        if with_slot:
            self.env['aic.hrm.match.request.slot'].create({
                'request_id': request.id, 'name': 'Dev',
                'required_hours': 8.0})
        return request

    def test_a_request_with_no_slot_cannot_be_ranked(self):
        """Nothing to fill is not an empty shortlist, it is an unanswerable
        question."""
        with self.assertRaises(UserError):
            self.engine.run_match(self._request(with_slot=False))

    def test_ranking_without_any_policy_is_refused(self):
        """Falling back to some built-in default would rank people under rules
        nobody chose."""
        self.env['aic.hrm.match.policy'].search(
            [('state', '=', 'active')]).write({'state': 'archived'})
        with self.assertRaises(UserError):
            self.engine.run_match(self._request())
