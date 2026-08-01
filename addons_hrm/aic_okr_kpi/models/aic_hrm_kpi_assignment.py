# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from odoo.addons.aic_hrm_base.models import utils

_WEIGHT_PRECISION = 2


class AicHrmKpiAssignment(models.Model):
    """One employee's KPI scorecard for one cycle.

    The core management gate: the sum of line weights must be exactly 100%
    before the scorecard can be submitted. Draft scorecards may be
    incomplete while being built.
    """
    _name = 'aic.hrm.kpi.assignment'
    _description = 'KPI Assignment (Personal Scorecard)'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'aic.hrm.owner.mixin', 'aic.hrm.scoring.mixin']
    _order = 'cycle_id desc, employee_id'
    _rec_name = 'display_label'

    employee_id = fields.Many2one('hr.employee', required=True, index=True)
    cycle_id = fields.Many2one(
        'aic.hrm.cycle', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(
        related='cycle_id.company_id', store=True, index=True)
    display_label = fields.Char(compute='_compute_display_label', store=True)
    job_note = fields.Char(
        string='Position / Team',
        help="Free-form role description, e.g. from the assignment sheet.")
    responsibility = fields.Text()
    line_ids = fields.One2many(
        'aic.hrm.kpi.assignment.line', 'assignment_id')
    total_weight = fields.Float(
        compute='_compute_totals', store=True,
        help="Sum of line weights; must reach exactly 100% to submit.")
    weight_ok = fields.Boolean(compute='_compute_totals', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('done', 'Done'),
    ], default='draft', required=True, tracking=True, copy=False)

    _employee_cycle_uniq = models.Constraint(
        'unique (employee_id, cycle_id)',
        'This employee already has a scorecard for this cycle.',
    )

    @api.depends('employee_id', 'cycle_id')
    def _compute_display_label(self):
        for assignment in self:
            assignment.display_label = (
                f'{assignment.employee_id.name or ""} · '
                f'{assignment.cycle_id.code or ""}')

    @api.depends('line_ids', 'line_ids.weight', 'line_ids.score',
                 'cycle_id.score_cap')
    def _compute_totals(self):
        for assignment in self:
            total = sum(assignment.line_ids.mapped('weight'))
            assignment.total_weight = total
            assignment.weight_ok = float_compare(
                total, 100.0, precision_digits=_WEIGHT_PRECISION) == 0
            pairs = [(line.score, line.weight)
                     for line in assignment.line_ids]
            assignment.score = utils.clamp(
                utils.weighted_average(pairs), 0.0,
                assignment.cycle_id.score_cap or 1.0)

    score = fields.Float(
        compute='_compute_totals', store=True, readonly=True,
        aggregator='avg')

    def _get_rag_profile(self):
        self.ensure_one()
        return self.cycle_id.rag_profile_id or super()._get_rag_profile()

    def _validate_state_change(self, target_state):
        allowed = {'draft': {'submitted'}, 'submitted': {'approved', 'draft'},
                   'approved': {'done'}, 'done': set()}
        if target_state in ('approved', 'done') and not self.env.su and \
                not self.env.user.has_group('aic_hrm_base.group_hrm_manager'):
            raise UserError(_(
                "Only performance managers may approve or close "
                "scorecards."))
        for assignment in self:
            if target_state not in allowed[assignment.state]:
                raise UserError(_(
                    "Scorecard %(name)s cannot go from %(current)s to "
                    "%(target)s.", name=assignment.display_label,
                    current=assignment.state, target=target_state))
            if target_state == 'submitted' and not assignment.weight_ok:
                raise UserError(_(
                    "Scorecard %(name)s weighs %(total)s%%: line weights "
                    "must sum to exactly 100%% before submission.",
                    name=assignment.display_label,
                    total=assignment.total_weight))

    def write(self, vals):
        if 'state' in vals:
            self._validate_state_change(vals['state'])
        self.cycle_id.ensure_editable()
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        cycles = self.env['aic.hrm.cycle'].browse(
            [vals['cycle_id'] for vals in vals_list if vals.get('cycle_id')])
        cycles.ensure_editable()
        return super().create(vals_list)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_done(self):
        self.write({'state': 'done'})


class AicHrmKpiAssignmentLine(models.Model):
    _name = 'aic.hrm.kpi.assignment.line'
    _description = 'KPI Assignment Line'
    _order = 'assignment_id, id'

    assignment_id = fields.Many2one(
        'aic.hrm.kpi.assignment', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='assignment_id.company_id', store=True)
    kpi_target_id = fields.Many2one(
        'aic.hrm.kpi.target', required=True, index=True, ondelete='restrict')
    weight = fields.Float(required=True)
    personal_target = fields.Float(
        help="Optional personal target when it differs from the KPI "
             "target's cycle value.")
    score = fields.Float(
        compute='_compute_score', store=True, aggregator='avg')

    _assignment_target_uniq = models.Constraint(
        'unique (assignment_id, kpi_target_id)',
        'This KPI target is already on the scorecard.',
    )

    @api.depends('kpi_target_id.achievement', 'kpi_target_id.actual_value',
                 'kpi_target_id.direction', 'personal_target',
                 'assignment_id.cycle_id.score_cap')
    def _compute_score(self):
        for line in self:
            target = line.kpi_target_id
            if line.personal_target:
                cap = line.assignment_id.cycle_id.score_cap or 1.0
                line.score = utils.achievement(
                    target.actual_value, line.personal_target,
                    target.direction, cap=cap)
            else:
                line.score = target.achievement

    @api.constrains('weight')
    def _check_weight(self):
        for line in self:
            if line.weight <= 0:
                raise ValidationError(_(
                    "Assignment line weights must be positive."))

    @api.constrains('kpi_target_id', 'assignment_id')
    def _check_same_cycle(self):
        for line in self:
            if line.kpi_target_id.cycle_id != line.assignment_id.cycle_id:
                raise ValidationError(_(
                    "KPI target %(target)s belongs to another cycle than "
                    "the scorecard.",
                    target=line.kpi_target_id.display_label))


class AicHrmDepartmentScorecard(models.Model):
    """Read-only department roll-up backed by a SQL view: always current,
    zero storage, safe at enterprise row counts."""
    _name = 'aic.hrm.department.scorecard'
    _description = 'Department Scorecard'
    _auto = False
    _order = 'cycle_id desc, department_id'

    department_id = fields.Many2one('hr.department', readonly=True)
    cycle_id = fields.Many2one('aic.hrm.cycle', readonly=True)
    company_id = fields.Many2one('res.company', readonly=True)
    employee_count = fields.Integer(readonly=True)
    avg_composite = fields.Float(
        readonly=True, aggregator='avg',
        help="Average personal scorecard score in the department.")
    avg_objective_score = fields.Float(
        readonly=True, aggregator='avg',
        help="Average department-level objective score.")

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    row_number() OVER () AS id,
                    a.department_id AS department_id,
                    a.cycle_id AS cycle_id,
                    a.company_id AS company_id,
                    COUNT(DISTINCT a.employee_id) AS employee_count,
                    AVG(a.score) AS avg_composite,
                    (SELECT AVG(o.score)
                     FROM aic_hrm_objective o
                     WHERE o.cycle_id = a.cycle_id
                       AND o.department_id = a.department_id
                       AND o.level = 'department') AS avg_objective_score
                FROM aic_hrm_kpi_assignment a
                WHERE a.department_id IS NOT NULL
                GROUP BY a.department_id, a.cycle_id, a.company_id
            )
        """)
