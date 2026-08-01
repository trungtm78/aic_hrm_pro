# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKpiAssignment(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Assignment = cls.env['aic.hrm.kpi.assignment']
        cls.kpi_quality = cls.Kpi.create({
            'name': 'Release quality', 'code': 'KPI-QLT',
            'direction': 'higher', 'aggregation': 'average',
        })
        cls.target_mrr = cls._make_target_for(cls.member_employee)
        cls.target_qlt = cls.KpiTarget.create({
            'kpi_id': cls.kpi_quality.id,
            'cycle_id': cls.year.id,
            'employee_id': cls.member_employee.id,
            'target_value': 90.0,
            'weight': 10.0,
        })

    @classmethod
    def _make_target_for(cls, employee, **kw):
        vals = {
            'kpi_id': cls.kpi_revenue.id,
            'cycle_id': cls.year.id,
            'employee_id': employee.id,
            'target_value': 100.0,
            'weight': 10.0,
        }
        vals.update(kw)
        return cls.KpiTarget.create(vals)

    def _make_assignment(self, weights=(60.0, 40.0), **kw):
        vals = {
            'employee_id': self.member_employee.id,
            'cycle_id': self.year.id,
            'line_ids': [
                (0, 0, {'kpi_target_id': self.target_mrr.id,
                        'weight': weights[0]}),
                (0, 0, {'kpi_target_id': self.target_qlt.id,
                        'weight': weights[1]}),
            ],
        }
        vals.update(kw)
        return self.Assignment.create(vals)

    def test_total_weight_and_checksum(self):
        assignment = self._make_assignment()
        self.assertAlmostEqual(assignment.total_weight, 100.0)
        self.assertTrue(assignment.weight_ok)
        assignment.line_ids[0].weight = 30.0
        self.assertAlmostEqual(assignment.total_weight, 70.0)
        self.assertFalse(assignment.weight_ok)

    def test_submit_requires_100_percent(self):
        assignment = self._make_assignment(weights=(50.0, 40.0))
        with self.assertRaises(UserError):
            assignment.action_submit()
        assignment.line_ids[0].weight = 60.0
        assignment.action_submit()
        self.assertEqual(assignment.state, 'submitted')

    def test_rounding_tolerated(self):
        third = self._make_target_for(
            self.member_employee, kpi_id=self.Kpi.create({
                'name': 'Third KPI', 'code': 'KPI-3RD'}).id)
        assignment = self.Assignment.create({
            'employee_id': self.member_employee.id,
            'cycle_id': self.year.id,
            'line_ids': [
                (0, 0, {'kpi_target_id': self.target_mrr.id, 'weight': 33.33}),
                (0, 0, {'kpi_target_id': self.target_qlt.id, 'weight': 33.33}),
                (0, 0, {'kpi_target_id': third.id, 'weight': 33.34}),
            ],
        })
        assignment.action_submit()
        self.assertEqual(assignment.state, 'submitted')

    def test_composite_score(self):
        assignment = self._make_assignment()
        self._add_result(self.target_mrr, '2026-01-01', '2026-01-31', 100)
        self._add_result(self.target_qlt, '2026-01-01', '2026-01-31', 45)
        # mrr achievement 1.0 * 60% + qlt achievement 0.5 * 40% = 0.8
        self.assertAlmostEqual(assignment.score, 0.8)

    def test_unique_per_employee_cycle(self):
        self._make_assignment()
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self._make_assignment()

    def test_line_target_same_cycle(self):
        other_cycle_target = self.KpiTarget.create({
            'kpi_id': self.kpi_revenue.id,
            'cycle_id': self.other_cycle.id,
            'employee_id': self.member_employee.id,
            'target_value': 50.0,
        })
        with self.assertRaises(ValidationError):
            self.Assignment.create({
                'employee_id': self.member_employee.id,
                'cycle_id': self.year.id,
                'line_ids': [(0, 0, {
                    'kpi_target_id': other_cycle_target.id, 'weight': 100.0})],
            })

    def test_member_cannot_approve_own_assignment(self):
        assignment = self._make_assignment()
        assignment.action_submit()
        with self.assertRaises(UserError):
            assignment.with_user(self.member_user).action_approve()
        assignment.action_approve()
        self.assertEqual(assignment.state, 'approved')

    def test_department_scorecard_view(self):
        assignment = self._make_assignment()
        self._add_result(self.target_mrr, '2026-01-01', '2026-01-31', 100)
        self.assertTrue(assignment.department_id)
        # SQL views read table state: flush pending ORM writes first
        # (matches how Odoo core tests exercise _auto=False reports).
        self.env.flush_all()
        rows = self.env['aic.hrm.department.scorecard'].search([
            ('cycle_id', '=', self.year.id),
            ('department_id', '=', self.department.id),
        ])
        self.assertTrue(rows)
        self.assertGreaterEqual(rows[0].employee_count, 1)
