# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import OkrCase


class KpiCase(OkrCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Kpi = cls.env['aic.hrm.kpi']
        cls.KpiTarget = cls.env['aic.hrm.kpi.target']
        cls.PeriodResult = cls.env['aic.hrm.kpi.period.result']
        cls.kpi_revenue = cls.Kpi.create({
            'name': 'Monthly recurring revenue',
            'code': 'KPI-MRR',
            'direction': 'higher',
            'aggregation': 'last',
            'frequency': 'monthly',
            'unit': 'USD',
        })

    @classmethod
    def _make_target(cls, **kw):
        vals = {
            'kpi_id': cls.kpi_revenue.id,
            'cycle_id': cls.year.id,
            'employee_id': cls.member_employee.id,
            'target_value': 100.0,
            'weight': 10.0,
        }
        vals.update(kw)
        return cls.KpiTarget.create(vals)

    @classmethod
    def _add_result(cls, target, date_from, date_to, actual, state='confirmed'):
        return cls.PeriodResult.create({
            'kpi_target_id': target.id,
            'date_from': date_from,
            'date_to': date_to,
            'actual': actual,
            'state': state,
        })


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKpiLibrary(KpiCase):

    def test_code_unique(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self.Kpi.create({'name': 'Duplicate', 'code': 'KPI-MRR'})

    def test_lower_better_needs_positive_default_target(self):
        with self.assertRaises(ValidationError):
            self.Kpi.create({
                'name': 'Critical bugs', 'code': 'KPI-BUG',
                'direction': 'lower', 'default_target': 0.0,
            })
        kpi = self.Kpi.create({
            'name': 'Critical bugs', 'code': 'KPI-BUG2',
            'direction': 'lower', 'default_target': 3.0,
        })
        self.assertTrue(kpi.id)

    def test_template_flag(self):
        template = self.Kpi.create({
            'name': 'Template KPI', 'code': 'KPI-TPL', 'is_template': True})
        self.assertFalse(template.company_id,
                         "templates are shared across companies")

    def test_iso_inspired_templates_seeded(self):
        templates = self.Kpi.search([('is_template', '=', True),
                                     ('code', 'like', 'HCT-%')])
        self.assertGreaterEqual(
            len(templates), 10,
            "the human-capital template library ships with the module")


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKpiTargetInheritance(KpiCase):

    def test_plain_create_inherits_definition(self):
        # Simulates the import path: create() without any onchange.
        target = self._make_target()
        self.assertEqual(target.direction, 'higher')
        self.assertEqual(target.aggregation, 'last')
        self.assertEqual(target.unit, 'USD')

    def test_override_survives_unrelated_writes(self):
        target = self._make_target()
        target.aggregation = 'average'
        target.write({'weight': 20.0})
        self.assertEqual(target.aggregation, 'average')

    def test_changing_kpi_recomputes_inherited_fields(self):
        # Documented semantics (CX#7): switching the definition always
        # overwrites local overrides.
        other = self.Kpi.create({
            'name': 'Tickets resolved', 'code': 'KPI-TIX',
            'direction': 'higher', 'aggregation': 'sum', 'unit': 'tickets',
        })
        target = self._make_target()
        target.aggregation = 'average'
        target.kpi_id = other
        self.assertEqual(target.aggregation, 'sum')
        self.assertEqual(target.unit, 'tickets')

    def test_unique_per_kpi_cycle_employee(self):
        self._make_target()
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self._make_target()

    def test_lower_better_target_positive(self):
        with self.assertRaises(ValidationError):
            self._make_target(target_value=0.0, direction='lower')


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKpiAchievement(KpiCase):

    def test_aggregation_last(self):
        target = self._make_target()  # last, higher, target 100
        self._add_result(target, '2026-01-01', '2026-01-31', 60)
        self._add_result(target, '2026-02-01', '2026-02-28', 90)
        self.assertAlmostEqual(target.actual_value, 90.0)
        self.assertAlmostEqual(target.achievement, 0.9)

    def test_aggregation_average(self):
        target = self._make_target(aggregation='average')
        self._add_result(target, '2026-01-01', '2026-01-31', 80)
        self._add_result(target, '2026-02-01', '2026-02-28', 120)
        self.assertAlmostEqual(target.actual_value, 100.0)
        self.assertAlmostEqual(target.achievement, 1.0)

    def test_aggregation_sum(self):
        target = self._make_target(aggregation='sum', target_value=200.0)
        self._add_result(target, '2026-01-01', '2026-01-31', 80)
        self._add_result(target, '2026-02-01', '2026-02-28', 70)
        self.assertAlmostEqual(target.actual_value, 150.0)
        self.assertAlmostEqual(target.achievement, 0.75)

    def test_draft_results_excluded(self):
        target = self._make_target(aggregation='sum')
        self._add_result(target, '2026-01-01', '2026-01-31', 50)
        self._add_result(target, '2026-02-01', '2026-02-28', 500, state='draft')
        self.assertAlmostEqual(target.actual_value, 50.0)

    def test_lower_better_achievement_clamped(self):
        target = self._make_target(
            direction='lower', target_value=10.0, aggregation='last')
        self._add_result(target, '2026-01-01', '2026-01-31', 10)
        self.assertAlmostEqual(target.achievement, 1.0)
        result = self._add_result(target, '2026-02-01', '2026-02-28', 30)
        # 2 - 30/10 = -1 -> clamped to 0, never negative on dashboards (OV#9)
        self.assertAlmostEqual(target.achievement, 0.0)
        result.unlink()
        self._add_result(target, '2026-03-01', '2026-03-31', 2)
        # under target -> capped at score cap, not 1.8
        self.assertAlmostEqual(target.achievement, 1.0)

    def test_boolean_direction(self):
        target = self._make_target(direction='boolean', target_value=1.0)
        self._add_result(target, '2026-01-01', '2026-03-31', 0)
        self.assertAlmostEqual(target.achievement, 0.0)
        target.period_result_ids.write({'actual': 1})
        self.assertAlmostEqual(target.achievement, 1.0)

    def test_period_unique_per_target(self):
        target = self._make_target()
        self._add_result(target, '2026-01-01', '2026-01-31', 60)
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self._add_result(target, '2026-01-01', '2026-01-31', 70)

    def test_rag_follows_cycle_profile(self):
        target = self._make_target()
        self._add_result(target, '2026-01-01', '2026-01-31', 80)
        self.assertEqual(target.rag, 'green')


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestKpiGovernance(KpiCase):

    def test_confirmed_target_locks_value(self):
        target = self._make_target()
        target.action_confirm()
        with self.assertRaises(UserError):
            target.write({'target_value': 500.0})
        revision = self.env['aic.hrm.target.revision'].create({
            'res_model': 'aic.hrm.kpi.target',
            'res_id': target.id,
            'field_name': 'target_value',
            'new_value_float': 150.0,
            'reason': 'Board revised the plan upward mid-year.',
        })
        revision.action_approve()
        self.assertAlmostEqual(target.target_value, 150.0)

    def test_forged_revision_context_blocked_for_member(self):
        target = self._make_target()
        target.action_confirm()
        with self.assertRaises(Exception):
            target.with_user(self.member_user).with_context(
                hrm_revision_write=True).write({'target_value': 999.0})

    def test_member_cannot_confirm_target(self):
        target = self._make_target()
        with self.assertRaises(UserError):
            target.with_user(self.member_user).action_confirm()

    def test_unassigned_duplicate_blocked(self):
        self._make_target(employee_id=False)
        with self.assertRaises(ValidationError):
            self._make_target(employee_id=False)

    def test_kpi_company_must_match_cycle(self):
        other_company = self.env['res.company'].create({'name': 'KPI Co 2'})
        foreign_kpi = self.Kpi.create({
            'name': 'Foreign KPI', 'code': 'KPI-FOREIGN',
            'company_id': other_company.id,
        })
        with self.assertRaises(ValidationError):
            self._make_target(kpi_id=foreign_kpi.id)

    def test_template_write_clears_company(self):
        kpi = self.Kpi.create({'name': 'Live KPI', 'code': 'KPI-LIVE'})
        self.assertTrue(kpi.company_id)
        kpi.write({'is_template': True})
        self.assertFalse(kpi.company_id)

    def test_period_move_to_locked_target_blocked(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 60)
        locked_cycle = self.Cycle.create({
            'name': 'KPI Locked', 'code': 'KPI-LOCK2', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })
        locked_target = self._make_target(
            cycle_id=locked_cycle.id, employee_id=self.manager_employee.id)
        locked_cycle.action_open()
        locked_cycle.action_start_review()
        locked_cycle.action_close()
        locked_cycle.action_lock()
        with self.assertRaises(UserError):
            result.write({'kpi_target_id': locked_target.id})

    def test_locked_cycle_blocks_period_results(self):
        target = self._make_target()
        self.year.action_open()
        self.year.action_start_review()
        self.year.action_close()
        self.year.action_lock()
        with self.assertRaises(Exception):
            self._add_result(target, '2026-01-01', '2026-01-31', 10)
