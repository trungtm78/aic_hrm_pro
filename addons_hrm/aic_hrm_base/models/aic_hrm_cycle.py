# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Days per check-in frequency; stale threshold defaults to twice the interval.
_FREQUENCY_DAYS = {'weekly': 7, 'biweekly': 14, 'monthly': 30}

# state -> states it may transition to; write() validates legality and
# permission itself, so no context flag can act as a bypassable boundary.
_ALLOWED_TRANSITIONS = {
    'draft': {'open'},
    'open': {'review'},
    'review': {'closed'},
    'closed': {'locked'},
    'locked': set(),
}

# Locking is an admin act; every other transition is a manager act.
_ADMIN_TRANSITIONS = {'locked'}


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

    @api.constrains('parent_id', 'date_start', 'date_end', 'company_id')
    def _check_parent(self):
        for cycle in self:
            if cycle._has_cycle():
                raise ValidationError(_("A cycle cannot contain itself."))
            parent = cycle.parent_id
            if not parent:
                continue
            if cycle.company_id != parent.company_id:
                raise ValidationError(_(
                    "Cycle %(name)s and its parent must belong to the same "
                    "company.", name=cycle.display_name))
            if (cycle.date_start < parent.date_start
                    or cycle.date_end > parent.date_end):
                raise ValidationError(_(
                    "Cycle %(name)s must fall entirely within its parent "
                    "cycle %(parent)s.", name=cycle.display_name,
                    parent=parent.display_name))

    @api.constrains('rag_profile_id', 'company_id')
    def _check_rag_profile_company(self):
        for cycle in self:
            profile_company = cycle.rag_profile_id.company_id
            if profile_company and profile_company != cycle.company_id:
                raise ValidationError(_(
                    "RAG profile %(profile)s belongs to another company.",
                    profile=cycle.rag_profile_id.display_name))

    def _validate_state_change(self, target_state):
        if not self.env.su:
            required_group = ('aic_hrm_base.group_hrm_admin'
                              if target_state in _ADMIN_TRANSITIONS
                              else 'aic_hrm_base.group_hrm_manager')
            if not self.env.user.has_group(required_group):
                raise UserError(_(
                    "You do not have the rights to move cycles to "
                    "%(target)s.", target=target_state))
        for cycle in self:
            if target_state not in _ALLOWED_TRANSITIONS[cycle.state]:
                raise UserError(_(
                    "Cycle %(name)s cannot go from %(current)s to %(target)s.",
                    name=cycle.display_name, current=cycle.state,
                    target=target_state))

    def _transition(self, target_state):
        self.write({'state': target_state})

    def write(self, vals):
        if 'state' in vals:
            self._validate_state_change(vals['state'])
        else:
            locked = self.filtered(lambda c: c.state == 'locked')
            if locked:
                raise UserError(_(
                    "Cycle %(name)s is locked and cannot be modified.",
                    name=locked[0].display_name))
        return super().write(vals)

    def unlink(self):
        # What must never be destroyed is performance history, and that
        # history is the records filed under a cycle. Refusing by state
        # instead blocked a cycle that had been opened and then emptied:
        # there is no way back to draft, so it could never be removed.
        locked = self.filtered(lambda c: c.state == 'locked')
        if locked:
            raise UserError(_(
                "Cycle %(name)s is locked and cannot be deleted.",
                name=locked[0].display_name))
        for cycle in self:
            holdings = cycle._held_records()
            if holdings:
                raise UserError(_(
                    "Cycle %(name)s still holds %(records)s. Remove them "
                    "first, or archive the cycle instead.",
                    name=cycle.display_name,
                    records=', '.join(
                        f'{count} × {label}' for label, count in holdings)))
        return super().unlink()

    def _held_records(self):
        """``[(model description, count)]`` of stored records that point at
        this cycle through a restricting many2one, in any installed module.

        Read from the registry rather than a hard-coded list, so a module
        that files new records under cycles is covered without touching this
        one."""
        self.ensure_one()
        holdings = []
        for model_name in sorted(self.env.registry):
            model = self.env[model_name]
            if model._abstract or model._transient or not model._auto:
                continue
            for field in model._fields.values():
                if (field.type == 'many2one' and field.store
                        and field.comodel_name == self._name
                        and field.ondelete == 'restrict'):
                    count = model.sudo().with_context(
                        active_test=False).search_count(
                        [(field.name, '=', self.id)])
                    if count:
                        holdings.append((model._description, count))
        return holdings

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
