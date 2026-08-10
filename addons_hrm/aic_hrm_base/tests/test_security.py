# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestBaseSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_employee = cls.env['res.users'].create({
            'name': 'Perf User', 'login': 'perf_user',
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('aic_hrm_base.group_hrm_user').id,
            ])],
        })
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Perf Manager', 'login': 'perf_manager',
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('aic_hrm_base.group_hrm_manager').id,
            ])],
        })
        cls.user_admin = cls.env['res.users'].create({
            'name': 'Perf Admin', 'login': 'perf_admin',
            'groups_id': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('aic_hrm_base.group_hrm_admin').id,
            ])],
        })
        cls.cycle = cls.env['aic.hrm.cycle'].create({
            'name': 'FY 2026', 'code': 'FY26-SEC', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })

    def test_admin_implies_manager_implies_user(self):
        self.assertTrue(self.user_admin.has_group('aic_hrm_base.group_hrm_manager'))
        self.assertTrue(self.user_manager.has_group('aic_hrm_base.group_hrm_user'))

    def test_user_reads_but_cannot_write_cycle(self):
        cycle = self.cycle.with_user(self.user_employee)
        self.assertEqual(cycle.name, 'FY 2026')
        with self.assertRaises(AccessError):
            cycle.write({'name': 'Hacked'})

    def test_manager_writes_cycle(self):
        self.cycle.with_user(self.user_manager).write({'name': 'FY 2026 (adjusted)'})
        self.assertEqual(self.cycle.name, 'FY 2026 (adjusted)')

    def test_metric_source_admin_only_write(self):
        rag_model = self.env['ir.model']._get('aic.hrm.rag.profile')
        self.env['aic.hrm.metric.allowed.model'].create({'model_id': rag_model.id})
        vals = {
            'name': 'Sec source', 'model_id': rag_model.id,
            'field_name': 'green_from', 'aggregate': 'count', 'domain': '[]',
        }
        with self.assertRaises(AccessError):
            self.env['aic.hrm.metric.source'].with_user(self.user_manager).create(dict(vals))
        source = self.env['aic.hrm.metric.source'].with_user(self.user_admin).create(vals)
        self.assertTrue(source.id)

    def test_multi_company_rule_on_cycle(self):
        other_company = self.env['res.company'].create({'name': 'Other Co'})
        other_cycle = self.env['aic.hrm.cycle'].create({
            'name': 'Other FY', 'code': 'FY26-OTHER', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
            'company_id': other_company.id,
        })
        visible = self.env['aic.hrm.cycle'].with_user(self.user_employee).search(
            [('code', 'in', ['FY26-SEC', 'FY26-OTHER'])])
        self.assertIn(self.cycle, visible)
        self.assertNotIn(other_cycle, visible)
