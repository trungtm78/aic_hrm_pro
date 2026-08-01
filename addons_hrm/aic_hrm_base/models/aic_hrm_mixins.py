# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AicHrmOwnerMixin(models.AbstractModel):
    """Shared owner fields: employee, their department and manager."""
    _name = 'aic.hrm.owner.mixin'
    _description = 'Owner Mixin'

    employee_id = fields.Many2one('hr.employee', string='Owner', index=True)
    department_id = fields.Many2one(
        'hr.department', compute='_compute_owner_org', store=True,
        readonly=False, index=True)
    manager_id = fields.Many2one(
        'hr.employee', string='Manager',
        compute='_compute_owner_org', store=True, readonly=False)

    @api.depends('employee_id')
    def _compute_owner_org(self):
        for record in self:
            if record.employee_id:
                record.department_id = record.employee_id.department_id
                record.manager_id = record.employee_id.parent_id


class AicHrmScoringMixin(models.AbstractModel):
    """Shared normalized score + RAG band pair.

    Concrete models implement ``_compute_score`` (storing ``score``) and
    declare their RAG profile resolution order in ``_get_rag_profile``.
    """
    _name = 'aic.hrm.scoring.mixin'
    _description = 'Scoring Mixin'

    score = fields.Float(
        readonly=True, aggregator='avg',
        help="Normalized 0..cap score.")
    rag = fields.Selection([
        ('green', 'Green'),
        ('amber', 'Amber'),
        ('red', 'Red'),
        ('none', 'Not scored'),
    ], compute='_compute_rag', store=True, string='RAG')

    def _get_rag_profile(self):
        """Return the RAG profile to resolve against; models override."""
        self.ensure_one()
        return self.env.ref('aic_hrm_base.rag_profile_default',
                            raise_if_not_found=False)

    @api.depends('score')
    def _compute_rag(self):
        for record in self:
            profile = record._get_rag_profile()
            record.rag = profile.resolve(record.score) if profile else 'none'
