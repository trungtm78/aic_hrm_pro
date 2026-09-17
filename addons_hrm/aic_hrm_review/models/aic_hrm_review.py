# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

# Final score below this suggests a performance improvement plan.
_PIP_THRESHOLD = 0.4

_NINE_BOX = {
    ('high', 'high'): 'star',
    ('high', 'medium'): 'high_performer',
    ('high', 'low'): 'workhorse',
    ('medium', 'high'): 'growth_talent',
    ('medium', 'medium'): 'core_player',
    ('medium', 'low'): 'solid_contributor',
    ('low', 'high'): 'rough_diamond',
    ('low', 'medium'): 'inconsistent',
    ('low', 'low'): 'underperformer',
}


class AicHrmReviewCycle(models.Model):
    _name = 'aic.hrm.review.cycle'
    _description = 'Review Cycle'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    perf_cycle_id = fields.Many2one(
        'aic.hrm.cycle', required=True, ondelete='restrict',
        help="Performance cycle whose goal scores feed the reviews.")
    company_id = fields.Many2one(
        related='perf_cycle_id.company_id', store=True, index=True)
    template_id = fields.Many2one('aic.hrm.review.template', required=True)
    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)
    department_ids = fields.Many2many(
        'hr.department',
        help="Scope; empty covers every active employee of the company.")
    review_ids = fields.One2many('aic.hrm.review', 'review_cycle_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('calibration', 'Calibration'),
        ('closed', 'Closed'),
    ], default='draft', required=True, tracking=True, copy=False)
    small_team_warning = fields.Char(
        compute='_compute_small_team_warning',
        help="Anonymity is arithmetically weak in very small teams.")

    @api.depends('department_ids')
    def _compute_small_team_warning(self):
        for cycle in self:
            counts = []
            for department in cycle.department_ids:
                counts.append(self.env['hr.employee'].search_count(
                    [('department_id', '=', department.id)]))
            if counts and min(counts) < 6:
                cycle.small_team_warning = _(
                    "A scoped department has fewer than 6 people: anonymous "
                    "feedback can often be guessed. Prefer department-level "
                    "aggregates.")
            else:
                cycle.small_team_warning = ''

    _CYCLE_TRANSITIONS = {
        'draft': {'open'},
        'open': {'calibration', 'draft'},
        'calibration': {'closed', 'open'},
        'closed': set(),
    }

    def _validate_state_change(self, target_state):
        """A review cycle is the frame a whole department is judged in: it
        moves one step at a time, only by a performance manager, and it does
        not close over reviews that are still open."""
        if not self.env.su and not self.env.user.has_group(
                'aic_hrm_base.group_hrm_manager'):
            raise UserError(_("Only performance managers may move a review cycle."))
        for cycle in self:
            if target_state not in self._CYCLE_TRANSITIONS[cycle.state]:
                raise UserError(_(
                    "Review cycle %(name)s cannot go from %(current)s to "
                    "%(target)s.", name=cycle.name, current=cycle.state,
                    target=target_state))
            if target_state == 'closed':
                unfinished = cycle.review_ids.filtered(lambda r: not r.is_final)
                if unfinished:
                    raise UserError(_(
                        "%(count)s review(s) of %(name)s have not reached their "
                        "final stage yet.", count=len(unfinished), name=cycle.name))

    def write(self, vals):
        if 'state' in vals:
            self._validate_state_change(vals['state'])
        return super().write(vals)

    def action_generate_reviews(self):
        for cycle in self:
            domain = [('company_id', '=', cycle.company_id.id)]
            if cycle.department_ids:
                domain.append(
                    ('department_id', 'in', cycle.department_ids.ids))
            employees = self.env['hr.employee'].search(domain)
            existing = cycle.review_ids.mapped('employee_id')
            first_stage = cycle.template_id.stage_ids.sorted('sequence')[:1]
            missing = employees - existing
            if missing:
                self.env['aic.hrm.review'].create([{
                    'review_cycle_id': cycle.id,
                    'employee_id': employee.id,
                    'stage_id': first_stage.id,
                } for employee in missing])
            cycle.message_post(body=_(
                "%(created)s review(s) generated; %(total)s in this cycle.",
                created=len(missing), total=len(cycle.review_ids)))
            if cycle.state == 'draft':
                cycle.write({'state': 'open'})


