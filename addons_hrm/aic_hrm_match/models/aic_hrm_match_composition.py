# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Multi-slot assignment composition with Hungarian optimization."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class AicHrmMatchComposition(models.Model):
    """One complete multi-slot assignment proposal."""
    _name = 'aic.hrm.match.composition'
    _description = 'Multi-Slot Staffing Composition'
    _order = 'sequence, id'

    run_id = fields.Many2one(
        'aic.hrm.match.run', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=0)
    line_ids = fields.One2many(
        'aic.hrm.match.composition.line', 'composition_id', string='Assignments')
    coverage_score = fields.Float(compute='_compute_coverage_score', store=True)
    # Required by cost_total below: a Monetary field with no currency beside it
    # is a number nobody can act on, and Odoo refuses to build the model at all
    # rather than rendering it bare.
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True)
    cost_total = fields.Monetary(compute='_compute_cost_total', store=True)
    capacity_ok = fields.Boolean(compute='_compute_capacity_ok', store=True)
    rejection_note = fields.Text()
    is_selected = fields.Boolean(compute='_compute_is_selected')
    company_id = fields.Many2one('res.company', related='run_id.company_id', store=True, index=True)

    @api.depends('sequence')
    def _compute_is_selected(self):
        for comp in self:
            comp.is_selected = (comp.sequence == 0)

    @api.depends('line_ids.marginal_gain')
    def _compute_coverage_score(self):
        for comp in self:
            if not comp.line_ids:
                comp.coverage_score = 0.0
                continue
            gains = [line.marginal_gain for line in comp.line_ids if line.marginal_gain is not None]
            comp.coverage_score = (sum(gains) / len(gains)) if gains else 0.0

    @api.depends('line_ids.assigned_hours')
    def _compute_cost_total(self):
        for comp in self:
            total = 0.0
            for line in comp.line_ids:
                if line.candidate_id and line.candidate_id.employee_id:
                    emp = line.candidate_id.employee_id
                    profile = self.env['aic.hrm.match.profile'].search(
                        [('employee_id', '=', emp.id)], limit=1)
                    rate = profile.cost_hourly if profile else 0.0
                    total += rate * (line.assigned_hours or 0.0)
            comp.cost_total = total

    @api.depends('line_ids.assigned_hours')
    def _compute_capacity_ok(self):
        for comp in self:
            if not comp.line_ids:
                comp.capacity_ok = True
                continue
            ok = True
            for line in comp.line_ids:
                if line.candidate_id and line.candidate_id.free_hours is not None:
                    if line.assigned_hours > line.candidate_id.free_hours:
                        ok = False
                        break
                if line.slot_id and line.slot_id.required_hours:
                    if line.assigned_hours < line.slot_id.required_hours * 0.8:
                        ok = False
                        break
            comp.capacity_ok = ok


class AicHrmMatchCompositionLine(models.Model):
    """One person assigned to one slot in a composition."""
    _name = 'aic.hrm.match.composition.line'
    _description = 'Composition Assignment Line'
    _order = 'sequence, id'

    composition_id = fields.Many2one(
        'aic.hrm.match.composition', required=True, index=True, ondelete='cascade')
    slot_id = fields.Many2one(
        'aic.hrm.match.request.slot', required=True, index=True, ondelete='cascade')
    candidate_id = fields.Many2one(
        'aic.hrm.match.candidate', required=True, index=True, ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', related='candidate_id.employee_id', store=True, index=True, readonly=True)
    assigned_hours = fields.Float(required=True, default=0.0)
    marginal_gain = fields.Float()
    sequence = fields.Integer(default=0)
    company_id = fields.Many2one('res.company', related='composition_id.company_id', store=True, index=True)

    _sql_constraints = [
        ('composition_slot_unique', 'unique(composition_id, slot_id)', 
         'Each slot can only appear once per composition.'),
    ]

    @api.constrains('assigned_hours')
    def _check_assigned_hours(self):
        for line in self:
            if line.assigned_hours < 0.0:
                raise ValidationError(_('Assigned hours must be non-negative.'))
