# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What a director reads on the cockpit, and what it must not claim.

Three readings on the leadership desk were wrong in the same direction - they
made a department with no figures look measured and judged:

* an unweighted average put a 50% objective on a par with a 10% one, so the
  department's 35% showed as 17,5%;
* "fresh check-ins" counted a key result nobody had ever checked in as fresh,
  reading 100% while nine of ten had no update at all;
* an objective with no figures scored 0 and turned red, which reads as "off
  track" when it means "not measured yet".

The arithmetic for the first two lives in the browser; the data the cockpit
reads, and the third reading, are settled here.
"""
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestCockpitReading(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.quarter_objectives = cls.Cycle.create({
            'name': 'Q4 2026', 'code': 'COCK-Q4', 'cycle_type': 'quarter',
            'date_start': '2026-10-01', 'date_end': '2026-12-31',
            'parent_id': cls.year.id})
        # A department with one measured objective at 50% weight and three
        # unmeasured ones - the customer's own shape.
        cls.measured = cls._make_objective(
            name='Doanh thu', cycle_id=cls.quarter_objectives.id, weight=50.0)
        cls._make_kr(cls.measured, baseline=0, target=100, current=70, weight=100.0)
        cls.unmeasured = []
        for index, weight in enumerate((20.0, 20.0, 10.0)):
            objective = cls._make_objective(
                name=f'Chưa đo {index}', cycle_id=cls.quarter_objectives.id, weight=weight)
            cls._make_kr(objective, baseline=0, target=100, current=0, weight=100.0)
            cls.unmeasured.append(objective)

    def test_an_objective_with_no_figures_is_not_scored_rather_than_off_track(self):
        for objective in self.unmeasured:
            self.assertAlmostEqual(objective.data_coverage, 0.0)
            self.assertEqual(objective.rag, 'none',
                             'no figures means not scored, not off track')
        self.assertEqual(self.measured.rag, 'green')

    def test_a_key_result_without_progress_is_not_scored_either(self):
        kr = self.unmeasured[0].kr_ids
        self.assertFalse(kr.has_actual)
        self.assertEqual(kr.rag, 'none')

    def test_a_scorecard_with_no_figures_is_not_scored(self):
        target = self._make_target(target_value=100.0)
        card = self.env['aic.hrm.kpi.assignment'].create({
            'employee_id': self.member_employee.id, 'cycle_id': self.year.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': 100.0})]})
        self.assertEqual(card.rag, 'none')
        self._add_result(target, '2026-01-01', '2026-01-31', 20.0)
        card.invalidate_recordset()
        self.assertEqual(card.rag, 'red', 'a measured 20% really is off track')

    def test_an_unmeasured_kpi_target_is_not_scored(self):
        target = self._make_target(target_value=100.0)
        self.assertEqual(target.rag, 'none')
        self._add_result(target, '2026-01-01', '2026-01-31', 95.0)
        target.invalidate_recordset()
        self.assertEqual(target.rag, 'green')

    def test_the_cockpit_reads_the_weights_and_the_coverage(self):
        """The browser needs weight and coverage to state the cycle's health;
        both must be readable on the objective."""
        fields = self.env['aic.hrm.objective'].fields_get(
            ['weight', 'score', 'data_coverage', 'rag', 'objective_type'])
        for name in ('weight', 'score', 'data_coverage', 'rag', 'objective_type'):
            self.assertIn(name, fields)
        objectives = self.env['aic.hrm.objective'].search_read(
            [('cycle_id', '=', self.quarter_objectives.id)],
            ['weight', 'score', 'data_coverage'])
        weighted = (sum(row['score'] * row['weight'] for row in objectives)
                    / sum(row['weight'] for row in objectives))
        self.assertAlmostEqual(weighted, 0.35, places=4,
                               msg='what the cockpit must show for this cycle')
        measured = [row for row in objectives if row['data_coverage']]
        self.assertEqual(len(measured), 1, 'and it must say three are unmeasured')

    def test_check_in_freshness_can_tell_never_from_stale(self):
        """`is_stale` only flags a key result that has a check-in and let it
        get old; the cockpit must count the ones never checked in too, which
        it can only do from has_actual / last_checkin_date."""
        kr = self.unmeasured[0].kr_ids
        self.assertFalse(kr.is_stale)
        self.assertFalse(kr.last_checkin_date)
        self.assertFalse(kr.has_actual)
        self.env['aic.hrm.checkin'].create({'kr_id': kr.id, 'value_current': 10.0})
        kr.invalidate_recordset()
        self.assertTrue(kr.has_actual)
        self.assertTrue(kr.last_checkin_date)