class AicHrmReview(models.Model):
    _name = 'aic.hrm.review'
    _description = 'Performance Review'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'aic.hrm.owner.mixin']
    _rec_name = 'display_label'

    review_cycle_id = fields.Many2one(
        'aic.hrm.review.cycle', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='review_cycle_id.company_id', store=True, index=True)
    employee_id = fields.Many2one('hr.employee', required=True, index=True)
    display_label = fields.Char(compute='_compute_display_label', store=True)
    stage_id = fields.Many2one('aic.hrm.review.stage', tracking=True)
    is_final = fields.Boolean(compute='_compute_is_final', store=True)

    goal_score = fields.Float(
        readonly=True, copy=False, aggregator='avg',
        help="The goal score this appraisal was signed on: a snapshot, taken "
             "when the review reaches the manager stage or when a manager "
             "refreshes it. Later scorecard changes never rewrite it.")
    goal_score_live = fields.Float(
        compute='_compute_goal_live', aggregator='avg',
        help="What the scorecards say right now, for this cycle and the "
             "cycles inside it (a quarterly review reads its months).")
    goal_coverage_live = fields.Float(
        string='Goal Data Coverage (%)', compute='_compute_goal_live',
        aggregator='avg',
        help="Share of scorecard weight that actually has confirmed figures.")
    goal_score_snapshot_on = fields.Datetime(readonly=True, copy=False)
    goal_score_snapshot_by = fields.Many2one(
        'res.users', readonly=True, copy=False, string='Snapshot taken by')
    self_score = fields.Float()
    manager_score = fields.Float(tracking=True)
    peer_score_avg = fields.Float(
        compute='_compute_peer_feedback', aggregator='avg',
        help="Average anonymous peer rating, only once enough raters "
             "submitted.")
    peer_feedback_ready = fields.Boolean(compute='_compute_peer_feedback')
    calibrated_score = fields.Float(readonly=True, copy=False, tracking=True)
    final_score = fields.Float(
        compute='_compute_final_score', store=True, aggregator='avg')
    potential_rating = fields.Selection([
        ('1', 'Low'), ('2', 'Medium'), ('3', 'High'),
    ], help="Manager's potential estimate, feeds the 9-box grid.")
    nine_box_position = fields.Selection([
        ('star', 'Star'),
        ('high_performer', 'High performer'),
        ('workhorse', 'Workhorse'),
        ('growth_talent', 'Growth talent'),
        ('core_player', 'Core player'),
        ('solid_contributor', 'Solid contributor'),
        ('rough_diamond', 'Rough diamond'),
        ('inconsistent', 'Inconsistent'),
        ('underperformer', 'Underperformer'),
    ], compute='_compute_nine_box', store=True)
    pip_suggested = fields.Boolean(readonly=True, copy=False)
    feedback_request_ids = fields.One2many(
        'aic.hrm.feedback.request', 'review_id')

    _cycle_employee_uniq = models.Constraint(
        'unique (review_cycle_id, employee_id)',
        'This employee already has a review in this cycle.',
    )

    @api.depends('employee_id', 'review_cycle_id')
    def _compute_display_label(self):
        for review in self:
            review.display_label = (
                f'{review.employee_id.name or ""} · '
                f'{review.review_cycle_id.name or ""}')

    @api.depends('stage_id')
    def _compute_is_final(self):
        for review in self:
            review.is_final = review.stage_id.stage_type == 'final'

    @api.depends('manager_score', 'calibrated_score')
    def _compute_final_score(self):
        for review in self:
            review.final_score = (review.calibrated_score
                                  or review.manager_score)

    def _peer_stage(self):
        self.ensure_one()
        return self.review_cycle_id.template_id.stage_ids.filtered(
            lambda s: s.stage_type == 'peer_feedback')[:1]

    @api.depends('feedback_request_ids.state')
    def _compute_peer_feedback(self):
        Response = self.env['aic.hrm.feedback.response'].sudo()
        for review in self:
            requests = review.feedback_request_ids.filtered(
                lambda r: r.rater_role == 'peer'
                and r.state == 'submitted')
            min_raters = review._peer_stage().min_raters or 3
            if len(requests) < min_raters:
                review.peer_feedback_ready = False
                review.peer_score_avg = 0.0
                continue
            responses = Response.search([
                ('request_id', 'in', requests.ids),
                ('rating', '>', 0),
            ])
            ratings = []
            for response in responses:
                scale = response.question_id._rating_scale()
                ratings.append(response.rating / scale)
            review.peer_feedback_ready = True
            review.peer_score_avg = (
                sum(ratings) / len(ratings) if ratings else 0.0)

    @api.depends('final_score', 'potential_rating')
    def _compute_nine_box(self):
        def band(score):
            if score >= 0.7:
                return 'high'
            if score >= 0.4:
                return 'medium'
            return 'low'

        potential_bands = {'1': 'low', '2': 'medium', '3': 'high'}
        for review in self:
            if not review.potential_rating:
                review.nine_box_position = False
                continue
            review.nine_box_position = _NINE_BOX[(
                band(review.final_score),
                potential_bands[review.potential_rating])]

    def _goal_scorecards(self):
        """Scorecards this review is judged on: the performance cycle itself
        and every cycle inside it, because KPIs are usually assigned monthly
        while a review covers a quarter or a year."""
        self.ensure_one()
        perf_cycle = self.review_cycle_id.perf_cycle_id
        if not perf_cycle:
            return self.env['aic.hrm.kpi.assignment']
        cycles = self.env['aic.hrm.cycle'].search(
            [('id', 'child_of', perf_cycle.id)])
        return self.env['aic.hrm.kpi.assignment'].search([
            ('cycle_id', 'in', cycles.ids),
            ('employee_id', '=', self.employee_id.id)])

    @api.depends('review_cycle_id.perf_cycle_id', 'employee_id')
    def _compute_goal_live(self):
        for review in self:
            cards = review._goal_scorecards()
            measured = cards.filtered('data_coverage')
            review.goal_score_live = (
                sum(measured.mapped('score_covered')) / len(measured)
                if measured else 0.0)
            review.goal_coverage_live = (
                sum(cards.mapped('data_coverage')) / len(cards) if cards else 0.0)

    def _snapshot_goal_score(self):
        """Freeze the goal score onto the review, with who and when."""
        for review in self:
            review.sudo().write({
                'goal_score': review.goal_score_live,
                'goal_score_snapshot_on': fields.Datetime.now(),
                'goal_score_snapshot_by': self.env.uid,
            })
            review.message_post(body=_(
                "Goal score fixed at %(score)s%% (data coverage %(coverage)s%%).",
                score=round(100 * review.goal_score_live, 1),
                coverage=round(review.goal_coverage_live, 1)))

    def action_refresh_goal_score(self):
        """Re-read the scorecards and fix the result onto the review."""
        if not self.env.su and not self.env.user.has_group(
                'aic_hrm_base.group_hrm_manager'):
            raise UserError(_(
                "Only performance managers may fix the goal score of a review."))
        self._snapshot_goal_score()
        return True

    feedback_submitted_count = fields.Integer(
        compute='_compute_feedback_progress',
        help="Submitted 360 invitations — aggregate only, never per-rater.")
    feedback_invited_count = fields.Integer(
        compute='_compute_feedback_progress')

    def _compute_feedback_progress(self):
        # Managers see progress as counts only; rows stay unreadable.
        for review in self:
            requests = review.sudo().feedback_request_ids
            review.feedback_invited_count = len(requests)
            review.feedback_submitted_count = len(requests.filtered(
                lambda r: r.state == 'submitted'))

    def write(self, vals):
        manager_fields = {'manager_score', 'potential_rating',
                          'calibrated_score'}
        if manager_fields & set(vals) and not self.env.su and \
                not self.env.user.has_group('aic_hrm_base.group_hrm_manager'):
            raise UserError(_(
                "Only performance managers may set manager, potential or "
                "calibrated ratings."))
        if vals.get('stage_id'):
            # From the manager stage onwards the appraisal is being signed, so
            # the goal score stops moving: it is frozen on the way in.
            stage = self.env['aic.hrm.review.stage'].browse(vals['stage_id'])
            if self._stage_needs_snapshot(stage):
                for review in self.filtered(lambda r: not r.goal_score_snapshot_on):
                    review._snapshot_goal_score()
        if 'self_score' in vals and not self.env.su and \
                not self.env.user.has_group('aic_hrm_base.group_hrm_admin'):
            for review in self:
                is_owner = review.employee_id.user_id == self.env.user
                in_self_stage = review.stage_id.stage_type == 'self'
                if not (is_owner and in_self_stage):
                    raise UserError(_(
                        "Self-assessment is written by the employee, during "
                        "the self stage only."))
        return super().write(vals)

    _SNAPSHOT_STAGES = ('manager', 'calibration', 'final')

    def _stage_needs_snapshot(self, stage):
        return stage.stage_type in self._SNAPSHOT_STAGES

    def action_next_stage(self):
        for review in self:
            stages = review.review_cycle_id.template_id.stage_ids.sorted(
                'sequence')
            stage_list = list(stages)
            index = stage_list.index(review.stage_id) \
                if review.stage_id in stage_list else -1
            if index + 1 >= len(stage_list):
                raise UserError(_("The review is already at its final "
                                  "stage."))
            review.stage_id = stage_list[index + 1]

    def action_finalize_review(self):
        for review in self:
            if not review.goal_score_snapshot_on and not review.goal_score:
                raise UserError(_(
                    "Fix the goal score of %(name)s first: an appraisal must "
                    "not be signed on a figure that can still move.",
                    name=review.display_label))
            final_stage = review.review_cycle_id.template_id.stage_ids \
                .filtered(lambda s: s.stage_type == 'final')[:1]
            review.stage_id = final_stage
            if review.final_score < _PIP_THRESHOLD:
                review.pip_suggested = True
                review._suggest_pip()

    def _suggest_pip(self):
        Idp = self.env['aic.hrm.idp']
        for review in self:
            existing = Idp.search([
                ('review_id', '=', review.id),
                ('plan_type', '=', 'pip')], limit=1)
            if existing:
                continue
            Idp.create({
                'employee_id': review.employee_id.id,
                'review_id': review.id,
                'plan_type': 'pip',
                'action_ids': [
                    (0, 0, {'name': _('30-day checkpoint: agree the '
                                      'improvement goals'),
                            'action_type': 'checkpoint'}),
                    (0, 0, {'name': _('60-day checkpoint: review progress '
                                      'evidence'),
                            'action_type': 'checkpoint'}),
                    (0, 0, {'name': _('90-day checkpoint: final decision'),
                            'action_type': 'checkpoint'}),
                ],
            })
