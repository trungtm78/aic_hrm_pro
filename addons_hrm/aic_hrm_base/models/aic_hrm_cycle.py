# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Days per check-in frequency; stale threshold defaults to twice the interval.
_FREQUENCY_DAYS = {'weekly': 7, 'biweekly': 14, 'monthly': 30}

# state -> states it may transition to (server-guarded; no free-form writes)
_ALLOWED_TRANSITIONS = {
    'draft': {'open'},
    'open': {'review'},
    'review': {'closed'},
    'closed': {'locked'},
    'locked': set(),
}


class AicHrmCycle(models.Model):
    _name = 'aic.hrm.cycle'
    _description = 'Performance Cycle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    cycle_type = fields.Selection([
        ('year', 'Year'),
        ('half', 'Half-year'),
        ('quarter', 'Quarter'),
        ('month', 'Month'),
        ('custom', 'Custom period'),
    ], default='year', required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    parent_id = fields.Many2one(
        'aic.hrm.cycle', string='Parent Cycle', index=True, ondelete='restrict',
        help="Containing cycle, e.g. the year a quarter belongs to. "
             "Cross-cycle goal alignment follows this relation.")
    child_ids = fields.One2many('aic.hrm.cycle', 'parent_id', string='Sub-cycles')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('review', 'In Review'),
        ('closed', 'Closed'),
        ('locked', 'Locked'),
    ], default='draft', required=True, tracking=True, copy=False)
    check_in_frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Every two weeks'),
        ('monthly', 'Monthly'),
    ], default='weekly', required=True)
    stale_days = fields.Integer(
        compute='_compute_stale_days', store=True, readonly=False,
        help="A goal with no check-in for this many days is flagged as stale. "
             "Defaults to twice the check-in interval.")
    rag_profile_id = fields.Many2one(
        'aic.hrm.rag.profile', string='RAG Profile', required=True,
        default=lambda self: self._default_rag_profile())
    score_cap = fields.Float(
        default=1.0, required=True,
        help="Upper bound of the normalized score scale. 1.0 is the Google "
             "OKR convention; raise it to allow visible overachievement.")
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    # NOTE(backport-18): Odoo 18 uses the legacy _sql_constraints list instead.
    _code_company_uniq = models.Constraint(
        'unique (code, company_id)',
        'The cycle code must be unique per company.',
    )

    @api.model
    def _default_rag_profile(self):
        profile = self.env.ref('aic_hrm_base.rag_profile_default',
                               raise_if_not_found=False)
        if not profile:
            profile = self.env['aic.hrm.rag.profile'].search([], limit=1)
        return profile

    @api.depends('check_in_frequency')
    def _compute_stale_days(self):
        for cycle in self:
            cycle.stale_days = 2 * _FREQUENCY_DAYS[cycle.check_in_frequency]

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for cycle in self:
            if cycle.date_end < cycle.date_start:
                raise ValidationError(_(
                    "Cycle %(name)s: the end date must be on or after the "
                    "start date.", name=cycle.display_name))

    @api.constrains('parent_id', 'date_start', 'date_end')
    def _check_parent(self):
        for cycle in self:
            if cycle._has_cycle():
                raise ValidationError(_("A cycle cannot contain itself."))
            parent = cycle.parent_id
            if parent and (cycle.date_start < parent.date_start
                           or cycle.date_end > parent.date_end):
                raise ValidationError(_(
                    "Cycle %(name)s must fall entirely within its parent "
                    "cycle %(parent)s.", name=cycle.display_name,
                    parent=parent.display_name))

    def _transition(self, target_state):
        for cycle in self:
            if target_state not in _ALLOWED_TRANSITIONS[cycle.state]:
                raise UserError(_(
                    "Cycle %(name)s cannot go from %(current)s to %(target)s.",
                    name=cycle.display_name, current=cycle.state,
                    target=target_state))
        self.write({'state': target_state})

    def action_open(self):
        self._transition('open')

    def action_start_review(self):
        self._transition('review')

    def action_close(self):
        self._transition('closed')

    def action_lock(self):
        self._transition('locked')

    def ensure_editable(self):
        """Guard used by every model that hangs off a cycle.

        Locked cycles are immutable; corrections after close must go through
        `aic.hrm.target.revision` with explicit approval instead.
        """
        for cycle in self:
            if cycle.state == 'locked':
                raise UserError(_(
                    "Cycle %(name)s is locked. Corrections require an "
                    "approved target revision.", name=cycle.display_name))
