# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Unit tests for the scoring maths. No ORM, no database, no fixtures.

Every criterion in the engine ends up here, so a wrong branch in this file is a
wrong staffing decision that still looks perfectly reasonable on screen. The
cases below are written against the table in the design: each normalisation
kind, both directions, and every degenerate input that has a defined answer.
"""
import math

from odoo.tests import BaseCase, tagged

from odoo.addons.aic_hrm_match.models import utils


@tagged('post_install', '-at_install', 'aic_hrm_match')
class NormalizationCase(BaseCase):

    def test_clamp_bounds_and_passthrough(self):
        self.assertEqual(utils.clamp(-1.0, 0.0, 1.0), 0.0)
        self.assertEqual(utils.clamp(2.0, 0.0, 1.0), 1.0)
        self.assertEqual(utils.clamp(0.4, 0.0, 1.0), 0.4)

    def test_weighted_average_of_pairs(self):
        self.assertAlmostEqual(
            utils.weighted_average([(1.0, 3.0), (0.0, 1.0)]), 0.75)

    def test_weighted_average_of_nothing_is_zero_not_a_crash(self):
        """An employee with no scored criteria is a real state - it must not
        divide by zero halfway through ranking two thousand people."""
        self.assertEqual(utils.weighted_average([]), 0.0)
        self.assertEqual(utils.weighted_average([(0.5, 0.0)]), 0.0)

    def test_weighted_average_ignores_negative_weights(self):
        self.assertAlmostEqual(
            utils.weighted_average([(1.0, 2.0), (0.0, -5.0)]), 1.0)

    # -- none ---------------------------------------------------------------

    def test_none_is_a_clamp_and_respects_direction(self):
        self.assertAlmostEqual(utils.normalize(1.4, kind='none'), 1.0)
        self.assertAlmostEqual(
            utils.normalize(0.25, kind='none', higher_is_better=False), 0.75)

    # -- ratio --------------------------------------------------------------

    def test_ratio_higher_is_value_over_saturation(self):
        self.assertAlmostEqual(
            utils.normalize(32.0, kind='ratio', saturation=64.0), 0.5)
        self.assertAlmostEqual(
            utils.normalize(80.0, kind='ratio', saturation=64.0), 1.0)

    def test_ratio_lower_rewards_small_values_and_survives_zero(self):
        """Cost fit asks "how far under the ceiling", so zero cost is a perfect
        score rather than a division by zero."""
        self.assertAlmostEqual(
            utils.normalize(0.0, kind='ratio', saturation=50.0,
                            higher_is_better=False), 1.0)
        self.assertAlmostEqual(
            utils.normalize(100.0, kind='ratio', saturation=50.0,
                            higher_is_better=False), 0.5)

    def test_ratio_without_a_saturation_is_a_configuration_error(self):
        with self.assertRaises(ValueError):
            utils.normalize(1.0, kind='ratio', saturation=0.0)

    # -- log ----------------------------------------------------------------

    def test_log_has_diminishing_returns(self):
        first = utils.normalize(1.0, kind='log', saturation=3.0)
        second = utils.normalize(2.0, kind='log', saturation=3.0)
        third = utils.normalize(3.0, kind='log', saturation=3.0)
        self.assertGreater(second - first, third - second)
        self.assertAlmostEqual(third, 1.0)

    def test_log_is_clamped_above_saturation(self):
        """Ten engagements with one customer must not score 1.6 and drag the
        weighted total past one."""
        self.assertAlmostEqual(
            utils.normalize(10.0, kind='log', saturation=3.0), 1.0)

    def test_log_treats_negative_input_as_zero(self):
        self.assertAlmostEqual(
            utils.normalize(-5.0, kind='log', saturation=3.0), 0.0)

    # -- minmax -------------------------------------------------------------

    def test_minmax_spreads_the_pool(self):
        self.assertAlmostEqual(
            utils.normalize(5.0, kind='minmax', pool=(0.0, 10.0)), 0.5)

    def test_minmax_without_spread_is_neutral_for_everyone(self):
        """A criterion that cannot tell candidates apart must not decide the
        ranking: giving everyone 1.0 would hand it the whole weight."""
        self.assertAlmostEqual(
            utils.normalize(7.0, kind='minmax', pool=(7.0, 7.0)), 0.5)

    def test_minmax_lower_inverts(self):
        self.assertAlmostEqual(
            utils.normalize(0.0, kind='minmax', pool=(0.0, 10.0),
                            higher_is_better=False), 1.0)

    # -- zscore -------------------------------------------------------------

    def test_zscore_maps_the_mean_to_one_half(self):
        self.assertAlmostEqual(
            utils.normalize(10.0, kind='zscore', pool_stats=(10.0, 2.0)), 0.5)

    def test_zscore_is_monotonic_and_bounded(self):
        low = utils.normalize(4.0, kind='zscore', pool_stats=(10.0, 2.0))
        high = utils.normalize(16.0, kind='zscore', pool_stats=(10.0, 2.0))
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)
        self.assertTrue(0.0 <= low <= 1.0 and 0.0 <= high <= 1.0)

    def test_zscore_without_deviation_is_neutral(self):
        self.assertAlmostEqual(
            utils.normalize(10.0, kind='zscore', pool_stats=(10.0, 0.0)), 0.5)

    # -- rank ---------------------------------------------------------------

    def test_rank_uses_percentiles(self):
        scores = utils.rank_normalize([10.0, 20.0, 30.0])
        self.assertAlmostEqual(scores[2], 5 / 6)
        self.assertAlmostEqual(scores[0], 1 / 6)

    def test_rank_gives_ties_the_same_midrank(self):
        """Two identical values scoring differently would make the ranking
        depend on list order, which is exactly the hidden bias to avoid."""
        scores = utils.rank_normalize([10.0, 10.0, 30.0])
        self.assertAlmostEqual(scores[0], scores[1])

    def test_rank_of_empty_and_single_pools(self):
        self.assertEqual(utils.rank_normalize([]), [])
        self.assertAlmostEqual(utils.rank_normalize([42.0])[0], 0.5)

    def test_rank_lower_inverts(self):
        scores = utils.rank_normalize([10.0, 30.0], higher_is_better=False)
        self.assertGreater(scores[0], scores[1])

    def test_unknown_kind_is_refused_loudly(self):
        with self.assertRaises(ValueError):
            utils.normalize(1.0, kind='vibes')

    def test_rank_through_the_scalar_entry_point_is_refused(self):
        """rank needs every value at once. Silently scoring one value against
        nothing would look like it worked and rank everybody identically."""
        with self.assertRaises(ValueError):
            utils.normalize(1.0, kind='rank')

    def test_minmax_without_a_pool_is_a_configuration_error(self):
        with self.assertRaises(ValueError):
            utils.normalize(1.0, kind='minmax')

    def test_zscore_without_pool_stats_is_a_configuration_error(self):
        with self.assertRaises(ValueError):
            utils.normalize(1.0, kind='zscore')


@tagged('post_install', '-at_install', 'aic_hrm_match')
class DecayCase(BaseCase):
    """Time decay is what keeps a certificate earned in 2015 from outranking
    one earned last year. Half-life semantics, not a linear slide."""

    def test_decay_is_one_inside_the_grace_period(self):
        self.assertAlmostEqual(
            utils.half_life_decay(age_days=100, half_life_days=730,
                                  grace_days=365), 1.0)

    def test_decay_halves_after_one_half_life_past_grace(self):
        value = utils.half_life_decay(age_days=365 + 730, half_life_days=730,
                                      grace_days=365, floor=0.0)
        self.assertAlmostEqual(value, 0.5)

    def test_decay_respects_its_floor(self):
        value = utils.half_life_decay(age_days=100000, half_life_days=730,
                                      grace_days=365, floor=0.6)
        self.assertAlmostEqual(value, 0.6)

    def test_decay_with_a_degenerate_half_life_drops_to_the_floor(self):
        """A half-life of zero is a misconfiguration; answering with the floor
        keeps the ranking running instead of raising inside the scoring loop."""
        self.assertAlmostEqual(
            utils.half_life_decay(age_days=400, half_life_days=0.0,
                                  grace_days=365, floor=0.6), 0.6)

    def test_unknown_age_does_not_penalise(self):
        """Missing data is not evidence of staleness: penalising it would push
        anyone with an incomplete profile permanently down the ranking."""
        self.assertAlmostEqual(utils.half_life_decay(age_days=None), 1.0)

    def test_inverse_document_frequency_favours_rare_expertise(self):
        rare = utils.inverse_document_frequency(holders=1, population=2000)
        common = utils.inverse_document_frequency(holders=1500, population=2000)
        self.assertGreater(rare, common)
        self.assertGreater(common, 0.0)

    def test_idf_handles_a_tag_nobody_holds(self):
        self.assertGreater(
            utils.inverse_document_frequency(holders=0, population=2000), 0.0)

    def test_idf_of_an_empty_population_is_neutral(self):
        self.assertEqual(
            utils.inverse_document_frequency(holders=0, population=0), 0.0)

    def test_ancestor_credit_decays_by_distance(self):
        self.assertAlmostEqual(utils.ancestor_credit(0), 1.0)
        self.assertAlmostEqual(utils.ancestor_credit(1, gamma=0.5), 0.5)
        self.assertAlmostEqual(utils.ancestor_credit(2, gamma=0.5), 0.25)
        self.assertEqual(utils.ancestor_credit(None), 0.0)

    def test_deterministic_salt_is_stable_and_spreads(self):
        """Ties must break the same way on a rerun of the same request, and
        differently across requests - otherwise the same person wins every tie
        forever, which is a bias that compounds silently for years."""
        first = utils.tiebreak_salt('SR-0042', 0, 17)
        self.assertEqual(first, utils.tiebreak_salt('SR-0042', 0, 17))
        self.assertNotEqual(first, utils.tiebreak_salt('SR-0043', 0, 17))
        self.assertNotEqual(first, utils.tiebreak_salt('SR-0042', 1, 17))
        self.assertTrue(0.0 <= first < 1.0)
