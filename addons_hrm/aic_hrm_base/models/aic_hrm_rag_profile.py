# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AicHrmRagProfile(models.Model):
    _name = 'aic.hrm.rag.profile'
    _description = 'RAG Threshold Profile'
    _order = 'name'

    name = fields.Char(required=True)
    green_from = fields.Float(
        default=0.7, required=True,
        help="Scores at or above this value resolve to green.")
    amber_from = fields.Float(
        default=0.4, required=True,
        help="Scores at or above this value (and below green) resolve to amber.")
    company_id = fields.Many2one(
        'res.company',
        help="Leave empty to share the profile across all companies.")
    active = fields.Boolean(default=True)

    @api.constrains('green_from', 'amber_from')
    def _check_threshold_ordering(self):
        for profile in self:
            if not (0.0 <= profile.amber_from < profile.green_from <= 1.0):
                raise ValidationError(_(
                    "RAG thresholds must satisfy 0 <= amber < green <= 1 "
                    "(got amber=%(amber)s, green=%(green)s).",
                    amber=profile.amber_from, green=profile.green_from))

    def resolve(self, score):
        """Map a 0..1 score to its RAG band: 'green' | 'amber' | 'red'."""
        self.ensure_one()
        if score >= self.green_from:
            return 'green'
        if score >= self.amber_from:
            return 'amber'
        return 'red'
