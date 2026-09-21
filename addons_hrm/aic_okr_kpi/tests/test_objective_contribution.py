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


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestCarriersForCycle(KpiCase):
    """The reading the alignment tree needs: one entry per person per key
    result, whatever number of months their scorecards are cut into.

    The report itself is deliberately per cycle, because a director asks it
    "what happened in August". The tree asks a different question - "who is
    carrying this quarterly key result" - and reading the report rows raw
    answered it with the same person three times over, once per month, with
    three different scores. The months belong to the answer, but as one line
    about a person, not as three people.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Contribution = cls.env['aic.hrm.objective.contribution']
        cls.may = cls.Cycle.create({
            'name': 'Tháng 5/2026', 'code': 'CAR-05', 'cycle_type': 'month',
            'date_start': '2026-05-01', 'date_end': '2026-05-31',
            'parent_id': cls.quarter.id})
        cls.june = cls.Cycle.create({
            'name': 'Tháng 6/2026', 'code': 'CAR-06', 'cycle_type': 'month',
            'date_start': '2026-06-01', 'date_end': '2026-06-30',
            'parent_id': cls.quarter.id})
        cls.objective = cls._make_objective(cycle_id=cls.quarter.id, weight=100.0)
        cls.kr = cls._make_kr(cls.objective, baseline=0, target=100, current=0,
                              weight=100.0)

    @classmethod
    def _month_kpi(cls, employee, cycle, weight, actual=None, kpi_code='KPI-CAR'):
        """One KPI serving the key result, on one person's scorecard for one
        month, optionally with its figure confirmed."""
        kpi = cls.Kpi.search([('code', '=', kpi_code)], limit=1) or cls.Kpi.create(
            {'name': kpi_code, 'code': kpi_code, 'direction': 'higher',
             'aggregation': 'last'})
        target = cls.KpiTarget.create({
            'kpi_id': kpi.id, 'cycle_id': cycle.id, 'employee_id': employee.id,
            'target_value': 100.0, 'weight': 100.0, 'kr_id': cls.kr.id})
        if actual is not None:
            cls._add_result(target, cycle.date_start, cycle.date_end, actual)
        card = cls.env['aic.hrm.kpi.assignment'].search(
            [('employee_id', '=', employee.id), ('cycle_id', '=', cycle.id)], limit=1)
        if card:
            card.write({'line_ids': [(0, 0, {'kpi_target_id': target.id,
                                             'weight': weight})]})
        else:
            card = cls.env['aic.hrm.kpi.assignment'].create({
                'employee_id': employee.id, 'cycle_id': cycle.id,
                'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': weight})]})
        return card

    def carriers(self):
        self.env.flush_all()
        return self.Contribution.carriers_for_cycle(self.quarter.id)

    def test_a_person_carrying_the_same_key_result_all_quarter_is_one_entry(self):
        self._month_kpi(self.member_employee, self.may, 100.0, actual=100.0)
        self._month_kpi(self.member_employee, self.june, 100.0, actual=100.0)
        self.assertEqual(len(self.Contribution.search(
            [('employee_id', '=', self.member_employee.id)])), 2,
            'the report keeps one row per month')
        entries = self.carriers()
        self.assertEqual(len(entries), 1, 'the tree reads one carrier')
        [entry] = entries
        self.assertEqual(entry['employee_id'], self.member_employee.id)
        self.assertEqual(entry['kr_id'], self.kr.id)
        self.assertEqual(entry['periods'], 2)
        self.assertEqual(entry['measured_periods'], 2)

    def test_the_weight_is_the_share_of_a_month_not_the_sum_of_the_months(self):
        """Weight is a share of one scorecard, out of 100. Added across
        months it would read 200 out of 100 and mean nothing."""
        self._month_kpi(self.member_employee, self.may, 60.0, actual=100.0)
        self._month_kpi(self.member_employee, self.june, 40.0, actual=100.0)
        [entry] = self.carriers()
        self.assertAlmostEqual(entry['weight'], 50.0,
                               msg='the average month, not the sum')

    def test_a_month_still_without_figures_lowers_the_coverage_not_the_score(self):
        self._month_kpi(self.member_employee, self.may, 100.0, actual=80.0)
        self._month_kpi(self.member_employee, self.june, 100.0)
        [entry] = self.carriers()
        self.assertEqual(entry['periods'], 2)
        self.assertEqual(entry['measured_periods'], 1)
        self.assertAlmostEqual(entry['coverage'], 50.0)
        self.assertAlmostEqual(entry['score_covered'], 0.8, places=4,
                               msg='scored on what was measured')

    def test_nothing_measured_anywhere_scores_nothing(self):
        self._month_kpi(self.member_employee, self.may, 100.0)
        [entry] = self.carriers()
        self.assertEqual(entry['measured_periods'], 0)
        self.assertAlmostEqual(entry['coverage'], 0.0)
        self.assertAlmostEqual(entry['score_covered'], 0.0)

    def test_two_people_on_one_key_result_stay_two_entries(self):
        self._month_kpi(self.member_employee, self.may, 100.0, actual=100.0)
        self._month_kpi(self.manager_employee, self.may, 80.0, actual=100.0)
        entries = self.carriers()
        self.assertEqual(len(entries), 2)
        self.assertEqual({entry['employee_id'] for entry in entries},
                         {self.member_employee.id, self.manager_employee.id})

    def test_entries_come_heaviest_first(self):
        self._month_kpi(self.member_employee, self.may, 40.0, actual=100.0)
        self._month_kpi(self.manager_employee, self.may, 90.0, actual=100.0)
        weights = [entry['weight'] for entry in self.carriers()]
        self.assertEqual(weights, sorted(weights, reverse=True))

    def test_an_objective_of_another_cycle_is_left_out(self):
        other_quarter = self.Cycle.create({
            'name': 'Quý sau', 'code': 'CAR-Q-NEXT', 'cycle_type': 'quarter',
            'date_start': '2026-07-01', 'date_end': '2026-09-30'})
        self._month_kpi(self.member_employee, self.may, 100.0, actual=100.0)
        self.env.flush_all()
        self.assertEqual(self.Contribution.carriers_for_cycle(other_quarter.id), [])

    def test_a_colleague_cannot_read_who_carries_what(self):
        self._month_kpi(self.member_employee, self.may, 100.0, actual=100.0)
        self.env.flush_all()
        with self.assertRaises(Exception):
            self.Contribution.with_user(self.member_user).carriers_for_cycle(
                self.quarter.id)
