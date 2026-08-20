# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestProgressReport(OkrCase):
    """The report has to answer "was this on pace THEN", not "is it on pace
    today". Everything below turns on that distinction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env['aic.hrm.progress.report']
        cls.objective = cls.Objective.create({
            'name': 'Ship the platform',
            'code': 'O-REP',
            'cycle_id': cls.year.id,
            'level': 'department',
            'department_id': cls.department.id,
            'weight': 100.0,
        })
        cls.kr = cls.KeyResult.create({
            'name': 'Subscribers onboarded',
            'code': 'KR-REP',
            'objective_id': cls.objective.id,
            'employee_id': cls.member_employee.id,
            'metric_type': 'number',
            'direction': 'higher',
            'baseline': 0.0,
            'target': 100.0,
            'weight': 1.0,
        })

    def _checkin(self, date, value):
        return self.env['aic.hrm.checkin'].create({
            'kr_id': self.kr.id,
            'date': date,
            'value_current': value,
            'confidence': 7,
        })

    # ---- the time series ----

    def test_one_row_per_checkin(self):
        self._checkin('2026-03-31', 20.0)
        self._checkin('2026-06-30', 50.0)
        rows = self.Report.search([('kr_id', '=', self.kr.id)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.mapped('kind'), ['kr', 'kr'])

    def test_expected_is_measured_at_the_date_not_today(self):
        """A check-in on 31 March in a calendar year is a quarter of the
        way through it. Reading the live expected_progress field instead
        would have reported today's elapsed calendar against a figure
        recorded months ago."""
        self._checkin('2026-03-31', 25.0)
        row = self.Report.search([('kr_id', '=', self.kr.id)])
        # 89 days of 364 elapsed on 31 March 2026.
        self.assertAlmostEqual(row.expected, 89 / 364.0, places=3)
        self.assertAlmostEqual(row.achieved, 0.25, places=3)
        self.assertAlmostEqual(row.gap, 0.25 - 89 / 364.0, places=3)

    def test_gap_sign_says_behind_or_ahead(self):
        self._checkin('2026-03-31', 5.0)      # 5% done, ~24% elapsed
        self._checkin('2026-06-30', 90.0)     # 90% done, ~50% elapsed
        rows = self.Report.search([('kr_id', '=', self.kr.id)],
                                  order='date asc')
        self.assertLess(rows[0].gap, 0, 'behind plan must read negative')
        self.assertGreater(rows[1].gap, 0, 'ahead of plan must read positive')

    def test_grouping_by_month_is_available(self):
        """The customer asked for week/month/quarter. Odoo groups a real
        date column natively, which is why the view stores a date rather
        than a pre-built bucket."""
        self._checkin('2026-03-31', 20.0)
        self._checkin('2026-06-30', 50.0)
        groups = self.Report._read_group(
            [('kr_id', '=', self.kr.id)], ['date:month'], ['__count'])
        self.assertEqual(len(groups), 2)

    # ---- dimensions ----

    def test_carries_department_and_owner(self):
        self._checkin('2026-06-30', 40.0)
        row = self.Report.search([('kr_id', '=', self.kr.id)])
        self.assertEqual(row.department_id, self.department)
        self.assertEqual(row.employee_id, self.member_employee)
        self.assertEqual(row.level, 'department')

    def test_groups_by_job_position(self):
        job = self.env['hr.job'].create({'name': 'Growth Lead'})
        self.member_employee.job_id = job
        self._checkin('2026-06-30', 40.0)
        row = self.Report.search([('kr_id', '=', self.kr.id)])
        self.assertEqual(row.job_id, job,
                         'reporting by position needs a real hr.job')

    # ---- KPI side of the union ----

    def _kpi_target(self, direction='higher', target=200.0):
        kpi = self.env['aic.hrm.kpi'].create({
            'name': 'Paying subscribers',
            'code': 'KPI-REP',
            'direction': direction,
            'aggregation': 'last',
            # The model refuses a lower-is-better KPI without a strictly
            # positive target - the achievement formula is undefined at 0.
            'default_target': target or 1.0,
        })
        return self.env['aic.hrm.kpi.target'].create({
            'kpi_id': kpi.id,
            'cycle_id': self.year.id,
            'objective_id': self.objective.id,
            'employee_id': self.member_employee.id,
            'target_value': target,
            'weight': 100.0,
        })

    def test_confirmed_period_results_appear_draft_ones_do_not(self):
        """A draft number is somebody's working note. A management report
        that reads it reports a number nobody stands behind."""
        target = self._kpi_target()
        period = self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id,
            'date_from': '2026-01-01',
            'date_to': '2026-06-30',
            'actual': 100.0,
        })
        self.assertFalse(
            self.Report.search([('kpi_target_id', '=', target.id)]),
            'a draft period result must not reach the report')
        period.state = 'confirmed'
        row = self.Report.search([('kpi_target_id', '=', target.id)])
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(row.achieved, 0.5, places=3)

    def test_lower_is_better_inverts_achievement(self):
        target = self._kpi_target(direction='lower', target=10.0)
        self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id,
            'date_from': '2026-01-01',
            'date_to': '2026-06-30',
            'actual': 8.0,
            'state': 'confirmed',
        })
        row = self.Report.search([('kpi_target_id', '=', target.id)])
        # 8 against a target of 10 is 1.2 before the cap; the cycle caps
        # the scale at 1.0 so an overachiever cannot drag an average past
        # what the scale is defined to mean.
        self.assertAlmostEqual(row.achieved, self.year.score_cap, places=3)

    def test_zero_target_does_not_divide_by_zero(self):
        target = self._kpi_target(target=0.0)
        self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id,
            'date_from': '2026-01-01',
            'date_to': '2026-06-30',
            'actual': 5.0,
            'state': 'confirmed',
        })
        row = self.Report.search([('kpi_target_id', '=', target.id)])
        self.assertEqual(row.achieved, 0.0)

    def test_both_kinds_share_one_table(self):
        self._checkin('2026-06-30', 40.0)
        target = self._kpi_target()
        self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id,
            'date_from': '2026-01-01',
            'date_to': '2026-06-30',
            'actual': 100.0,
            'state': 'confirmed',
        })
        kinds = self.Report.search(
            [('cycle_id', '=', self.year.id)]).mapped('kind')
        self.assertIn('kr', kinds)
        self.assertIn('kpi', kinds)

    def test_single_day_cycle_does_not_divide_by_zero(self):
        """Cycle dates are required, so a cycle is never undated - but it
        can span a single day, and that is a zero-length calendar. Without
        the guard this takes the whole view down, not just one row."""
        self.year.write({'date_start': '2026-06-30',
                         'date_end': '2026-06-30'})
        self._checkin('2026-06-30', 40.0)
        row = self.Report.search([('kr_id', '=', self.kr.id)])
        self.assertEqual(len(row), 1)
        self.assertFalse(row.expected)
        self.assertAlmostEqual(row.achieved, 0.4, places=3)
