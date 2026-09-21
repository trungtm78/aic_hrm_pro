# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Who carries an objective, and what each of them is scoring on it.

The link from a person's KPI to a department objective existed in the data
and nowhere on screen: asked "who is carrying this objective", the system
had no answer. These cases pin what the answer means.

The trap this report has to survive is the customer's own KPI design: the
same revenue figure is deliberately carried by several people at once - not
split between them. So the rows must stay per person, and summing them must
never be mistaken for the department total.
"""
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestObjectiveContribution(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Contribution = cls.env['aic.hrm.objective.contribution']
        cls.month = cls.Cycle.create({
            'name': 'Tháng 5/2026', 'code': 'CTR-05', 'cycle_type': 'month',
            'date_start': '2026-05-01', 'date_end': '2026-05-31',
            'parent_id': cls.quarter.id})
        # The department objective sits on the quarter; the KPIs are monthly.
        cls.objective = cls._make_objective(cycle_id=cls.quarter.id, weight=100.0)
        cls.kr = cls._make_kr(cls.objective, baseline=0, target=100, current=0,
                              weight=100.0)

    @classmethod
    def _target(cls, employee, value=100.0, kpi_code='KPI-CTR', actual=None):
        kpi = cls.Kpi.search([('code', '=', kpi_code)], limit=1) or cls.Kpi.create(
            {'name': kpi_code, 'code': kpi_code, 'direction': 'higher',
             'aggregation': 'last'})
        target = cls.KpiTarget.create({
            'kpi_id': kpi.id, 'cycle_id': cls.month.id, 'employee_id': employee.id,
            'target_value': value, 'weight': 100.0, 'kr_id': cls.kr.id})
        if actual is not None:
            cls._add_result(target, '2026-05-01', '2026-05-31', actual)
        return target

    @classmethod
    def _card(cls, employee, lines):
        return cls.env['aic.hrm.kpi.assignment'].create({
            'employee_id': employee.id, 'cycle_id': cls.month.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': weight})
                         for target, weight in lines]})

    def rows(self, **kw):
        self.env.flush_all()
        domain = [(name, '=', value.id if hasattr(value, 'id') else value)
                  for name, value in kw.items()]
        return self.Contribution.search(domain)

    def test_a_person_carrying_one_objective_appears_with_their_weight(self):
        target = self._target(self.member_employee, actual=80.0)
        self._card(self.member_employee, [(target, 100.0)])
        [row] = self.rows(employee_id=self.member_employee)
        self.assertEqual(row.objective_id, self.objective)
        self.assertEqual(row.kr_id, self.kr)
        self.assertEqual(row.cycle_id, self.month)
        self.assertEqual(row.target_count, 1)
        self.assertAlmostEqual(row.weight, 100.0)
        self.assertAlmostEqual(row.measured_weight, 100.0)
        self.assertAlmostEqual(row.coverage, 100.0)
        self.assertAlmostEqual(row.score_covered, 0.8, places=4)

    def test_the_score_is_read_over_the_part_that_has_figures(self):
        """Half the weight measured at 80% is 80% on what was measured, and
        40% over the whole commitment. Both are shown, and the coverage says
        which is which."""
        measured = self._target(self.member_employee, actual=80.0)
        waiting = self._target(self.member_employee, kpi_code='KPI-CTR-2')
        self._card(self.member_employee, [(measured, 50.0), (waiting, 50.0)])
        [row] = self.rows(employee_id=self.member_employee)
        self.assertAlmostEqual(row.weight, 100.0)
        self.assertAlmostEqual(row.measured_weight, 50.0)
        self.assertAlmostEqual(row.coverage, 50.0)
        self.assertAlmostEqual(row.score_covered, 0.8, places=4)
        self.assertAlmostEqual(row.score, 0.4, places=4)

    def test_a_figure_carried_by_two_people_stays_two_rows(self):
        """Shared accountability, not a split: the customer gives the same
        revenue line to several people. One row each, and the department
        total is not their sum."""
        mine = self._target(self.member_employee, actual=100.0)
        theirs = self._target(self.manager_employee, actual=100.0, kpi_code='KPI-CTR')
        self._card(self.member_employee, [(mine, 100.0)])
        self._card(self.manager_employee, [(theirs, 100.0)])
        rows = self.rows(objective_id=self.objective)
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('employee_id')),
                         {self.member_employee, self.manager_employee})
        for row in rows:
            self.assertAlmostEqual(row.weight, 100.0, msg='per person, not halved')

    def test_a_monthly_kpi_reports_under_the_quarterly_objective(self):
        target = self._target(self.member_employee, actual=50.0)
        self._card(self.member_employee, [(target, 100.0)])
        [row] = self.rows(employee_id=self.member_employee)
        self.assertEqual(row.objective_id.cycle_id, self.quarter)
        self.assertEqual(row.cycle_id, self.month,
                         'the row belongs to the month the work was done in')

    def test_a_kpi_that_serves_no_objective_is_not_on_the_report(self):
        loose = self.KpiTarget.create({
            'kpi_id': self.kpi_revenue.id, 'cycle_id': self.month.id,
            'employee_id': self.member_employee.id, 'target_value': 10.0,
            'weight': 100.0})
        self.assertFalse(loose.objective_id)
        self._card(self.member_employee, [(loose, 100.0)])
        self.assertFalse(self.rows(employee_id=self.member_employee))

    def test_several_kpis_of_one_person_add_up_into_one_row(self):
        first = self._target(self.member_employee, actual=100.0)
        second = self._target(self.member_employee, kpi_code='KPI-CTR-3', actual=0.0)
        self._card(self.member_employee, [(first, 60.0), (second, 40.0)])
        [row] = self.rows(employee_id=self.member_employee)
        self.assertEqual(row.target_count, 2)
        self.assertAlmostEqual(row.weight, 100.0)
        self.assertAlmostEqual(row.score_covered, 0.6, places=4)

    def test_the_report_is_for_managers_only(self):
        """It shows what every colleague committed and scored."""
        self.env.flush_all()
        with self.assertRaises(Exception):
            self.Contribution.with_user(self.member_user).search([])
        self.assertIsNotNone(
            self.Contribution.with_user(self.manager_user).search([]))
