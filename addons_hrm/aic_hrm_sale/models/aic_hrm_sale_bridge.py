# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


_SALES_SOURCES = [
    ('off', 'Manual figures'),
    ('quotation_count', 'Quotations created'),
    ('order_count', 'Orders confirmed'),
    ('order_revenue', 'Confirmed order revenue (untaxed)'),
    ('invoiced_revenue', 'Invoiced revenue (untaxed, posted)'),
]


class AicHrmKpi(models.Model):
    _inherit = 'aic.hrm.kpi'

    default_sales_source = fields.Selection(
        _SALES_SOURCES, default='off', required=True,
        string='Sales Collection',
        help="Set ONCE on the KPI definition: every target assigned to any "
             "employee inherits this collection mode automatically.")


class AicHrmKpiTarget(models.Model):
    _inherit = 'aic.hrm.kpi.target'

    sales_source = fields.Selection(
        _SALES_SOURCES, compute='_compute_sales_source', store=True,
        readonly=False, required=True, precompute=True,
        help="Automatic monthly actuals pulled from the owner's sales "
             "documents. Inherited from the KPI definition; override per "
             "target when needed. Results land as DRAFT period rows - a "
             "manager still confirms them before they score.")

    @api.depends('kpi_id')
    def _compute_sales_source(self):
        for target in self:
            target.sales_source = (target.kpi_id.default_sales_source
                                   or 'off')

    def _sales_value(self, date_from, date_to):
        """Aggregate the owner's sales documents for one period."""
        self.ensure_one()
        user = self.employee_id.user_id
        if not user:
            return 0.0
        if self.sales_source == 'quotation_count':
            return float(self.env['sale.order'].search_count([
                ('user_id', '=', user.id),
                ('create_date', '>=', fields.Datetime.to_datetime(
                    str(date_from))),
                ('create_date', '<=', fields.Datetime.to_datetime(
                    f'{date_to} 23:59:59')),
            ]))
        if self.sales_source in ('order_count', 'order_revenue'):
            domain = [
                ('user_id', '=', user.id),
                ('state', '=', 'sale'),
                ('date_order', '>=', fields.Datetime.to_datetime(
                    str(date_from))),
                ('date_order', '<=', fields.Datetime.to_datetime(
                    f'{date_to} 23:59:59')),
            ]
            if self.sales_source == 'order_count':
                return float(self.env['sale.order'].search_count(domain))
            result = self.env['sale.order']._read_group(
                domain, [], ['amount_untaxed:sum'])
            return float(result[0][0] or 0.0)
        if self.sales_source == 'invoiced_revenue':
            result = self.env['account.move']._read_group([
                ('invoice_user_id', '=', user.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', date_from),
                ('invoice_date', '<=', date_to),
            ], [], ['amount_untaxed_signed:sum'])
            return float(result[0][0] or 0.0)
        return 0.0

    def action_sync_sales_actuals(self):
        """Upsert this month's DRAFT period result from sales documents."""
        PeriodResult = self.env['aic.hrm.kpi.period.result']
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        month_end = (month_start + relativedelta(months=1)
                     - relativedelta(days=1))
        for target in self.filtered(lambda t: t.sales_source != 'off'):
            value = target._sales_value(month_start, month_end)
            existing = PeriodResult.search([
                ('kpi_target_id', '=', target.id),
                ('date_from', '<=', month_end),
                ('date_to', '>=', month_start),
            ], limit=1)
            if existing:
                # Manual always beats automatic: only rows the automation
                # itself created (source=auto) may be refreshed.
                if existing.state == 'draft' and existing.source == 'auto':
                    existing.write({'actual': value})
            else:
                PeriodResult.create({
                    'kpi_target_id': target.id,
                    'date_from': month_start,
                    'date_to': month_end,
                    'actual': value,
                    'source': 'auto',
                    'state': 'draft',
                })

    @api.model
    def _cron_sync_sales_actuals(self):
        self.search([
            ('sales_source', '!=', 'off'),
            ('cycle_id.state', 'in', ('draft', 'open')),
        ]).action_sync_sales_actuals()
