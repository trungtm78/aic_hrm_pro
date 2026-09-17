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
    group_ids = fields.One2many(
        'aic.hrm.kpi.assignment.group', 'assignment_id', string='KPI Groups',
        copy=True,
        help="Weighted sections of the scorecard, e.g. revenue KPIs 80% and "
             "management KPIs 20%. Leave empty for a flat scorecard.")
    total_weight = fields.Float(
        compute='_compute_totals', store=True,
        help="Sum of line weights; must reach exactly 100% to submit.")
    weight_ok = fields.Boolean(compute='_compute_totals', store=True)
    weight_issue = fields.Char(
        compute='_compute_totals', store=True,
        help="Why the weights do not add up, when they do not.")
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
                 'line_ids.has_actual',
                 'line_ids.group_id', 'line_ids.weight_in_group',
                 'group_ids.weight', 'group_ids.group_id',
                 'group_ids.total_in_group', 'cycle_id.score_cap')
    def _compute_totals(self):
        for assignment in self:
            total = sum(assignment.line_ids.mapped('weight'))
            assignment.total_weight = total
            assignment.weight_issue = assignment._weight_issue(total)
            assignment.weight_ok = not assignment.weight_issue
            pairs = [(line.score, line.weight)
                     for line in assignment.line_ids]
            cap = assignment.cycle_id.score_cap or 1.0
            assignment.score = utils.clamp(
                utils.weighted_average(pairs), 0.0, cap)
            covered = [(line.score, line.weight)
                       for line in assignment.line_ids if line.has_actual]
            assignment.data_coverage = utils.coverage(covered, pairs)
            assignment.score_covered = utils.clamp(
                utils.weighted_average(covered), 0.0, cap)

    score = fields.Float(
        compute='_compute_totals', store=True, readonly=True,
        aggregator='avg')
    data_coverage = fields.Float(
        string='Data Coverage (%)', compute='_compute_totals', store=True,
        aggregator='avg',
        help="Share of the scorecard's weight whose KPIs have confirmed "
             "actuals.")
    score_covered = fields.Float(
        string='Score on Measured KPIs', compute='_compute_totals',
        store=True, aggregator='avg',
        help="Weighted score over the KPIs that have confirmed actuals only. "
             "Read it together with the data coverage.")

    def _weight_issue(self, total):
        """First reason the weights do not add up, or False.

        With groups, both levels must hold on their own: two groups whose
        lines total 120% and 80% still make exactly 100 overall, and a
        total-only check would pass a scorecard nobody drew up."""
        self.ensure_one()

        def off(value):
            return float_compare(
                value, 100.0, precision_digits=_WEIGHT_PRECISION) != 0

        if not self.group_ids:
            return (_("line weights total %(total)s%%", total=total)
                    if off(total) else False)
        if self.line_ids.filtered(lambda line: not line.group_id):
            return _("every line must belong to one of the scorecard's "
                     "groups")
        declared = self.group_ids.group_id
        stray = self.line_ids.group_id - declared
        if stray:
            return _("group %(group)s is used by a line but not declared on "
                     "the scorecard", group=stray[0].display_name)
        group_total = sum(self.group_ids.mapped('weight'))
        if off(group_total):
            return _("the groups total %(total)s%%", total=group_total)
        for group in self.group_ids:
            if off(group.total_in_group):
                return _("the lines of group %(group)s total %(total)s%%",
                         group=group.group_id.display_name,
                         total=group.total_in_group)
        return False

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
                    "Scorecard %(name)s cannot be submitted: %(issue)s. "
                    "Weights must add up to exactly 100%%.",
                    name=assignment.display_label,
                    issue=assignment.weight_issue))

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
    group_id = fields.Many2one(
        'aic.hrm.kpi.group', string='KPI Group', index=True,
        ondelete='restrict')
    weight_in_group = fields.Float(
        string='Weight in Group',
        help="Share of this line inside its group, in percent.")
    weight = fields.Float(
        required=True, compute='_compute_weight', store=True, readonly=False,
        precompute=True,
        help="Share of the whole scorecard. On a grouped line it is derived: "
             "group weight x weight in group.")
    has_actual = fields.Boolean(
        related='kpi_target_id.has_actual', store=True)
    personal_target = fields.Float(
        help="Optional personal target when it differs from the KPI "
             "target's cycle value.")
    score = fields.Float(
        compute='_compute_score', store=True, aggregator='avg')

    _assignment_target_uniq = models.Constraint(
        'unique (assignment_id, kpi_target_id)',
        'This KPI target is already on the scorecard.',
    )

    @api.depends('group_id', 'weight_in_group',
                 'assignment_id.group_ids.group_id',
                 'assignment_id.group_ids.weight')
    def _compute_weight(self):
        for line in self:
            section = line.assignment_id.group_ids.filtered(
                lambda group: group.group_id == line.group_id)[:1]
            if line.group_id and section:
                line.weight = round(
                    section.weight * line.weight_in_group / 100.0,
                    _WEIGHT_PRECISION + 2)
            else:
                line.weight = line.weight

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

    @api.constrains('weight', 'weight_in_group', 'group_id')
    def _check_weight(self):
        for line in self:
            share = line.weight_in_group if line.group_id else line.weight
            if share <= 0:
                raise ValidationError(_(
                    "Assignment line weights must be positive."))

    @api.constrains('kpi_target_id')
    def _check_not_tracking(self):
        for line in self:
            if line.kpi_target_id.is_tracking:
                raise ValidationError(_(
                    "KPI target %(target)s is tracking-only and cannot carry "
                    "weight on a scorecard.",
                    target=line.kpi_target_id.display_label))

    @api.constrains('kpi_target_id', 'assignment_id')
    def _check_same_cycle(self):
        for line in self:
            if line.kpi_target_id.cycle_id != line.assignment_id.cycle_id:
                raise ValidationError(_(
                    "KPI target %(target)s belongs to another cycle than "
                    "the scorecard.",
                    target=line.kpi_target_id.display_label))


