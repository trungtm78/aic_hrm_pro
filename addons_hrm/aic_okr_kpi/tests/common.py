# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase


class OkrCase(TransactionCase):
    """Shared fixtures: one year cycle with a Q2 child, a small org chart."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cycle = cls.env['aic.hrm.cycle']
        cls.Objective = cls.env['aic.hrm.objective']
        cls.KeyResult = cls.env['aic.hrm.key.result']

        cls.year = cls.Cycle.create({
            'name': 'FY 2026', 'code': 'OKR-FY26', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })
        cls.quarter = cls.Cycle.create({
            'name': 'Q2 2026', 'code': 'OKR-Q2-26', 'cycle_type': 'quarter',
            'date_start': '2026-04-01', 'date_end': '2026-06-30',
            'parent_id': cls.year.id,
        })
        cls.other_cycle = cls.Cycle.create({
            'name': 'FY 2027', 'code': 'OKR-FY27', 'cycle_type': 'year',
            'date_start': '2027-01-01', 'date_end': '2027-12-31',
        })

        cls.department = cls.env['hr.department'].create(
            {'name': 'Digital Products'})
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Mai Manager', 'login': 'okr_manager',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('aic_hrm_base.group_hrm_manager').id,
            ])],
        })
        cls.member_user = cls.env['res.users'].create({
            'name': 'Nam Member', 'login': 'okr_member',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('aic_hrm_base.group_hrm_user').id,
            ])],
        })
        cls.outsider_user = cls.env['res.users'].create({
            'name': 'Out Sider', 'login': 'okr_outsider',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('aic_hrm_base.group_hrm_user').id,
            ])],
        })
        cls.manager_employee = cls.env['hr.employee'].create({
            'name': 'Mai Manager', 'user_id': cls.manager_user.id,
            'department_id': cls.department.id,
        })
        cls.member_employee = cls.env['hr.employee'].create({
            'name': 'Nam Member', 'user_id': cls.member_user.id,
            'department_id': cls.department.id,
            'parent_id': cls.manager_employee.id,
        })
        cls.outsider_employee = cls.env['hr.employee'].create({
            'name': 'Out Sider', 'user_id': cls.outsider_user.id,
        })

    @classmethod
    def _make_objective(cls, **kw):
        vals = {
            'name': 'Grow digital revenue',
            'cycle_id': cls.year.id,
            'level': 'department',
            'department_id': cls.department.id,
            'weight': 25.0,
        }
        vals.update(kw)
        return cls.Objective.create(vals)

    @classmethod
    def _make_kr(cls, objective, **kw):
        vals = {
            'name': 'Reach the target',
            'objective_id': objective.id,
            'metric_type': 'number',
            'direction': 'higher',
            'baseline': 0.0,
            'target': 100.0,
            'weight': 1.0,
        }
        vals.update(kw)
        return cls.KeyResult.create(vals)
