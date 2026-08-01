# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestObjectiveScoring(OkrCase):

    def test_weighted_rollup(self):
        objective = self._make_objective()
        self._make_kr(objective, weight=60, baseline=0, target=100, current=100)
        self._make_kr(objective, weight=40, baseline=0, target=100, current=50)
        self.assertAlmostEqual(objective.score, 0.8)
        self.assertEqual(objective.kr_count, 2)

    def test_no_krs_scores_zero(self):
        objective = self._make_objective()
        self.assertAlmostEqual(objective.score, 0.0)

    def test_zero_weights_safe(self):
        objective = self._make_objective()
        self._make_kr(objective, weight=0, current=100)
        self.assertAlmostEqual(objective.score, 0.0)

    def test_weight_bounds(self):
        with self.assertRaises(ValidationError):
            self._make_objective(weight=120.0)
        with self.assertRaises(ValidationError):
            self._make_objective(weight=-5.0)

    def test_alignment_same_cycle(self):
        parent = self._make_objective(name='Company bet', level='company')
        child = self._make_objective(name='Dept slice', parent_id=parent.id)
        self.assertEqual(child.parent_id, parent)

    def test_alignment_quarter_to_year(self):
        annual = self._make_objective(name='Annual bet', level='company')
        quarterly = self._make_objective(
            name='Q2 slice', cycle_id=self.quarter.id, parent_id=annual.id)
        self.assertEqual(quarterly.parent_id, annual)

    def test_alignment_unrelated_cycle_rejected(self):
        annual = self._make_objective(name='Annual bet')
        with self.assertRaises(ValidationError):
            self._make_objective(
                name='2027 orphan', cycle_id=self.other_cycle.id,
                parent_id=annual.id)

    def test_contributes_to_same_rule(self):
        annual = self._make_objective(name='Annual bet')
        quarterly = self._make_objective(
            name='Q2 helper', cycle_id=self.quarter.id,
            contributes_to_ids=[(4, annual.id)])
        self.assertIn(annual, quarterly.contributes_to_ids)
        with self.assertRaises(ValidationError):
            self._make_objective(
                name='2027 helper', cycle_id=self.other_cycle.id,
                contributes_to_ids=[(4, annual.id)])

    def test_no_parent_recursion(self):
        objective = self._make_objective()
        with self.assertRaises(ValidationError):
            objective.parent_id = objective

    def test_cross_cycle_rollup_includes_children(self):
        annual = self._make_objective(name='Annual bet')
        self._make_kr(annual, weight=1, baseline=0, target=100, current=50)
        quarterly = self._make_objective(
            name='Q2 slice', cycle_id=self.quarter.id, parent_id=annual.id,
            weight=1.0)
        self._make_kr(quarterly, weight=1, baseline=0, target=10, current=10)
        # One weighted pool: own KR (score 0.5, weight 1) + child objective
        # (score 1.0, weight 1) -> 0.75.
        self.assertAlmostEqual(quarterly.score, 1.0)
        self.assertAlmostEqual(annual.score, 0.75,
                               msg="child objectives roll up next to own KRs")

    def test_locked_cycle_blocks_new_goals(self):
        cycle = self.Cycle.create({
            'name': 'Lockable', 'code': 'OKR-LOCK', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })
        objective = self._make_objective(cycle_id=cycle.id)
        cycle.action_open()
        cycle.action_start_review()
        cycle.action_close()
        cycle.action_lock()
        with self.assertRaises(Exception):
            self._make_objective(cycle_id=cycle.id, name='Too late')
        with self.assertRaises(Exception):
            self._make_kr(objective)
