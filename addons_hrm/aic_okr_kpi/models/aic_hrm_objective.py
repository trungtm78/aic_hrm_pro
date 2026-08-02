# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.aic_hrm_base.models import utils

# state -> reachable states; write() itself validates legality + permission,
# so no context flag can act as a bypassable trust boundary.
_TRANSITIONS = {
    'draft': {'submitted'},
    'submitted': {'approved', 'draft'},
    'approved': {'in_progress'},
    'in_progress': {'self_assessed'},
    'self_assessed': {'manager_review'},
    'manager_review': {'done'},
    'done': set(),
}

# Target states that only performance managers may reach.
_MANAGER_TRANSITIONS = {'approved', 'done'}

# Once approved, these fields only change through an approved target revision.
_GOVERNED_STATES = ('approved', 'in_progress', 'self_assessed',
                    'manager_review', 'done')
_GOVERNED_FIELDS = ('weight',)


class AicHrmObjective(models.Model):
    _name = 'aic.hrm.objective'
    _description = 'Objective'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'aic.hrm.owner.mixin', 'aic.hrm.scoring.mixin']
    _order = 'cycle_id desc, code, id'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'aic.hrm.objective'),
        required=True, copy=False)
    cycle_id = fields.Many2one(
        'aic.hrm.cycle', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(
        related='cycle_id.company_id', store=True, index=True)
    level = fields.Selection([
        ('company', 'Company'),
        ('branch', 'Branch'),
        ('department', 'Department'),
        ('team', 'Team'),
        ('individual', 'Individual'),
    ], default='department', required=True)
    branch_id = fields.Many2one(
        'res.company', string='Branch',
        domain="['|', ('id', '=', company_id),"
               " ('id', 'child_of', company_id)]",
        help="Branch or subsidiary this objective belongs to "
             "(for branch-level objectives).")
    team_id = fields.Many2one(
        'aic.hrm.team', string='Team', index=True, ondelete='restrict',
        help="Team this objective belongs to (for team-level objectives).")
    perspective_id = fields.Many2one(
        'aic.hrm.perspective', string='BSC Perspective', index=True,
        ondelete='set null',
        help="Balanced Scorecard perspective this objective serves; "
             "leadership uses it to check the portfolio is balanced.")
    ksf_id = fields.Many2one(
        'aic.hrm.ksf', string='Key Success Factor', index=True,
        ondelete='set null',
        help="Success factor this objective drives - the strategy-level "
             "'must go right' it exists for.")
    framework_dimension_ids = fields.Many2many(
        'aic.hrm.perspective', 'aic_hrm_objective_dimension_rel',
        'objective_id', 'perspective_id', string='Framework Tags',
        help="Read this objective through additional frameworks - e.g. "
             "Hoshin 'Breakthrough' or 4DX 'Wildly Important Goal' on "
             "top of its BSC perspective.")
    objective_type = fields.Selection([
        ('committed', 'Committed'),
        ('aspirational', 'Aspirational'),
    ], default='committed', required=True,
        help="Committed objectives are expected to land at 100%. "
             "Aspirational ones are moonshots where ~70% is a success.")
    weight = fields.Float(
        default=10.0, tracking=True,
        help="Relative weight (%) among sibling objectives at the same level.")
    priority = fields.Selection([
        ('high', 'High'), ('medium', 'Medium'), ('low', 'Low'),
    ], default='medium')
    visibility = fields.Selection([
        ('public', 'Public'), ('private', 'Private'),
    ], default='public', required=True,
        help="Public goals are visible to every performance user; private "
             "ones only to the owner, their managers and HR.")
    description = fields.Html()
    note = fields.Text()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('self_assessed', 'Self-assessed'),
        ('manager_review', 'Manager Review'),
        ('done', 'Done'),
    ], default='draft', required=True, tracking=True, copy=False)

    parent_id = fields.Many2one(
        'aic.hrm.objective', string='Parent Objective', index=True,
        ondelete='set null',
        help="Objective this one cascades from — in the same cycle or in the "
             "containing cycle (e.g. a quarterly objective under an annual "
             "one).")
    child_ids = fields.One2many('aic.hrm.objective', 'parent_id')
    contributes_to_ids = fields.Many2many(
        'aic.hrm.objective', 'aic_hrm_objective_contribution_rel',
        'source_id', 'target_id', string='Contributes To',
        help="Soft alignment links besides the primary parent.")
    kr_ids = fields.One2many('aic.hrm.key.result', 'objective_id',
                             string='Key Results')
    kr_count = fields.Integer(compute='_compute_kr_count')

    @api.depends('kr_ids')
    def _compute_kr_count(self):
        for objective in self:
            objective.kr_count = len(objective.kr_ids)

    @api.depends('kr_ids.score', 'kr_ids.weight',
                 'child_ids.score', 'child_ids.weight',
                 'cycle_id.score_cap')
    def _compute_score(self):
        for objective in self:
            pairs = [(kr.score, kr.weight) for kr in objective.kr_ids]
            pairs += [(child.score, child.weight)
                      for child in objective.child_ids]
            # Clamp against OWN cycle cap: a child cycle with a higher cap
            # must not push the parent above its scale.
            objective.score = utils.clamp(
                utils.weighted_average(pairs), 0.0,
                objective.cycle_id.score_cap or 1.0)

    score = fields.Float(
        compute='_compute_score', store=True, readonly=True, aggregator='avg')

    def _get_rag_profile(self):
        self.ensure_one()
        return self.cycle_id.rag_profile_id or super()._get_rag_profile()

    @api.constrains('weight')
    def _check_weight(self):
        for objective in self:
            if not 0.0 <= objective.weight <= 100.0:
                raise ValidationError(_(
                    "Objective weight must be between 0 and 100 (got "
                    "%(weight)s).", weight=objective.weight))

    @api.constrains('level', 'branch_id', 'department_id', 'team_id',
                    'employee_id')
    def _check_level_anchor(self):
        """Each level anchors to its own organizational unit, so filters
        and roll-ups by branch/department/team/person stay trustworthy."""
        requirements = {
            'branch': ('branch_id', _("a branch")),
            'department': ('department_id', _("a department")),
            'team': ('team_id', _("a team")),
            'individual': ('employee_id', _("an owner (employee)")),
        }
        for objective in self:
            requirement = requirements.get(objective.level)
            if requirement and not objective[requirement[0]]:
                raise ValidationError(_(
                    "%(level)s-level objectives must be linked to "
                    "%(unit)s.",
                    level=dict(objective._fields['level'].selection)[
                        objective.level],
                    unit=requirement[1]))

    def _check_alignment_cycle(self, other, link_label):
        """1A rule: aligned objectives live in the same cycle or in the
        containing (parent) cycle. Anything else is a modelling error."""
        for objective in self:
            allowed_cycles = objective.cycle_id | objective.cycle_id.parent_id
            if other.cycle_id not in allowed_cycles:
                raise ValidationError(_(
                    "%(link)s: objective %(other)s belongs to cycle "
                    "%(other_cycle)s, which is neither this objective's "
                    "cycle nor its containing cycle.",
                    link=link_label, other=other.display_name,
                    other_cycle=other.cycle_id.display_name))

    @api.constrains('parent_id', 'cycle_id')
    def _check_parent_alignment(self):
        for objective in self:
            if objective._has_cycle():
                raise ValidationError(_(
                    "An objective cannot cascade from itself."))
            if objective.parent_id:
                objective._check_alignment_cycle(
                    objective.parent_id, _("Parent alignment"))

    @api.constrains('contributes_to_ids', 'cycle_id')
    def _check_contribution_alignment(self):
        for objective in self:
            for target in objective.contributes_to_ids:
                if target == objective:
                    raise ValidationError(_(
                        "An objective cannot contribute to itself."))
                objective._check_alignment_cycle(
                    target, _("Contribution alignment"))

    # ---- lifecycle ----

    @api.model_create_multi
    def create(self, vals_list):
        cycles = self.env['aic.hrm.cycle'].browse(
            [vals['cycle_id'] for vals in vals_list if vals.get('cycle_id')])
        cycles.ensure_editable()
        return super().create(vals_list)

    def _validate_state_change(self, target_state):
        """Legality + permission for a state change, whatever the entry
        point (action method or direct write over RPC)."""
        if target_state in _MANAGER_TRANSITIONS and not self.env.su and \
                not self.env.user.has_group('aic_hrm_base.group_hrm_manager'):
            raise UserError(_(
                "Only performance managers may move objectives to "
                "%(target)s.", target=target_state))
        for objective in self:
            if target_state not in _TRANSITIONS[objective.state]:
                raise UserError(_(
                    "Objective %(name)s cannot go from %(current)s to "
                    "%(target)s.", name=objective.display_name,
                    current=objective.state, target=target_state))

    def write(self, vals):
        if 'state' in vals:
            self._validate_state_change(vals['state'])
        self.cycle_id.ensure_editable()
        if 'cycle_id' in vals:
            self.env['aic.hrm.cycle'].browse(
                vals['cycle_id']).ensure_editable()
        if not self._revision_write_allowed():
            governed = [f for f in _GOVERNED_FIELDS if f in vals]
            if governed:
                blocked = self.filtered(
                    lambda o: o.state in _GOVERNED_STATES)
                if blocked:
                    raise UserError(_(
                        "%(fields)s on approved objectives change only "
                        "through an approved target revision.",
                        fields=', '.join(governed)))
        return super().write(vals)

    def _transition(self, target_state):
        self.write({'state': target_state})

    def action_submit(self):
        self._transition('submitted')

    def action_reset_to_draft(self):
        self._transition('draft')

    def action_approve(self):
        self._transition('approved')

    def action_start(self):
        self._transition('in_progress')

    def action_self_assess(self):
        self._transition('self_assessed')

    def action_manager_review(self):
        self._transition('manager_review')

    def action_finalize(self):
        self._transition('done')
