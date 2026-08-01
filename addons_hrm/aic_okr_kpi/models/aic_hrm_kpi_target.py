# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.aic_hrm_base.models import utils

# Locked once the target is confirmed; changed only via approved revisions.
_GOVERNED_FIELDS = ('target_value', 'baseline_value', 'weight')
_GOVERNED_STATES = ('confirmed', 'done')


class AicHrmKpiTarget(models.Model):
    """A KPI instantiated for one cycle (and usually one owner).

    Definition attributes (direction, aggregation, unit, frequency) are
    inherited from the KPI as STORED COMPUTED fields with readonly=False:
    every creation path — form, import, API — gets correct values, manual
    overrides survive unrelated writes, and switching the KPI definition
    deliberately recomputes them (documented CX#7 semantics).
    """
    _name = 'aic.hrm.kpi.target'
    _description = 'KPI Target'
    _inherit = ['mail.thread', 'aic.hrm.owner.mixin', 'aic.hrm.scoring.mixin']
    _order = 'cycle_id desc, kpi_id, id'
    _rec_name = 'display_label'

    kpi_id = fields.Many2one(
        'aic.hrm.kpi', required=True, index=True, ondelete='restrict')
    cycle_id = fields.Many2one(
        'aic.hrm.cycle', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(
        related='cycle_id.company_id', store=True, index=True)
    objective_id = fields.Many2one(
        'aic.hrm.objective', index=True, ondelete='set null',
        help="Objective this KPI reports under, if any.")
    display_label = fields.Char(
        compute='_compute_display_label', store=True)
    weight = fields.Float(
        default=10.0, tracking=True,
        help="Weight of this KPI inside its owner's scorecard.")
    baseline_value = fields.Float()
    target_value = fields.Float(tracking=True)
    direction = fields.Selection([
        ('higher', 'Higher is better'),
        ('lower', 'Lower is better'),
        ('boolean', 'Pass / Fail'),
    ], compute='_compute_inherited', store=True, readonly=False,
        required=True, precompute=True)
    aggregation = fields.Selection([
        ('last', 'Final period value'),
        ('average', 'Average of periods'),
        ('sum', 'Cumulative sum'),
    ], compute='_compute_inherited', store=True, readonly=False,
        required=True, precompute=True)
    unit = fields.Char(
        compute='_compute_inherited', store=True, readonly=False,
        precompute=True)
    frequency = fields.Selection([
        ('monthly', 'Monthly'), ('quarterly', 'Quarterly'),
    ], compute='_compute_inherited', store=True, readonly=False,
        required=True, precompute=True)
    metric_source_id = fields.Many2one(
        'aic.hrm.metric.source',
        help="Optional automated pull for period actuals.")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], default='draft', required=True, tracking=True, copy=False)
    period_result_ids = fields.One2many(
        'aic.hrm.kpi.period.result', 'kpi_target_id')
    actual_value = fields.Float(
        compute='_compute_actuals', store=True,
        help="Cycle-level actual, aggregated from confirmed period results.")
    achievement = fields.Float(
        compute='_compute_actuals', store=True, aggregator='avg',
        help="Normalized 0..cap achievement against the cycle target.")
    note = fields.Text()

    _kpi_cycle_owner_uniq = models.Constraint(
        'unique (kpi_id, cycle_id, employee_id)',
        'This KPI is already assigned to this owner for this cycle.',
    )

    @api.depends('kpi_id', 'employee_id')
    def _compute_display_label(self):
        for target in self:
            owner = target.employee_id.name or _('Unassigned')
            target.display_label = f'{target.kpi_id.code} · {owner}'

    @api.depends('kpi_id')
    def _compute_inherited(self):
        for target in self:
            kpi = target.kpi_id
            if kpi:
                target.direction = kpi.direction
                target.aggregation = kpi.aggregation
                target.unit = kpi.unit
                target.frequency = kpi.frequency

    @api.depends('period_result_ids.actual', 'period_result_ids.state',
                 'period_result_ids.date_to', 'aggregation', 'direction',
                 'target_value', 'cycle_id.score_cap')
    def _compute_actuals(self):
        for target in self:
            results = target.period_result_ids.filtered(
                lambda r: r.state == 'confirmed')
            if not results:
                target.actual_value = 0.0
                target.achievement = 0.0
                target.score = 0.0
                continue
            values = results.mapped('actual')
            if target.aggregation == 'sum':
                actual = sum(values)
            elif target.aggregation == 'average':
                actual = sum(values) / len(values)
            else:  # last: value of the latest confirmed period
                actual = max(results, key=lambda r: r.date_to).actual
            cap = target.cycle_id.score_cap or 1.0
            target.actual_value = actual
            target.achievement = utils.achievement(
                actual, target.target_value, target.direction, cap=cap)
            target.score = target.achievement

    score = fields.Float(
        compute='_compute_actuals', store=True, readonly=True,
        aggregator='avg')

    def _get_rag_profile(self):
        self.ensure_one()
        return (self.kpi_id.rag_profile_id
                or self.cycle_id.rag_profile_id
                or super()._get_rag_profile())

    @api.constrains('direction', 'target_value')
    def _check_lower_target(self):
        for target in self:
            if target.direction == 'lower' and target.target_value <= 0.0:
                raise ValidationError(_(
                    "Lower-is-better targets must be strictly positive; "
                    "model 'zero incidents' goals as Pass/Fail."))

    @api.constrains('objective_id', 'cycle_id')
    def _check_objective_cycle(self):
        for target in self:
            if target.objective_id and \
                    target.objective_id.cycle_id != target.cycle_id:
                raise ValidationError(_(
                    "The linked objective belongs to a different cycle."))

    @api.model_create_multi
    def create(self, vals_list):
        cycles = self.env['aic.hrm.cycle'].browse(
            [vals['cycle_id'] for vals in vals_list if vals.get('cycle_id')])
        cycles.ensure_editable()
        return super().create(vals_list)

    def write(self, vals):
        self.cycle_id.ensure_editable()
        if 'cycle_id' in vals:
            self.env['aic.hrm.cycle'].browse(
                vals['cycle_id']).ensure_editable()
        if not self.env.context.get('hrm_revision_write'):
            governed = [f for f in _GOVERNED_FIELDS if f in vals]
            if governed:
                blocked = self.filtered(
                    lambda t: t.state in _GOVERNED_STATES)
                if blocked:
                    raise UserError(_(
                        "%(fields)s on confirmed KPI targets change only "
                        "through an approved target revision.",
                        fields=', '.join(governed)))
        return super().write(vals)

    def action_confirm(self):
        for target in self.filtered(lambda t: t.state == 'draft'):
            target.with_context(hrm_revision_write=True).write(
                {'state': 'confirmed'})

    def action_done(self):
        for target in self.filtered(lambda t: t.state == 'confirmed'):
            target.with_context(hrm_revision_write=True).write(
                {'state': 'done'})


