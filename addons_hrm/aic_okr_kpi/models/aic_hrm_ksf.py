# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AicHrmKsf(models.Model):
    """Key Success Factor (Rockart's critical success factors).

    The few areas where things MUST go right for the strategy to work.
    KSFs sit between strategy and measurement: each belongs to a BSC
    perspective, objectives declare which factor they drive, KPIs
    declare which factor they measure. A starter catalog ships as data;
    companies extend it with their own factors.
    """
    _name = 'aic.hrm.ksf'
    _description = 'Key Success Factor'
    _order = 'perspective_id, sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    perspective_id = fields.Many2one(
        'aic.hrm.perspective', string='BSC Perspective', index=True,
        ondelete='set null',
        help="Perspective this success factor belongs to.")
    description = fields.Text(
        translate=True,
        help="What 'going right' looks like, in business language.")
    kpi_ids = fields.One2many(
        'aic.hrm.kpi', 'ksf_id', string='Measuring KPIs')
    objective_ids = fields.One2many(
        'aic.hrm.objective', 'ksf_id', string='Driving Objectives')
    company_id = fields.Many2one(
        'res.company',
        help="Empty on the shared built-in catalog; set on "
             "company-specific factors.")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique (code)',
        'Key success factor codes must be unique.',
    )
