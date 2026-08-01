# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AicHrmKpiGroup(models.Model):
    _name = 'aic.hrm.kpi.group'
    _description = 'KPI Group'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one('res.company')
    active = fields.Boolean(default=True)


class AicHrmKpi(models.Model):
    """KPI definition following the professional documentation form:
    definition, formula, unit, direction, aggregation, frequency, data
    source, leading/lagging flag, defaults and RAG override."""
    _name = 'aic.hrm.kpi'
    _description = 'KPI Definition'
    _order = 'code, id'

    name = fields.Char(required=True)
    code = fields.Char(
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'aic.hrm.kpi'),
        required=True, copy=False)
    is_template = fields.Boolean(
        help="Templates are shared across companies and copied into real "
             "KPIs; they never carry live targets themselves.")
    group_id = fields.Many2one('aic.hrm.kpi.group')
    definition = fields.Text(
        help="What exactly does this KPI measure, in business language?")
    formula = fields.Text(
        help="Documented calculation formula (for humans, not executed).")
    unit = fields.Char()
    direction = fields.Selection([
        ('higher', 'Higher is better'),
        ('lower', 'Lower is better'),
        ('boolean', 'Pass / Fail'),
    ], default='higher', required=True)
    aggregation = fields.Selection([
        ('last', 'Final period value'),
        ('average', 'Average of periods'),
        ('sum', 'Cumulative sum'),
    ], default='last', required=True,
        help="How period results combine into the cycle-level actual.")
    frequency = fields.Selection([
        ('monthly', 'Monthly'), ('quarterly', 'Quarterly'),
    ], default='monthly', required=True)
    data_source = fields.Char(
        help="Where the actuals come from (report, system, meeting minutes).")
    flag_type = fields.Selection([
        ('leading', 'Leading indicator'),
        ('lagging', 'Lagging indicator'),
    ], default='lagging')
    default_baseline = fields.Float()
    default_target = fields.Float()
    rag_profile_id = fields.Many2one(
        'aic.hrm.rag.profile',
        help="Optional override of the cycle's RAG thresholds for this KPI.")
    note = fields.Text()
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        help="Empty on shared templates.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'KPI codes must be unique.'),
    ]

    @api.constrains('direction', 'default_target')
    def _check_lower_target(self):
        for kpi in self:
            if kpi.direction == 'lower' and kpi.default_target <= 0.0:
                raise ValidationError(_(
                    "KPI %(name)s: lower-is-better KPIs need a strictly "
                    "positive target — the linear achievement formula is "
                    "undefined at target 0. Model 'zero incidents' goals as "
                    "Pass/Fail instead.", name=kpi.name))

    @api.constrains('is_template', 'company_id')
    def _check_template_shared(self):
        for kpi in self:
            if kpi.is_template and kpi.company_id:
                raise ValidationError(_(
                    "Template KPIs are shared and cannot belong to a "
                    "company."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_template'):
                vals['company_id'] = False
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('is_template'):
            vals['company_id'] = False
        return super().write(vals)
