# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKrProgress(OkrCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.objective = cls._make_objective()

    def test_number_higher(self):
        kr = self._make_kr(self.objective, baseline=0, target=100, current=40)
        self.assertAlmostEqual(kr.progress, 0.4)
        kr.current = 150
        self.assertAlmostEqual(kr.progress, 1.0, msg="capped at cycle cap")

    def test_number_lower(self):
        kr = self._make_kr(
            self.objective, direction='lower', baseline=40, target=10,
            current=25)
        self.assertAlmostEqual(kr.progress, 0.5)

    def test_percent_type(self):
        kr = self._make_kr(
            self.objective, metric_type='percent', baseline=0, target=95,
            current=47.5)
        self.assertAlmostEqual(kr.progress, 0.5)

    def test_boolean_type(self):
        kr = self._make_kr(
            self.objective, metric_type='boolean', baseline=0, target=1,
            current=0)
        self.assertAlmostEqual(kr.progress, 0.0)
        kr.current = 1
        self.assertAlmostEqual(kr.progress, 1.0)

    def test_milestone_type(self):
        kr = self._make_kr(
            self.objective, metric_type='milestone', milestone_ids=[
                (0, 0, {'name': 'Design sign-off', 'weight': 1}),
                (0, 0, {'name': 'Go-live', 'weight': 3}),
            ])
        self.assertAlmostEqual(kr.progress, 0.0)
        kr.milestone_ids[0].is_done = True
        self.assertAlmostEqual(kr.progress, 0.25)
        kr.milestone_ids[1].is_done = True
        self.assertAlmostEqual(kr.progress, 1.0)

    def test_score_respects_cycle_cap(self):
        capped = self.Cycle.create({
            'name': 'Capped', 'code': 'OKR-CAP', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
            'score_cap': 1.2,
        })
        objective = self._make_objective(cycle_id=capped.id)
        kr = self._make_kr(objective, baseline=0, target=100, current=130)
        self.assertAlmostEqual(kr.progress, 1.2)

    def test_target_equals_baseline_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_kr(self.objective, baseline=50.0, target=50.0)

    def test_rag_follows_cycle_profile(self):
        kr = self._make_kr(self.objective, baseline=0, target=100, current=80)
        self.assertEqual(kr.rag, 'green')
        kr.current = 50
        self.assertEqual(kr.rag, 'amber')
        kr.current = 10
        self.assertEqual(kr.rag, 'red')
