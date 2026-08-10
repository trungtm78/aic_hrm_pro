# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AicHrmFramework(models.Model):
    """A management framework whose dimensions classify goals.

    Balanced Scorecard, Hoshin Kanri, 4DX... each framework brings its
    own set of dimensions (modelled as perspectives). Objectives can be
    read through several frameworks at once - e.g. BSC:Customer and
    Hoshin:Breakthrough on the same objective.
    """
    _name = 'aic.hrm.framework'
    _description = 'Management Framework'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    perspective_ids = fields.One2many(
        'aic.hrm.perspective', 'framework_id', string='Dimensions')
    company_id = fields.Many2one(
        'res.company',
        help="Empty on the shared built-in frameworks; set on "
             "company-specific ones.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Framework codes must be unique.'),
    ]


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
    framework_id = fields.Many2one(
        'aic.hrm.framework', string='Framework', index=True,
        ondelete='set null',
        help="Framework this dimension belongs to (BSC, Hoshin, 4DX...).")
    description = fields.Text(translate=True)
    company_id = fields.Many2one(
        'res.company',
        help="Empty on the shared built-in perspectives; set on "
             "company-specific ones.")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'Perspective codes must be unique.'),
    ]
