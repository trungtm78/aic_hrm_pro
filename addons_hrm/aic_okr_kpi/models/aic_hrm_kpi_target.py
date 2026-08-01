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

    def _load_actuals_map(self):
        """Batch aggregate confirmed period results: three SQL round-trips
        for the whole recordset instead of one ORM pass per target.
        Returns {target_id: (sum, count, last_actual)}."""
        real_ids = [i for i in self.ids if isinstance(i, int)]
        actuals = {}
        if not real_ids:
            return actuals
        PeriodResult = self.env['aic.hrm.kpi.period.result']
        PeriodResult.flush_model(['kpi_target_id', 'actual', 'state',
                                  'date_to'])
        for target_rec, total, count in PeriodResult._read_group(
                [('kpi_target_id', 'in', real_ids),
                 ('state', '=', 'confirmed')],
                ['kpi_target_id'], ['actual:sum', '__count']):
            actuals[target_rec.id] = [total or 0.0, count, 0.0]
        self.env.cr.execute("""
            SELECT DISTINCT ON (kpi_target_id) kpi_target_id, actual
            FROM aic_hrm_kpi_period_result
            WHERE kpi_target_id = ANY(%s) AND state = 'confirmed'
            ORDER BY kpi_target_id, date_to DESC, id DESC
        """, (real_ids,))
        for target_id, last_actual in self.env.cr.fetchall():
            if target_id in actuals:
                actuals[target_id][2] = last_actual or 0.0
        return actuals

    @api.depends('period_result_ids', 'period_result_ids.actual',
                 'period_result_ids.state', 'period_result_ids.date_to',
                 'aggregation', 'direction', 'target_value',
                 'cycle_id.score_cap')
    def _compute_actuals(self):
        actuals = self._load_actuals_map()
        for target in self:
            entry = actuals.get(target.id) if isinstance(target.id, int) \
                else None
            if entry is None:
                # Unsaved records (onchange) aggregate in memory.
                results = target.period_result_ids.filtered(
                    lambda r: r.state == 'confirmed')
                entry = [sum(results.mapped('actual')), len(results),
                         max(results, key=lambda r: r.date_to).actual
                         if results else 0.0]
            total, count, last_actual = entry
            if not count:
                target.actual_value = 0.0
                target.achievement = 0.0
                target.score = 0.0
                continue
            if target.aggregation == 'sum':
                actual = total
            elif target.aggregation == 'average':
                actual = total / count
            else:
                actual = last_actual
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

    @api.constrains('kpi_id', 'cycle_id')
    def _check_kpi_company(self):
        for target in self:
            kpi_company = target.kpi_id.company_id
            if kpi_company and kpi_company != target.cycle_id.company_id:
                raise ValidationError(_(
                    "KPI %(kpi)s belongs to another company than the cycle.",
                    kpi=target.kpi_id.display_name))

    @api.constrains('kpi_id', 'cycle_id', 'employee_id')
    def _check_unique_unassigned(self):
        # The SQL unique constraint cannot catch duplicated NULL owners.
        for target in self.filtered(lambda t: not t.employee_id):
            duplicate = self.search_count([
                ('id', '!=', target.id),
                ('kpi_id', '=', target.kpi_id.id),
                ('cycle_id', '=', target.cycle_id.id),
                ('employee_id', '=', False),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    "An unassigned target for this KPI already exists in "
                    "this cycle."))

    @api.model_create_multi
    def create(self, vals_list):
        cycles = self.env['aic.hrm.cycle'].browse(
            [vals['cycle_id'] for vals in vals_list if vals.get('cycle_id')])
        cycles.ensure_editable()
        return super().create(vals_list)

    def _validate_state_change(self, target_state):
        allowed = {'draft': {'confirmed'}, 'confirmed': {'done'},
                   'done': set()}
        if not self.env.su and not self.env.user.has_group(
                'aic_hrm_base.group_hrm_manager'):
            raise UserError(_(
                "Only performance managers may confirm or close KPI "
                "targets."))
        for target in self:
            if target_state not in allowed[target.state]:
                raise UserError(_(
                    "KPI target %(name)s cannot go from %(current)s to "
                    "%(target)s.", name=target.display_label,
                    current=target.state, target=target_state))

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
                    lambda t: t.state in _GOVERNED_STATES)
                if blocked:
                    raise UserError(_(
                        "%(fields)s on confirmed KPI targets change only "
                        "through an approved target revision.",
                        fields=', '.join(governed)))
        return super().write(vals)

    @api.model
    def _cron_refresh_metric_sources(self):
        """Pull automated actuals for the current month into draft period
        results. Runs as the cron superuser, which satisfies the metric
        source's admin gate."""
        targets = self.search([
            ('metric_source_id', '!=', False),
            ('cycle_id.state', '=', 'open'),
        ])
        PeriodResult = self.env['aic.hrm.kpi.period.result']
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for target in targets:
            value = target.metric_source_id.compute_value(
                date_from=month_start, date_to=today)
            existing = PeriodResult.search([
                ('kpi_target_id', '=', target.id),
                ('date_from', '=', month_start),
            ], limit=1)
            if existing:
                if existing.state == 'draft':
                    existing.write({'actual': value, 'source': 'auto'})
            else:
                PeriodResult.create({
                    'kpi_target_id': target.id,
                    'date_from': month_start,
                    'date_to': today,
                    'actual': value,
                    'source': 'auto',
                    'state': 'draft',
                })

    def action_confirm(self):
        self.filtered(lambda t: t.state == 'draft').write(
            {'state': 'confirmed'})

    def action_done(self):
        self.filtered(lambda t: t.state == 'confirmed').write(
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
        if 'kpi_target_id' in vals:
            self.env['aic.hrm.kpi.target'].browse(
                vals['kpi_target_id']).cycle_id.ensure_editable()
        return super().write(vals)

    def unlink(self):
        self.kpi_target_id.cycle_id.ensure_editable()
        return super().unlink()