class AicHrmKpiAssignmentGroup(models.Model):
    """A weighted section of one scorecard, e.g. "revenue KPIs: 80%"."""
    _name = 'aic.hrm.kpi.assignment.group'
    _description = 'Scorecard KPI Group'
    _order = 'assignment_id, sequence, id'

    assignment_id = fields.Many2one(
        'aic.hrm.kpi.assignment', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='assignment_id.company_id', store=True)
    sequence = fields.Integer(related='group_id.sequence', store=True)
    group_id = fields.Many2one(
        'aic.hrm.kpi.group', string='KPI Group', required=True,
        ondelete='restrict')
    weight = fields.Float(
        required=True, help="Share of the scorecard, in percent.")
    total_in_group = fields.Float(
        compute='_compute_total_in_group', store=True,
        help="Sum of the in-group weights of this group's lines; must be "
             "100%.")

    _assignment_group_uniq = models.Constraint(
        'unique (assignment_id, group_id)',
        'This KPI group is already on the scorecard.',
    )

    @api.depends('assignment_id.line_ids.group_id',
                 'assignment_id.line_ids.weight_in_group')
    def _compute_total_in_group(self):
        for section in self:
            section.total_in_group = sum(
                section.assignment_id.line_ids.filtered(
                    lambda line: line.group_id == section.group_id
                ).mapped('weight_in_group'))

    @api.constrains('weight')
    def _check_weight(self):
        for section in self:
            if section.weight <= 0:
                raise ValidationError(_(
                    "KPI group weights must be positive."))


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
    avg_score_covered = fields.Float(
        readonly=True, aggregator='avg',
        help="Average score over the KPIs that have confirmed actuals.")
    avg_data_coverage = fields.Float(
        string='Data Coverage (%)', readonly=True, aggregator='avg',
        help="Average share of scorecard weight that has confirmed actuals.")
    avg_objective_score = fields.Float(
        readonly=True, aggregator='avg',
        help="Average department-level objective score, taken from this cycle "
             "or from the nearest cycle above it.")
    objective_cycle_id = fields.Many2one(
        'aic.hrm.cycle', string='OKR Cycle', readonly=True,
        help="Which cycle the objective score came from. Objectives are often "
             "set per quarter while scorecards are assigned per month.")

    def init(self):
        # The objective score follows the cycle's ancestry (month -> quarter ->
        # year) and the nearest level that actually has department objectives
        # wins: KPIs are assigned monthly while objectives are set per quarter,
        # and a monthly row that only looked at its own month reported a
        # department with no strategy. `objective_cycle_id` says which level
        # answered, so nobody has to guess.
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH RECURSIVE lineage AS (
                    SELECT c.id AS cycle_id, c.id AS ancestor_id,
                           c.parent_id AS next_id, 0 AS depth
                    FROM aic_hrm_cycle c
                    UNION ALL
                    SELECT l.cycle_id, c.id AS ancestor_id,
                           c.parent_id AS next_id, l.depth + 1
                    FROM lineage l
                    JOIN aic_hrm_cycle c ON c.id = l.next_id
                    WHERE l.depth < 10
                ),
                objective_by_level AS (
                    SELECT l.cycle_id, l.ancestor_id, l.depth, o.department_id,
                           AVG(o.score) AS objective_score
                    FROM lineage l
                    JOIN aic_hrm_objective o
                      ON o.cycle_id = l.ancestor_id
                     AND o.level = 'department'
                     AND o.department_id IS NOT NULL
                    GROUP BY l.cycle_id, l.ancestor_id, l.depth, o.department_id
                ),
                nearest_objective AS (
                    SELECT DISTINCT ON (cycle_id, department_id)
                           cycle_id, department_id, ancestor_id, objective_score
                    FROM objective_by_level
                    ORDER BY cycle_id, department_id, depth
                )
                SELECT
                    -- A stable id per (department, cycle) group: row_number()
                    -- changes between queries, so reading a row Odoo had just
                    -- searched could land on a different department.
                    MIN(a.id) AS id,
                    a.department_id AS department_id,
                    a.cycle_id AS cycle_id,
                    a.company_id AS company_id,
                    COUNT(DISTINCT a.employee_id) AS employee_count,
                    AVG(a.score) AS avg_composite,
                    AVG(a.score_covered) AS avg_score_covered,
                    AVG(a.data_coverage) AS avg_data_coverage,
                    MAX(n.objective_score) AS avg_objective_score,
                    MAX(n.ancestor_id) AS objective_cycle_id
                FROM aic_hrm_kpi_assignment a
                LEFT JOIN nearest_objective n
                       ON n.cycle_id = a.cycle_id
                      AND n.department_id = a.department_id
                WHERE a.department_id IS NOT NULL
                GROUP BY a.department_id, a.cycle_id, a.company_id
            )
        """)
