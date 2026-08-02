# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_sale')
class TestSalesActuals(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.sales_user = env['res.users'].create({
            'name': 'Sale Rep', 'login': 'kpi_sale_rep',
            'groups_id': [(6, 0, [
                env.ref('base.group_user').id,
                env.ref('sales_team.group_sale_salesman').id,
                env.ref('aic_hrm_base.group_hrm_user').id,
            ])],
        })
        cls.sales_employee = env['hr.employee'].create({
            'name': 'Sale Rep', 'user_id': cls.sales_user.id})
        cls.cycle = env['aic.hrm.cycle'].create({
            'name': 'Sales FY', 'code': 'SALE-FY', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31'})
        cls.kpi = env['aic.hrm.kpi'].create({
            'name': 'Monthly confirmed revenue', 'code': 'SALE-REV',
            'aggregation': 'sum'})
        cls.partner = env['res.partner'].create({'name': 'KPI Customer'})
        cls.product = env['product.product'].create({
            'name': 'KPI Service', 'list_price': 100.0, 'type': 'service'})

    def _make_target(self, source, target_value=1000.0):
        return self.env['aic.hrm.kpi.target'].create({
            'kpi_id': self.kpi.id,
            'cycle_id': self.cycle.id,
            'employee_id': self.sales_employee.id,
            'target_value': target_value,
            'sales_source': source,
        })

    def _make_order(self, qty=3, confirm=True):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'user_id': self.sales_user.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': qty,
                'price_unit': 100.0,
            })],
        })
        if confirm:
            order.action_confirm()
        return order

    def test_order_revenue_actual(self):
        target = self._make_target('order_revenue')
        self._make_order(qty=3)          # 300 confirmed
        self._make_order(qty=2, confirm=False)  # quotation: excluded
        target.action_sync_sales_actuals()
        result = target.period_result_ids
        self.assertEqual(len(result), 1)
        self.assertEqual(result.state, 'draft')
        self.assertEqual(result.source, 'auto')
        self.assertAlmostEqual(result.actual, 300.0)
        # scoring waits for the manager: draft rows never count
        self.assertAlmostEqual(target.achievement, 0.0)
        result.write({'state': 'confirmed'})
        self.assertAlmostEqual(target.actual_value, 300.0)

    def test_quotation_count_actual(self):
        target = self._make_target('quotation_count', target_value=10.0)
        self._make_order(confirm=False)
        self._make_order(confirm=False)
        target.action_sync_sales_actuals()
        self.assertAlmostEqual(target.period_result_ids.actual, 2.0)

    def test_rerun_updates_draft_in_place(self):
        target = self._make_target('order_revenue')
        self._make_order(qty=1)
        target.action_sync_sales_actuals()
        self.assertAlmostEqual(target.period_result_ids.actual, 100.0)
        self._make_order(qty=4)
        self.env['aic.hrm.kpi.target']._cron_sync_sales_actuals()
        self.assertEqual(len(target.period_result_ids), 1,
                         'cron updates the draft row, never duplicates')
        self.assertAlmostEqual(target.period_result_ids.actual, 500.0)

    def test_definition_level_setting_inherited_per_staff(self):
        """Set collection ONCE on the KPI: every staff target inherits."""
        self.kpi.write({'default_sales_source': 'order_revenue'})
        second_rep = self.env['hr.employee'].create({'name': 'Rep Two'})
        target_a = self.env['aic.hrm.kpi.target'].create({
            'kpi_id': self.kpi.id, 'cycle_id': self.cycle.id,
            'employee_id': self.sales_employee.id, 'target_value': 1000.0})
        target_b = self.env['aic.hrm.kpi.target'].create({
            'kpi_id': self.kpi.id, 'cycle_id': self.cycle.id,
            'employee_id': second_rep.id, 'target_value': 1000.0})
        self.assertEqual(target_a.sales_source, 'order_revenue')
        self.assertEqual(target_b.sales_source, 'order_revenue')
        # per-target override survives unrelated writes
        target_b.sales_source = 'off'
        target_b.write({'weight': 20.0})
        self.assertEqual(target_b.sales_source, 'off')

    def test_manual_entry_always_beats_automation(self):
        """A hand-entered figure is never clobbered by the sales cron."""
        target = self._make_target('order_revenue')
        self._make_order(qty=1)  # automation would say 100
        manual = self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id,
            'date_from': fields.Date.context_today(target).replace(day=1),
            'date_to': fields.Date.context_today(target),
            'actual': 999.0,
            'source': 'manual',
            'state': 'draft',
        })
        self.env['aic.hrm.kpi.target']._cron_sync_sales_actuals()
        self.assertAlmostEqual(manual.actual, 999.0,
                               msg='manual always beats automatic')
        self.assertEqual(len(target.period_result_ids), 1,
                         'no duplicate auto row either')

    def test_sales_models_allowlisted(self):
        allowed = self.env['aic.hrm.metric.allowed.model'].search(
            [('model_name', 'in', ('sale.order', 'account.move'))])
        self.assertEqual(len(allowed), 2)
