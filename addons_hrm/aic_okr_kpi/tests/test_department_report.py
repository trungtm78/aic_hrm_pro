# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The department roll-up a director reads.

KPIs are assigned monthly while objectives are set for the quarter, so a
monthly row that looks for objectives filed on that same month finds none and
reports a department with no strategy. The roll-up therefore takes the
objective score from the row's own cycle or, failing that, from the nearest
cycle above it - and says which cycle it came from. It also carries the score
over measured KPIs and the data coverage, because an average score without
coverage invites the wrong conclusion.
"""
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestDepartmentReport(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env['aic.hrm.department.scorecard']
        cls.q1 = cls.Cycle.create({
            'name': 'Q1 2026', 'code': 'RPT-Q1', 'cycle_type': 'quarter',
            'date_start': '2026-01-01', 'date_end': '2026-03-31', 'parent_id': cls.year.id})
        cls.january = cls.Cycle.create({
            'name': 'January 2026', 'code': 'RPT-01', 'cycle_type': 'month',
            'date_start': '2026-01-01', 'date_end': '2026-01-31', 'parent_id': cls.q1.id})
        # The quarter carries the department objective; the month carries the
        # scorecard - exactly how the customer's data is organised.
        cls.objective = cls._make_objective(cycle_id=cls.q1.id, weight=100.0)
        cls._make_kr(cls.objective, baseline=0, target=100, current=70, weight=100.0)
        target = cls._make_target(cycle_id=cls.january.id, target_value=100.0)
        cls._add_result(target, '2026-01-01', '2026-01-31', 50.0)
        unmeasured = cls._make_target(
            cycle_id=cls.january.id, target_value=100.0,
            kpi_id=cls.Kpi.create({'name': 'Chưa đo', 'code': 'KPI-RPT-2'}).id)
        cls.card = cls.env['aic.hrm.kpi.assignment'].create({
            'employee_id': cls.member_employee.id, 'cycle_id': cls.january.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': 60.0}),
                         (0, 0, {'kpi_target_id': unmeasured.id, 'weight': 40.0})]})

    def row(self, cycle):
        self.env.flush_all()
        return self.Report.search([('cycle_id', '=', cycle.id),
                                   ('department_id', '=', self.department.id)])

    def test_a_monthly_row_shows_the_quarter_objective_and_says_so(self):
        [row] = self.row(self.january)
        self.assertAlmostEqual(row.avg_objective_score, 0.7, places=4)
        self.assertEqual(row.objective_cycle_id, self.q1,
                         'the report must name the cycle the OKR score came from')

    def test_the_row_carries_score_coverage_next_to_the_score(self):
        [row] = self.row(self.january)
        self.assertAlmostEqual(row.avg_composite, 0.3, places=4)
        self.assertAlmostEqual(row.avg_score_covered, 0.5, places=4)
        self.assertAlmostEqual(row.avg_data_coverage, 60.0, places=2)
        self.assertEqual(row.employee_count, 1)

    def test_an_objective_on_the_row_cycle_wins_over_the_parent(self):
        own = self._make_objective(cycle_id=self.january.id, weight=100.0)
        self._make_kr(own, baseline=0, target=100, current=20, weight=100.0)
        [row] = self.row(self.january)
        self.assertAlmostEqual(row.avg_objective_score, 0.2, places=4)
        self.assertEqual(row.objective_cycle_id, self.january)

    def test_a_department_without_objectives_anywhere_reports_none(self):
        other = self.env['hr.department'].create({'name': 'Phòng chưa có OKR'})
        employee = self.env['hr.employee'].create(
            {'name': 'Người mới', 'department_id': other.id})
        target = self._make_target(cycle_id=self.january.id, employee_id=employee.id,
                                   target_value=10.0)
        self.env['aic.hrm.kpi.assignment'].create({
            'employee_id': employee.id, 'cycle_id': self.january.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': 100.0})]})
        self.env.flush_all()
        [row] = self.Report.search([('cycle_id', '=', self.january.id),
                                    ('department_id', '=', other.id)])
        self.assertFalse(row.objective_cycle_id)
        self.assertAlmostEqual(row.avg_objective_score, 0.0)

    def test_the_roll_up_is_for_managers_only(self):
        """Averages of a whole department are not everyone's business."""
        self.env.flush_all()
        with self.assertRaises(Exception):
            self.Report.with_user(self.member_user).search([])
        self.assertTrue(self.Report.with_user(self.manager_user).search([]) is not None)
