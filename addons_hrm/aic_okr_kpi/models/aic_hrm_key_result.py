# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from odoo.addons.aic_hrm_base.models import utils

# Once the objective is approved these change only via target revisions;
# 'current' stays free because check-ins write it continuously.
_GOVERNED_FIELDS = ('target', 'baseline', 'weight')
_GOVERNED_STATES = ('approved', 'in_progress', 'self_assessed',
                    'manager_review', 'done')


class AicHrmKeyResult(models.Model):
    _name = 'aic.hrm.key.result'
    _description = 'Key Result'
    _inherit = ['mail.thread', 'aic.hrm.owner.mixin', 'aic.hrm.scoring.mixin']
    _order = 'objective_id, code, id'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(
        default=lambda self: self.env['ir.sequence'].next_by_code(
            'aic.hrm.key.result'),
        required=True, copy=False)
    objective_id = fields.Many2one(
        'aic.hrm.objective', required=True, index=True, ondelete='cascade')
    cycle_id = fields.Many2one(
        related='objective_id.cycle_id', store=True, index=True)
    company_id = fields.Many2one(
        related='objective_id.company_id', store=True, index=True)
    metric_type = fields.Selection([
        ('number', 'Number'),
        ('percent', 'Percentage'),
        ('milestone', 'Milestones'),
        ('boolean', 'Done / Not done'),
    ], default='number', required=True)
    direction = fields.Selection([
        ('higher', 'Higher is better'),
        ('lower', 'Lower is better'),
    ], default='higher', required=True)
    unit = fields.Char()
    baseline = fields.Float()
    current = fields.Float(tracking=True)
    target = fields.Float()
    weight = fields.Float(
        default=1.0,
        help="Relative weight of this key result inside its objective.")
    deadline = fields.Date()
    focus_quarters = fields.Char(
        help="Free-form focus period, e.g. 'Q2-Q3'.")
    priority = fields.Selection([
        ('high', 'High'), ('medium', 'Medium'), ('low', 'Low'),
    ], default='medium')
    note = fields.Text()
    milestone_ids = fields.One2many(
        'aic.hrm.kr.milestone', 'kr_id', string='Milestones')
    progress = fields.Float(
        compute='_compute_progress', store=True, aggregator='avg',
        help="Normalized 0..cap progress toward the target.")
    last_checkin_date = fields.Date(readonly=True, copy=False)
    confidence = fields.Integer(
        readonly=True, copy=False,
        help="Latest check-in confidence, 1 (will miss) to 10 (will hit).")

    @api.depends('metric_type', 'direction', 'baseline', 'current', 'target',
                 'milestone_ids.is_done', 'milestone_ids.weight',
                 'cycle_id.score_cap')
    def _compute_progress(self):
        for kr in self:
            cap = kr.cycle_id.score_cap or 1.0
            if kr.metric_type == 'milestone':
                pairs = [(1.0 if m.is_done else 0.0, m.weight)
                         for m in kr.milestone_ids]
                value = utils.clamp(utils.weighted_average(pairs), 0.0, cap)
            elif kr.metric_type == 'boolean':
                value = 1.0 if kr.current >= 1 else 0.0
            else:
                value = utils.progress_linear(
                    kr.baseline, kr.current, kr.target,
                    higher_is_better=kr.direction == 'higher', cap=cap)
            kr.progress = value
            kr.score = value

    score = fields.Float(
        compute='_compute_progress', store=True, readonly=True,
        aggregator='avg')

    def _get_rag_profile(self):
        self.ensure_one()
        return self.cycle_id.rag_profile_id or super()._get_rag_profile()

    @api.constrains('metric_type', 'baseline', 'target')
    def _check_span(self):
        for kr in self:
            if kr.metric_type in ('number', 'percent') and \
                    float_compare(kr.target, kr.baseline,
                                  precision_digits=6) == 0:
                raise ValidationError(_(
                    "Key result %(name)s: target and baseline must differ, "
                    "otherwise progress is undefined.", name=kr.display_name))

    @api.constrains('weight')
    def _check_weight(self):
        for kr in self:
            if kr.weight < 0:
                raise ValidationError(_(
                    "Key result weight cannot be negative."))

    @api.model_create_multi
    def create(self, vals_list):
        objectives = self.env['aic.hrm.objective'].browse(
            [vals['objective_id'] for vals in vals_list
             if vals.get('objective_id')])
        objectives.cycle_id.ensure_editable()
        return super().create(vals_list)

    def write(self, vals):
        self.cycle_id.ensure_editable()
        if not self.env.context.get('hrm_revision_write'):
            governed = [f for f in _GOVERNED_FIELDS if f in vals]
            if governed:
                blocked = self.filtered(
                    lambda kr: kr.objective_id.state in _GOVERNED_STATES)
                if blocked:
                    raise UserError(_(
                        "%(fields)s on key results of approved objectives "
                        "change only through an approved target revision.",
                        fields=', '.join(governed)))
        return super().write(vals)


class AicHrmKrMilestone(models.Model):
    _name = 'aic.hrm.kr.milestone'
    _description = 'Key Result Milestone'
    _order = 'kr_id, sequence, id'

    kr_id = fields.Many2one(
        'aic.hrm.key.result', required=True, index=True, ondelete='cascade')
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    weight = fields.Float(default=1.0)
    is_done = fields.Boolean()
    date_done = fields.Date(readonly=True, copy=False)

    def write(self, vals):
        if vals.get('is_done') and 'date_done' not in vals:
            vals['date_done'] = fields.Date.context_today(self)
        elif vals.get('is_done') is False:
            vals['date_done'] = False
        return super().write(vals)
