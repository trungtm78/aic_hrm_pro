# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

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
    _inherit = ['mail.thread', 'aic.hrm.owner.mixin', 'aic.hrm.scoring.mixin',
                'aic.hrm.revisable.mixin']
    _order = 'cycle_id desc, kpi_id, id'
    _rec_name = 'display_label'

    kpi_id = fields.Many2one(
        'aic.hrm.kpi', required=True, index=True, ondelete='restrict')
    cycle_id = fields.Many2one(
        'aic.hrm.cycle', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(
        related='cycle_id.company_id', store=True, index=True)
    kr_id = fields.Many2one(
        'aic.hrm.key.result', string='Key Result', index=True,
        ondelete='set null',
        help="Key result this KPI serves. It may belong to a longer cycle "
             "than the target, e.g. a quarterly key result for a monthly "
             "KPI.")
    objective_id = fields.Many2one(
        'aic.hrm.objective', index=True, ondelete='set null',
        compute='_compute_objective_id', store=True, readonly=False,
        precompute=True,
        help="Objective this KPI reports under, if any. Follows the key "
             "result when one is set.")
    target_note = fields.Char(
        string='Target as Assigned',
        help="The target in the words of the assignment sheet. Needed when "
             "the target is a milestone ('LIVE on 7/9 with 10 merchants') "
             "rather than a number, and kept next to the number otherwise.")
    team_id = fields.Many2one(
        'aic.hrm.team', string='Team', index=True, ondelete='restrict',
        help="Team this target is tracked for, when the KPI is a team "
             "number rather than a personal one.")
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
    perspective_id = fields.Many2one(
        related='kpi_id.perspective_id', store=True, index=True)
    collection_method = fields.Selection(
        related='kpi_id.collection_method')
    collection_guideline = fields.Text(
        related='kpi_id.collection_guideline',
        help="How to collect this number - defined once on the KPI, "
             "shown here so the owner knows the operating procedure.")
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
    has_actual = fields.Boolean(
        compute='_compute_actuals', store=True,
        help="At least one confirmed period result exists.")
    is_tracking = fields.Boolean(
        string='Tracking Only',
        help="Followed for information (e.g. department costs): the actual is "
             "shown but not scored, and the target cannot sit on a weighted "
             "scorecard line.")
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

    @api.depends('kr_id')
    def _compute_objective_id(self):
        for target in self:
            if target.kr_id:
                target.objective_id = target.kr_id.objective_id
            else:
                target.objective_id = target.objective_id

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
                 'cycle_id.score_cap', 'is_tracking')
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
            target.has_actual = bool(count)
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
            target.actual_value = actual
            if target.is_tracking:
                target.achievement = 0.0
                target.score = 0.0
                continue
            cap = target.cycle_id.score_cap or 1.0
            target.achievement = utils.achievement(
                actual, target.target_value, target.direction, cap=cap)
            target.score = target.achievement

    score = fields.Float(
        compute='_compute_actuals', store=True, readonly=True,
        aggregator='avg')

    @api.depends('score', 'is_tracking')
    def _compute_rag(self):
        tracking = self.filtered('is_tracking')
        tracking.rag = 'none'
        super(AicHrmKpiTarget, self - tracking)._compute_rag()

    @api.constrains('is_tracking')
    def _check_tracking_not_weighted(self):
        lines = self.env['aic.hrm.kpi.assignment.line'].search_count(
            [('kpi_target_id', 'in', self.filtered('is_tracking').ids)], limit=1)
        if lines:
            raise ValidationError(_(
                "A target on a scorecard carries weight; it cannot be made "
                "tracking-only."))

    def _get_rag_profile(self):
        self.ensure_one()
        return (self.kpi_id.rag_profile_id
                or self.cycle_id.rag_profile_id
                or super()._get_rag_profile())

    @api.constrains('direction', 'target_value')
    def _check_lower_target(self):
        for target in self:
            if target.direction == 'lower' and target.target_value < 0.0:
                raise ValidationError(_(
                    "A lower-is-better target cannot be negative. Use 0 for "
                    "zero tolerance."))

    @api.constrains('objective_id', 'kr_id', 'cycle_id')
    def _check_objective_cycle(self):
        # A monthly KPI serves a quarterly (or yearly) plan: the goal it
        # reports under may sit in the target's cycle or any cycle above it,
        # never in an unrelated or a shorter one.
        for target in self:
            lineage = target.cycle_id._lineage()
            if target.objective_id and \
                    target.objective_id.cycle_id not in lineage:
                raise ValidationError(_(
                    "The linked objective belongs to a cycle that does not "
                    "contain %(cycle)s.", cycle=target.cycle_id.display_name))
            if target.kr_id and target.kr_id.objective_id != target.objective_id:
                raise ValidationError(_(
                    "Key result %(kr)s belongs to another objective than the "
                    "one this KPI reports under.",
                    kr=target.kr_id.display_name))

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
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for target in targets:
            target._pull_metric_period(month_start, today)

    def _pull_metric_period(self, date_from, date_to):
        """Upsert one automatic draft result for the period.

        Manual always beats automatic: an existing result is refreshed only
        while it is still an automatic draft."""
        self.ensure_one()
        value = self.metric_source_id.compute_value(
            date_from=date_from, date_to=date_to)
        PeriodResult = self.env['aic.hrm.kpi.period.result']
        existing = PeriodResult.search([
            ('kpi_target_id', '=', self.id),
            ('date_from', '=', date_from),
        ], limit=1)
        if existing:
            if existing.state == 'draft' and existing.source == 'auto':
                existing.write({'actual': value, 'date_to': date_to})
            return existing
        return PeriodResult.create({
            'kpi_target_id': self.id,
            'date_from': date_from,
            'date_to': date_to,
            'actual': value,
            'source': 'auto',
            'state': 'draft',
        })

    def _metric_periods(self, today):
        """Periods of the target's cycle that have started by ``today``:
        one per month for monthly targets, the whole cycle otherwise."""
        self.ensure_one()
        start, end = self.cycle_id.date_start, self.cycle_id.date_end
        if start > today:
            return []
        if self.frequency != 'monthly':
            return [(start, min(end, today))]
        periods, month_start = [], start
        while month_start <= min(end, today):
            month_end = month_start + relativedelta(day=31)
            periods.append((month_start, min(month_end, end, today)))
            month_start = month_end + relativedelta(days=1)
        return periods

    def action_pull_metric_actuals(self):
        """Read every started period of each target from its metric source,
        e.g. July and August revenue from posted invoices, not only the
        current month the nightly pull covers."""
        without = self.filtered(lambda target: not target.metric_source_id)
        if without:
            raise UserError(_(
                "%(targets)s: set a metric source before pulling actuals.",
                targets=', '.join(without.mapped('display_label'))))
        self.cycle_id.ensure_editable()
        today = fields.Date.context_today(self)
        for target in self:
            for date_from, date_to in target._metric_periods(today):
                target._pull_metric_period(date_from, date_to)
        return True

    audit_count = fields.Integer(compute='_compute_audit_count')

    def _compute_audit_count(self):
        Audit = self.env['aic.hrm.kpi.result.audit']
        counts = {}
        real_ids = [i for i in self.ids if isinstance(i, int)]
        if real_ids:
            for target, count in Audit._read_group(
                    [('kpi_target_id', 'in', real_ids)], ['kpi_target_id'], ['__count']):
                counts[target.id] = count
        for target in self:
            target.audit_count = counts.get(target.id, 0)

    def action_open_result_audit(self):
        """Every change ever made to this KPI's figures, newest first."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actual figure history'),
            'res_model': 'aic.hrm.kpi.result.audit',
            'view_mode': 'list,form',
            'domain': [('kpi_target_id', '=', self.id)],
            'context': {'create': False},
        }

    def action_confirm(self):
        self.filtered(lambda t: t.state == 'draft').write(
            {'state': 'confirmed'})

    def action_done(self):
        self.filtered(lambda t: t.state == 'confirmed').write(
            {'state': 'done'})


# Once a figure is part of a score, these may only change after the
# confirmation has been withdrawn with a reason.
_LOCKED_ONCE_CONFIRMED = ('actual', 'date_from', 'date_to', 'kpi_target_id')


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
    confirmed_by = fields.Many2one(
        'res.users', string='Confirmed by', readonly=True, copy=False,
        help="Who accepted this figure into the score.")
    confirmed_on = fields.Datetime(readonly=True, copy=False)
    audit_ids = fields.One2many(
        'aic.hrm.kpi.result.audit', 'result_id', string='History',
        readonly=True)

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

    @api.constrains('date_from', 'date_to', 'kpi_target_id')
    def _check_period_inside_cycle(self):
        """A figure dated outside the cycle it scores is a data error that
        silently moves someone's score."""
        for result in self:
            cycle = result.kpi_target_id.cycle_id
            if not cycle:
                continue
            if result.date_from < cycle.date_start or result.date_to > cycle.date_end:
                raise ValidationError(_(
                    "The period %(start)s - %(end)s falls outside cycle "
                    "%(cycle)s (%(from)s - %(to)s).",
                    start=result.date_from, end=result.date_to,
                    cycle=cycle.display_name, **{'from': cycle.date_start,
                                                 'to': cycle.date_end}))

    @api.model_create_multi
    def create(self, vals_list):
        targets = self.env['aic.hrm.kpi.target'].browse(
            [vals['kpi_target_id'] for vals in vals_list
             if vals.get('kpi_target_id')])
        targets.cycle_id.ensure_editable()
        if any(vals.get('state') == 'confirmed' for vals in vals_list):
            # Entering a figure and accepting it into the score are two
            # different rights; creating it already confirmed needs the second.
            self._check_manager()
        results = super().create(vals_list)
        Audit = self.env['aic.hrm.kpi.result.audit']
        for result in results:
            Audit.record_event(result, 'create')
            if result.state == 'confirmed':
                result.sudo().write({'confirmed_by': self.env.uid,
                                     'confirmed_on': fields.Datetime.now()})
                Audit.record_event(result, 'confirm', old={'state': 'draft'})
        return results

    def write(self, vals):
        self.kpi_target_id.cycle_id.ensure_editable()
        if 'kpi_target_id' in vals:
            self.env['aic.hrm.kpi.target'].browse(
                vals['kpi_target_id']).cycle_id.ensure_editable()
        if 'state' in vals:
            self._validate_state_change(vals['state'])
        locked = [field for field in _LOCKED_ONCE_CONFIRMED if field in vals]
        if locked and not self.env.context.get('hrm_result_state_change'):
            confirmed = self.filtered(lambda r: r.state == 'confirmed')
            if confirmed:
                raise UserError(_(
                    "%(fields)s cannot change on a confirmed figure: withdraw "
                    "the confirmation first, with a reason.",
                    fields=', '.join(locked)))
        before = {result.id: {'actual': result.actual, 'state': result.state}
                  for result in self}
        written = super().write(vals)
        Audit = self.env['aic.hrm.kpi.result.audit']
        for result in self:
            old = before[result.id]
            if 'actual' in vals and old['actual'] != result.actual:
                Audit.record_event(result, 'edit', old=old)
        return written

    def unlink(self):
        self.kpi_target_id.cycle_id.ensure_editable()
        confirmed = self.filtered(lambda r: r.state == 'confirmed')
        if confirmed:
            raise UserError(_(
                "A confirmed figure cannot be deleted: withdraw the "
                "confirmation first, with a reason. The score depends on it."))
        Audit = self.env['aic.hrm.kpi.result.audit']
        for result in self:
            Audit.record_event(result, 'delete')
        return super().unlink()

    def _check_manager(self):
        if not self.env.su and not self.env.user.has_group(
                'aic_hrm_base.group_hrm_manager'):
            raise UserError(_(
                "Only performance managers may confirm period results."))

    def _validate_state_change(self, target_state):
        """Confirming, and taking a confirmation back, are managers' acts -
        whichever way they are written, form, list or RPC."""
        self._check_manager()
        if target_state == 'draft' and not self.env.context.get(
                'hrm_result_reset_reason'):
            withdrawing = self.filtered(lambda r: r.state == 'confirmed')
            if withdrawing:
                raise UserError(_(
                    "Withdrawing a confirmed figure changes a score: do it "
                    "through \"Withdraw confirmation\" and state the reason."))

    def action_confirm(self):
        """Confirm the selected results; only confirmed results score."""
        self._check_manager()
        drafts = self.filtered(lambda r: r.state == 'draft')
        Audit = self.env['aic.hrm.kpi.result.audit']
        for result in drafts:
            result.with_context(hrm_result_state_change=True).write({
                'state': 'confirmed', 'confirmed_by': self.env.uid,
                'confirmed_on': fields.Datetime.now()})
            Audit.record_event(result, 'confirm', old={'state': 'draft'})
        return True

    def action_open_reset_wizard(self):
        """Ask for the reason before a confirmed figure leaves the score."""
        self._check_manager()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Withdraw confirmation'),
            'res_model': 'aic.hrm.kpi.result.reset.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_result_ids': self.ids},
        }

    def action_reset_to_draft(self, reason=False):
        self._check_manager()
        confirmed = self.filtered(lambda r: r.state == 'confirmed')
        if confirmed and not reason:
            raise UserError(_(
                "Withdrawing a confirmed figure changes a score: state the "
                "reason."))
        Audit = self.env['aic.hrm.kpi.result.audit']
        for result in confirmed:
            # Who confirmed it is cleared by the write, so read it first.
            confirmer = result.confirmed_by
            result.with_context(hrm_result_state_change=True,
                                hrm_result_reset_reason=True).write({
                'state': 'draft', 'confirmed_by': False, 'confirmed_on': False})
            Audit.record_event(result, 'reset', reason=reason,
                               old={'state': 'confirmed'},
                               same_user=confirmer.id == self.env.uid)
            target = result.kpi_target_id
            target.message_post(body=_(
                "Confirmation withdrawn for the period %(start)s - %(end)s "
                "(figure %(actual)s). Reason: %(reason)s",
                start=result.date_from, end=result.date_to,
                actual=result.actual, reason=reason))
        return True
