# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.addons.aic_hrm_base.models import utils
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestScoringUtils(TransactionCase):
    """Pure scoring math. No ORM involved beyond the test harness."""

    # ---- clamp / safe_div ----

    def test_clamp(self):
        self.assertEqual(utils.clamp(0.5, 0.0, 1.0), 0.5)
        self.assertEqual(utils.clamp(-0.2, 0.0, 1.0), 0.0)
        self.assertEqual(utils.clamp(1.7, 0.0, 1.0), 1.0)

    def test_safe_div(self):
        self.assertEqual(utils.safe_div(10.0, 4.0), 2.5)
        self.assertEqual(utils.safe_div(1.0, 0.0), 0.0)
        self.assertEqual(utils.safe_div(1.0, 0.0, default=1.0), 1.0)

    # ---- progress_linear: number/percent KR normalization ----

    def test_progress_higher_better(self):
        # baseline 0, target 100
        self.assertAlmostEqual(utils.progress_linear(0, 40, 100), 0.4)
        self.assertAlmostEqual(utils.progress_linear(0, 100, 100), 1.0)
        # overachievement clamps at cap
        self.assertAlmostEqual(utils.progress_linear(0, 150, 100), 1.0)
        self.assertAlmostEqual(utils.progress_linear(0, 150, 100, cap=1.2), 1.2)
        # below baseline clamps at 0
        self.assertAlmostEqual(utils.progress_linear(50, 20, 100), 0.0)

    def test_progress_lower_better(self):
        # baseline 40 defects, target 10 defects (lower is better)
        self.assertAlmostEqual(
            utils.progress_linear(40, 25, 10, higher_is_better=False), 0.5)
        self.assertAlmostEqual(
            utils.progress_linear(40, 10, 10, higher_is_better=False), 1.0)
        self.assertAlmostEqual(
            utils.progress_linear(40, 60, 10, higher_is_better=False), 0.0)

    def test_progress_degenerate_target_equals_baseline(self):
        # target == baseline is a configuration error upstream; math returns 0
        self.assertEqual(utils.progress_linear(50, 70, 50), 0.0)

    # ---- achievement: KPI actual vs target ----

    def test_achievement_higher(self):
        self.assertAlmostEqual(utils.achievement(90, 100, 'higher'), 0.9)
        self.assertAlmostEqual(utils.achievement(120, 100, 'higher'), 1.0)
        self.assertAlmostEqual(
            utils.achievement(120, 100, 'higher', cap=1.5), 1.2)
        self.assertEqual(utils.achievement(50, 0, 'higher'), 0.0)

    def test_achievement_lower(self):
        # linear: 2 - actual/target, clamped [0, cap]
        self.assertAlmostEqual(utils.achievement(100, 100, 'lower'), 1.0)
        self.assertAlmostEqual(utils.achievement(150, 100, 'lower'), 0.5)
        self.assertAlmostEqual(utils.achievement(250, 100, 'lower'), 0.0)
        # under target clamps at cap, never above
        self.assertAlmostEqual(utils.achievement(50, 100, 'lower'), 1.0)
        self.assertEqual(utils.achievement(10, 0, 'lower'), 0.0)

    def test_achievement_boolean(self):
        self.assertEqual(utils.achievement(1, 1, 'boolean'), 1.0)
        self.assertEqual(utils.achievement(0, 1, 'boolean'), 0.0)
        self.assertEqual(utils.achievement(2, 1, 'boolean'), 1.0)

    # ---- weighted_average ----

    def test_weighted_average(self):
        self.assertAlmostEqual(
            utils.weighted_average([(1.0, 60), (0.5, 40)]), 0.8)
        self.assertEqual(utils.weighted_average([]), 0.0)
        self.assertEqual(utils.weighted_average([(0.7, 0)]), 0.0)
