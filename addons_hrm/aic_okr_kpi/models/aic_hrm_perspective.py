# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AicHrmPerspective(models.Model):
    """Strategic perspective, after Kaplan-Norton's Balanced Scorecard.

    Objectives and KPIs tagged by perspective let leadership check the
    portfolio is balanced (not everything financial) and read results
    the BSC way. The four classic perspectives ship as data; companies
    add their own (e.g. Sustainability) freely.
    """
    _name = 'aic.hrm.perspective'
    _description = 'Strategic Perspective (BSC)'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    company_id = fields.Many2one(
        'res.company',
        help="Empty on the shared built-in perspectives; set on "
             "company-specific ones.")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique (code)',
        'Perspective codes must be unique.',
    )
