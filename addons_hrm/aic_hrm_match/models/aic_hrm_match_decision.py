# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Decision log — immutable audit trail of staffing selections."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AicHrmMatchDecision(models.Model):
    _name = 'aic.hrm.match.decision'
    _description = 'Staffing Decision'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC'

    # Immutable references
    request_id = fields.Many2one('aic.hrm.match.request', 'Request', required=True, ondelete='restrict')
    slot_id = fields.Many2one('aic.hrm.match.request.slot', 'Slot', ondelete='restrict')
    run_id = fields.Many2one('aic.hrm.match.run', 'Ranking Run', required=True, ondelete='restrict')
    candidate_id = fields.Many2one('aic.hrm.match.candidate', 'Candidate', ondelete='set null')
    employee_id = fields.Many2one('hr.employee', 'Employee', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', 'Company', related='request_id.request_company_id', store=True)

    # Metadata
    decided_by_id = fields.Many2one('res.users', 'Decided By', readonly=True, default=lambda self: self.env.user)
    decided_date = fields.Datetime('Decided At', readonly=True, default=fields.Datetime.now)
    
    # Decision type
    decision_type = fields.Selection([
        ('ranked', 'From Ranking'),
        ('override', 'Override'),
        ('waived', 'Waived Hard Gate'),
    ], 'Type', required=True, default='ranked')
    
    # Override metadata
    is_override = fields.Boolean('Overridden', compute='_compute_is_override', store=True)
    override_category = fields.Selection([
        ('rank', 'Lower Rank Selected'),
        ('hard_gate', 'Hard Gate Waved'),
        ('cost', 'Cost Limit Exceeded'),
        ('skill_gap', 'Skill Gap Accepted'),
        ('capacity', 'Capacity Risk'),
        ('other', 'Other'),
    ], 'Override Reason Category')
    override_reason = fields.Text('Override Reason', tracking=True)
    
    # Snapshot at decision time
    rank_at_decision = fields.Integer('Rank When Decided', readonly=True)
    score_at_decision = fields.Float('Score When Decided', readonly=True, digits=(5, 4))
    rank_delta = fields.Integer('Rank Change', compute='_compute_rank_delta', store=True)
    weights_snapshot = fields.Text('Policy Weights', readonly=True)

    # Allocations created from this decision
    allocation_ids = fields.One2many('aic.hrm.match.allocation', 'decision_id', 'Allocations', readonly=True)
    
    # State machine
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], 'State', default='draft', tracking=True)
    
    # Constraints
    _sql_constraints = [
        ('request_slot_employee_uniq', 'unique(request_id, slot_id, employee_id)', 
         'Only one decision per employee per slot'),
    ]

    @api.depends('decision_type', 'rank_at_decision')
    def _compute_is_override(self):
        for rec in self:
            rec.is_override = rec.decision_type != 'ranked' or (rec.rank_at_decision or 999) > 1

    @api.depends('rank_at_decision')
    def _compute_rank_delta(self):
        for rec in self:
            if rec.candidate_id and rec.rank_at_decision:
                rec.rank_delta = rec.candidate_id.rank - rec.rank_at_decision
            else:
                rec.rank_delta = 0

    def write(self, vals):
        """Confirmed decisions are immutable."""
        for rec in self:
            if rec.state == 'confirmed' and any(k not in ('notes',) for k in vals):
                raise UserError(_('Confirmed decisions cannot be edited. Create a new decision instead.'))
        return super().write(vals)

    def unlink(self):
        """Decisions are audit records and must never be deleted."""
        raise UserError(_('Decisions cannot be deleted (audit trail).'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            candidate = self.env['aic.hrm.match.candidate'].browse(vals.get('candidate_id'))
            if candidate:
                vals['rank_at_decision'] = candidate.rank
                vals['score_at_decision'] = candidate.total_score
        
        recs = super().create(vals_list)
        
        for rec in recs:
            if rec.is_override and not rec.override_reason:
                raise UserError(_('Override reason is required when selecting non-top candidate.'))
        
        return recs
    def action_confirm(self):
        """Confirm the decision and book the time it commits.

        The booking is the point. A decision that records who was chosen but
        leaves their calendar untouched means the next planner ranks them as
        free, books them again, and neither clash guard nor capacity report
        ever sees a problem - because as far as the data is concerned, nothing
        was ever committed.

        Idempotent: confirming twice must not book the same stretch of time
        twice, and a planner double-clicking is not an unusual event.
        """
        for rec in self:
            if rec.state == 'confirmed':
                continue
            if not rec.allocation_ids:
                rec._create_allocation()
            rec.state = 'confirmed'
            rec.allocation_ids.filtered(
                lambda a: a.state == 'draft').write({'state': 'confirmed'})
            rec.message_post(body=_('Decision confirmed by %(user)s',
                user=self.env.user.name))

    def _create_allocation(self):
        """Book the seat's window for the person chosen.

        The slot's own window when it has one, the request's otherwise: a seat
        may run for part of a longer engagement, and booking the whole
        engagement would take time nobody agreed to give.
        """
        self.ensure_one()
        slot = self.slot_id
        request = self.request_id
        hours = slot.required_hours
        if not hours and slot.fte_ratio:
            hours = slot.fte_ratio * self.env[
                'aic.hrm.match.availability'].get_gross_hours(
                    self.employee_id,
                    slot.date_start or request.date_start,
                    slot.date_end or request.date_end)
        return self.env['aic.hrm.match.allocation'].create({
            'employee_id': self.employee_id.id,
            'date_start': slot.date_start or request.date_start,
            'date_end': slot.date_end or request.date_end,
            'allocated_hours': hours,
            'decision_id': self.id,
            'task_id': request.task_id.id,
            'project_id': request.project_id.id,
            'partner_id': request.partner_id.id,
            'state': 'draft',
        })

    def action_cancel(self):
        """Cancel the decision — revert state to draft."""
        for rec in self:
            if rec.allocation_ids.filtered(lambda a: a.state in ('confirmed', 'done')):
                raise UserError(_('Cannot cancel: allocations already confirmed.'))
            rec.state = 'draft'
            rec.message_post(body=_('Decision cancelled by %(user)s',
                user=self.env.user.name))

