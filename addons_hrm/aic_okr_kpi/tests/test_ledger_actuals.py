# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Actuals read from another application, and scores that admit missing data.

A department keeps its revenue on invoices and its costs in the ledger; its
KPIs should read those numbers for every month of the cycle, not only the
month the nightly pull happens to run in. Once pulled, a manager confirms a
month's results in one go. And when only some KPIs have data, the scorecard
must say how much of it is measured instead of scoring the rest as zero.
"""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestPullActuals(KpiCase):
    """Uses check-ins as the external ledger: dated, numeric, allowlistable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['aic.hrm.metric.allowed.model'].create(
            {'model_id': cls.env['ir.model']._get('aic.hrm.checkin').id})
        cls.fy25 = cls.Cycle.create({
            'name': 'FY 2025', 'code': 'LEDGER-FY25', 'cycle_type': 'year',
            'date_start': '2025-01-01', 'date_end': '2025-12-31'})
        cls.q3 = cls.Cycle.create({
            'name': 'Q3 2025', 'code': 'LEDGER-Q3', 'cycle_type': 'quarter',
            'date_start': '2025-07-01', 'date_end': '2025-09-30', 'parent_id': cls.fy25.id})
        cls.july = cls.Cycle.create({
            'name': 'July 2025', 'code': 'LEDGER-07', 'cycle_type': 'month',
            'date_start': '2025-07-01', 'date_end': '2025-07-31', 'parent_id': cls.q3.id})
        ledger_goal = cls._make_objective(name='Ledger', cycle_id=cls.fy25.id)
        cls.ledger = cls._make_kr(ledger_goal, name='Ledger lines', target=1000.0)
        Checkin = cls.env['aic.hrm.checkin']
        for day, value in (('2025-07-10', 30.0), ('2025-07-20', 20.0),
                           ('2025-08-05', 40.0), ('2025-09-30', 5.0)):
            Checkin.create({'kr_id': cls.ledger.id, 'date': day, 'value_current': value})
        cls.source = cls.env['aic.hrm.metric.source'].create({
            'name': 'Ledger total', 'model_id': cls.env['ir.model']._get('aic.hrm.checkin').id,
            'domain': "[('kr_id.name', '=', 'Ledger lines')]", 'field_name': 'value_current',
            'aggregate': 'sum', 'date_field': 'date', 'multiplier': 0.1})

    def results(self, target):
        return [(r.date_from.isoformat(), r.date_to.isoformat(), round(r.actual, 6), r.source, r.state)
                for r in target.period_result_ids.sorted('date_from')]

    def test_monthly_cycle_target_gets_its_month(self):
        target = self._make_target(cycle_id=self.july.id, metric_source_id=self.source.id)
        target.action_pull_metric_actuals()
        self.assertEqual(self.results(target), [('2025-07-01', '2025-07-31', 5.0, 'auto', 'draft')])

    def test_quarterly_target_gets_every_month_of_its_cycle(self):
        target = self._make_target(cycle_id=self.q3.id, metric_source_id=self.source.id)
        target.action_pull_metric_actuals()
        self.assertEqual(self.results(target), [
            ('2025-07-01', '2025-07-31', 5.0, 'auto', 'draft'),
            ('2025-08-01', '2025-08-31', 4.0, 'auto', 'draft'),
            ('2025-09-01', '2025-09-30', 0.5, 'auto', 'draft'),
        ])

    def test_quarterly_frequency_is_one_period(self):
        target = self._make_target(cycle_id=self.q3.id, metric_source_id=self.source.id,
                                   frequency='quarterly')
        target.action_pull_metric_actuals()
        self.assertEqual(self.results(target), [('2025-07-01', '2025-09-30', 9.5, 'auto', 'draft')])

    def test_pulling_again_refreshes_drafts_and_spares_the_rest(self):
        target = self._make_target(cycle_id=self.q3.id, metric_source_id=self.source.id)
        self._add_result(target, '2025-08-01', '2025-08-31', 99.0, state='draft')  # manual
        target.action_pull_metric_actuals()
        july = target.period_result_ids.filtered(lambda r: r.date_from.month == 7)
        july.state = 'confirmed'
        self.env['aic.hrm.checkin'].create(
            {'kr_id': self.ledger.id, 'date': '2025-09-01', 'value_current': 10.0})
        target.action_pull_metric_actuals()
        self.assertEqual(self.results(target), [
            ('2025-07-01', '2025-07-31', 5.0, 'auto', 'confirmed'),
            ('2025-08-01', '2025-08-31', 99.0, 'manual', 'draft'),
            ('2025-09-01', '2025-09-30', 1.5, 'auto', 'draft'),
        ])

    def test_future_months_are_not_pulled(self):
        future = self.Cycle.create({
            'name': 'Next year', 'code': 'LEDGER-FUT', 'cycle_type': 'quarter',
            'date_start': '2999-01-01', 'date_end': '2999-03-31'})
        target = self._make_target(cycle_id=future.id, metric_source_id=self.source.id)
        target.action_pull_metric_actuals()
        self.assertFalse(target.period_result_ids)

    def test_targets_without_source_are_refused(self):
        target = self._make_target(cycle_id=self.july.id)
        with self.assertRaisesRegex(UserError, 'source'):
            target.action_pull_metric_actuals()

    def test_only_hr_administrators_pull(self):
        target = self._make_target(cycle_id=self.july.id, metric_source_id=self.source.id)
        with self.assertRaises(Exception):
            target.with_user(self.manager_user).action_pull_metric_actuals()


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestConfirmPeriodResults(KpiCase):

    def test_confirm_and_reset_a_selection(self):
        target = self._make_target()
        results = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft') | \
            self._add_result(target, '2026-02-01', '2026-02-28', 90.0, state='draft')
        results.with_user(self.manager_user).action_confirm()
        self.assertEqual(set(results.mapped('state')), {'confirmed'})
        self.assertAlmostEqual(target.actual_value, 90.0)
        results.with_user(self.manager_user).action_reset_to_draft()
        self.assertEqual(set(results.mapped('state')), {'draft'})
        self.assertAlmostEqual(target.actual_value, 0.0)

    def test_members_cannot_confirm(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        with self.assertRaises(UserError):
            result.with_user(self.member_user).action_confirm()


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestDataCoverage(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_kpi = cls.Kpi.create({'name': 'Churn', 'code': 'KPI-COV'})

    def _card(self):
        measured = self._make_target(target_value=100.0)
        unmeasured = self._make_target(kpi_id=self.other_kpi.id, target_value=100.0)
        card = self.env['aic.hrm.kpi.assignment'].create({
            'employee_id': self.member_employee.id, 'cycle_id': self.year.id,
            'line_ids': [(0, 0, {'kpi_target_id': measured.id, 'weight': 60.0}),
                         (0, 0, {'kpi_target_id': unmeasured.id, 'weight': 40.0})]})
        return card, measured

    def test_nothing_measured(self):
        card, _measured = self._card()
        self.assertEqual(card.line_ids.mapped('has_actual'), [False, False])
        self.assertAlmostEqual(card.data_coverage, 0.0)
        self.assertAlmostEqual(card.score_covered, 0.0)

    def test_score_on_the_measured_part(self):
        card, measured = self._card()
        self._add_result(measured, '2026-01-01', '2026-01-31', 50.0)
        self.assertEqual(card.line_ids.mapped('has_actual'), [True, False])
        self.assertAlmostEqual(card.score, 0.3)
        self.assertAlmostEqual(card.score_covered, 0.5)
        self.assertAlmostEqual(card.data_coverage, 60.0)

    def test_draft_results_do_not_count_as_measured(self):
        card, measured = self._card()
        self._add_result(measured, '2026-01-01', '2026-01-31', 50.0, state='draft')
        self.assertAlmostEqual(card.data_coverage, 0.0)

    def test_objective_coverage_from_key_results(self):
        objective = self._make_objective()
        checked = self._make_kr(objective, weight=60.0)
        self._make_kr(objective, weight=20.0)
        milestones = self._make_kr(objective, weight=20.0, metric_type='milestone', target=0.0,
                                   milestone_ids=[(0, 0, {'name': 'A', 'weight': 1.0}),
                                                  (0, 0, {'name': 'B', 'weight': 1.0})])
        self.assertAlmostEqual(objective.data_coverage, 0.0)
        self.env['aic.hrm.checkin'].create({'kr_id': checked.id, 'value_current': 50.0})
        self.assertTrue(checked.has_actual)
        self.assertAlmostEqual(objective.data_coverage, 60.0)
        self.assertAlmostEqual(objective.score_covered, 0.5)
        milestones.milestone_ids[0].is_done = True
        self.assertAlmostEqual(objective.data_coverage, 80.0)
        self.assertAlmostEqual(objective.score_covered, (0.5 * 60 + 0.5 * 20) / 80)


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestTrackingTargets(KpiCase):

    def test_tracking_target_shows_actual_without_score(self):
        target = self._make_target(is_tracking=True, target_value=0.0, direction='lower')
        self._add_result(target, '2026-01-01', '2026-01-31', 18.4)
        self.assertAlmostEqual(target.actual_value, 18.4)
        self.assertTrue(target.has_actual)
        self.assertAlmostEqual(target.achievement, 0.0)
        self.assertEqual(target.rag, 'none')

    def test_tracking_target_cannot_be_weighted_on_a_scorecard(self):
        target = self._make_target(is_tracking=True)
        with self.assertRaises(ValidationError):
            self.env['aic.hrm.kpi.assignment'].create({
                'employee_id': self.member_employee.id, 'cycle_id': self.year.id,
                'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': 100.0})]})

    def test_a_target_on_a_scorecard_cannot_become_tracking(self):
        target = self._make_target()
        self.env['aic.hrm.kpi.assignment'].create({
            'employee_id': self.member_employee.id, 'cycle_id': self.year.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': 100.0})]})
        with self.assertRaises(ValidationError):
            target.is_tracking = True
