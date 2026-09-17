# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""How a monthly KPI plan hangs off a quarterly OKR plan.

A department plans key results for the quarter and assigns KPIs month by
month, each KPI serving a named key result. That link, the KPI's wording when
its target is a milestone rather than a number, and zero-tolerance targets are
covered here.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKpiPlanLinks(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.month = cls.Cycle.create({
            'name': 'May 2026', 'code': 'OKR-M05-26', 'cycle_type': 'month',
            'date_start': '2026-05-01', 'date_end': '2026-05-31',
            'parent_id': cls.quarter.id,
        })
        cls.quarter_objective = cls._make_objective(cycle_id=cls.quarter.id)
        cls.quarter_kr = cls._make_kr(cls.quarter_objective)

    # ---- F1: KPI target serves a key result ----

    def test_monthly_target_serves_a_quarterly_key_result(self):
        target = self._make_target(cycle_id=self.month.id, kr_id=self.quarter_kr.id)
        self.assertEqual(target.kr_id, self.quarter_kr)
        self.assertEqual(target.objective_id, self.quarter_objective,
                         'the objective follows the key result')

    def test_key_result_two_levels_up_is_accepted(self):
        year_objective = self._make_objective(cycle_id=self.year.id)
        year_kr = self._make_kr(year_objective)
        target = self._make_target(cycle_id=self.month.id, kr_id=year_kr.id)
        self.assertEqual(target.objective_id, year_objective)

    def test_key_result_from_an_unrelated_cycle_is_refused(self):
        foreign = self._make_kr(self._make_objective(cycle_id=self.other_cycle.id))
        with self.assertRaises(ValidationError):
            self._make_target(cycle_id=self.month.id, kr_id=foreign.id)

    def test_key_result_from_a_child_cycle_is_refused(self):
        month_kr = self._make_kr(self._make_objective(cycle_id=self.month.id))
        with self.assertRaises(ValidationError):
            self._make_target(cycle_id=self.quarter.id, kr_id=month_kr.id)

    def test_objective_and_key_result_must_agree(self):
        other_objective = self._make_objective(cycle_id=self.quarter.id, name='Other')
        with self.assertRaises(ValidationError):
            self._make_target(cycle_id=self.month.id, kr_id=self.quarter_kr.id,
                              objective_id=other_objective.id)

    def test_same_cycle_objective_still_allowed(self):
        objective = self._make_objective(cycle_id=self.year.id)
        target = self._make_target(objective_id=objective.id)
        self.assertEqual(target.objective_id, objective)

    def test_changing_the_key_result_moves_the_objective(self):
        target = self._make_target(cycle_id=self.month.id, kr_id=self.quarter_kr.id)
        second = self._make_objective(cycle_id=self.quarter.id, name='Second')
        second_kr = self._make_kr(second)
        target.kr_id = second_kr
        self.assertEqual(target.objective_id, second)

    def test_rollover_to_next_month_keeps_the_quarterly_key_result(self):
        june = self.Cycle.create({
            'name': 'June 2026', 'code': 'OKR-M06-26', 'cycle_type': 'month',
            'date_start': '2026-06-01', 'date_end': '2026-06-30',
            'parent_id': self.quarter.id,
        })
        self._make_target(cycle_id=self.month.id, kr_id=self.quarter_kr.id,
                          target_note='≥ 49,15 tỷ')
        self.env['aic.hrm.rollover.wizard'].create({
            'source_cycle_id': self.month.id, 'target_cycle_id': june.id,
        }).action_rollover()
        copy = self.KpiTarget.search([('cycle_id', '=', june.id)])
        self.assertEqual(copy.kr_id, self.quarter_kr)
        self.assertEqual(copy.objective_id, self.quarter_objective)
        self.assertEqual(copy.target_note, '≥ 49,15 tỷ')

    def test_rollover_into_an_unrelated_cycle_drops_the_link(self):
        self._make_target(cycle_id=self.month.id, kr_id=self.quarter_kr.id)
        self.env['aic.hrm.rollover.wizard'].create({
            'source_cycle_id': self.month.id, 'target_cycle_id': self.other_cycle.id,
            'copy_objectives': False,
        }).action_rollover()
        copy = self.KpiTarget.search([('cycle_id', '=', self.other_cycle.id)])
        self.assertFalse(copy.kr_id)
        self.assertFalse(copy.objective_id)

    # ---- F4: milestone wording ----

    def test_target_note_keeps_the_assigned_wording(self):
        target = self._make_target(direction='boolean', target_value=1.0,
                                   target_note='LIVE 7/9; ≥ 10 merchant ký')
        self.assertEqual(target.target_note, 'LIVE 7/9; ≥ 10 merchant ký')

    # ---- F3: zero tolerance ----

    def test_zero_tolerance_target_is_valid(self):
        target = self._make_target(direction='lower', target_value=0.0)
        self._add_result(target, '2026-01-01', '2026-01-31', 0)
        self.assertAlmostEqual(target.achievement, 1.0)

    def test_zero_tolerance_breach_scores_nothing(self):
        target = self._make_target(direction='lower', target_value=0.0)
        self._add_result(target, '2026-01-01', '2026-01-31', 1)
        self.assertAlmostEqual(target.achievement, 0.0)

    def test_negative_lower_target_still_refused(self):
        with self.assertRaises(ValidationError):
            self._make_target(direction='lower', target_value=-1.0)
