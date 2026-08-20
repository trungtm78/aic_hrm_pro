# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Experience ladders differ per organisation, so they are data.

One company runs Junior / Mid / Senior; another runs five grades with a
principal track beside them. Hard-coding either makes the seniority criterion
either wrong or unusable, so the rungs and their order live in a table.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AicHrmMatchSeniority(models.Model):
    _name = 'aic.hrm.match.seniority'
    _description = 'Staffing Seniority Level'
    _order = 'rank, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    rank = fields.Integer(
        required=True, default=10,
        help="Position on the ladder. Only the ordering matters, so leave gaps "
             "(10, 20, 30) and a grade can be inserted later without "
             "renumbering everything below it.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # NOTE(backport-18): Odoo 18 uses the legacy _sql_constraints list instead.
    _code_uniq = models.Constraint(
        'unique (code)',
        'A seniority level with this code already exists.',
    )

    @api.constrains('rank')
    def _check_rank(self):
        for level in self:
            if level.rank < 0:
                raise ValidationError(_(
                    "Seniority %(name)s: rank cannot be negative. Ranks are "
                    "compared directly, so a negative one would sort below "
                    "having no seniority recorded at all.",
                    name=level.display_name))