class AicHrmKpiPeriodResult(models.Model):
    _name = 'aic.hrm.kpi.period.result'
    _description = 'KPI Period Result'
    _order = 'kpi_target_id, date_from'

    kpi_target_id = fields.Many2one(
        'aic.hrm.kpi.target', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='kpi_target_id.company_id', store=True, index=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    actual = fields.Float()
    period_target = fields.Float(
        help="Optional period-specific target when it differs from a simple "
             "pro-rata of the cycle target.")
    note = fields.Char()
    source = fields.Selection([
        ('manual', 'Manual entry'),
        ('import', 'Imported'),
        ('auto', 'Metric source'),
        ('checkin', 'Check-in'),
    ], default='manual', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], default='draft', required=True)

    _period_uniq = models.Constraint(
        'unique (kpi_target_id, date_from)',
        'This period already has a result for this KPI target.',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for result in self:
            if result.date_to < result.date_from:
                raise ValidationError(_(
                    "Period end must be on or after its start."))

    @api.model_create_multi
    def create(self, vals_list):
        targets = self.env['aic.hrm.kpi.target'].browse(
            [vals['kpi_target_id'] for vals in vals_list
             if vals.get('kpi_target_id')])
        targets.cycle_id.ensure_editable()
        return super().create(vals_list)

    def write(self, vals):
        self.kpi_target_id.cycle_id.ensure_editable()
        return super().write(vals)

    def unlink(self):
        self.kpi_target_id.cycle_id.ensure_editable()
        return super().unlink()
