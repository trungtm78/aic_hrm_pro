# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The two screens a planner actually starts from.

Nobody opens a staffing request first. They are looking at a task that needs
somebody on it, and the useful question is "who can take this, and when". So
the first wizard turns a task into a request, a slot and a ranking in one
press, carrying over everything the task already knows.

Both are transient, and that is the reason neither may hold the outcome. A
transient record is garbage-collected and has no chatter, so an assignment
recorded in a wizard is an assignment nobody can explain a week later. What
each one produces is a stored record: a request and a run, or a decision and
the bookings behind it.
"""
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AicHrmMatchWizardFindFit(models.TransientModel):
    _name = 'aic.hrm.match.wizard.find_fit'
    _description = 'Find Best Fit'

    task_id = fields.Many2one('project.task')
    project_id = fields.Many2one('project.project')
    partner_id = fields.Many2one('res.partner', string='Customer')

    name = fields.Char(string='What needs staffing')
    date_start = fields.Datetime(required=True)
    date_end = fields.Datetime(required=True)
    required_hours = fields.Float(
        default=0.0,
        help="Leave at zero to ask for whoever is free rather than for a fixed "
             "amount of effort.")
    priority = fields.Selection([
        ('0', 'Normal'), ('1', 'Important'), ('2', 'Urgent'),
    ], default='0')
    policy_id = fields.Many2one(
        'aic.hrm.match.policy', domain=[('state', '=', 'active')],
        help="Left empty, the policy that claims this request decides. Setting "
             "one here is how a planner runs an exceptional round without "
             "changing the rules for everybody else.")

    # A fortnight is long enough to be worth ranking and short enough that a
    # planner corrects it rather than accepting it out of inattention.
    _DEFAULT_WINDOW_DAYS = 14

    @api.model
    def default_get(self, fields_list):
        """Prefill from the task the planner came from.

        Making somebody retype the project, the customer and the dates that are
        already on the screen they arrived from is how a two-click flow turns
        into a form nobody opens twice.
        """
        values = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        start = fields.Datetime.to_datetime(str(today) + ' 00:00:00')
        end = start + relativedelta(days=self._DEFAULT_WINDOW_DAYS)

        if self.env.context.get('active_model') == 'project.task':
            task = self.env['project.task'].browse(
                self.env.context.get('active_id')).exists()
            if task:
                values.setdefault('task_id', task.id)
                values.setdefault('project_id', task.project_id.id)
                values.setdefault('partner_id',
                                  task.project_id.partner_id.id or False)
                values.setdefault('name', task.display_name)
                if task.date_deadline:
                    # A deadline is when the work has to be finished, so it is
                    # the end of the window rather than the start. Reading it as
                    # a start date would rank people for a fortnight that begins
                    # the day the job was already due.
                    deadline = fields.Datetime.to_datetime(
                        str(task.date_deadline)[:10] + ' 23:59:59')
                    end = deadline
                    start = min(start, deadline - relativedelta(
                        days=self._DEFAULT_WINDOW_DAYS))
        values.setdefault('date_start', start)
        values.setdefault('date_end', end)
        return values

    def action_create_and_rank(self):
        """Create the request and its slot, rank, and open the result."""
        self.ensure_one()
        if self.date_end <= self.date_start:
            # Caught here rather than by the request's own constraint so the
            # message lands on the screen the dates were typed on.
            raise UserError(_(
                "The window ends before it starts. Nobody can be free for "
                "negative time."))

        request = self.env['aic.hrm.match.request'].create({
            'name': self.name or (self.task_id.display_name
                                  or _('Staffing request')),
            'request_type': 'task' if self.task_id else 'standalone',
            'task_id': self.task_id.id,
            'project_id': self.project_id.id,
            'partner_id': self.partner_id.id,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'priority': self.priority,
        })
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id,
            'name': self.task_id.display_name or request.name,
            'required_hours': self.required_hours,
        })
        return request.action_rank()


class AicHrmMatchWizardAssign(models.TransientModel):
    _name = 'aic.hrm.match.wizard.assign'
    _description = 'Assign From Ranking'

    request_id = fields.Many2one('aic.hrm.match.request', readonly=True)
    run_id = fields.Many2one('aic.hrm.match.run', readonly=True)
    decision_ids = fields.One2many(
        'aic.hrm.match.wizard.assign.line', 'wizard_id', string='Assignments')

    @api.model
    def default_get(self, fields_list):
        """Open with the ranking's own recommendation already filled in.

        The common case is agreeing with it. Making a planner re-pick the name
        the screen just put in front of them adds a step that teaches nobody
        anything, and the override log is what captures the cases where they
        disagree.
        """
        values = super().default_get(fields_list)
        if self.env.context.get('active_model') != 'aic.hrm.match.run':
            return values
        run = self.env['aic.hrm.match.run'].browse(
            self.env.context.get('active_id')).exists()
        if not run:
            return values

        values['run_id'] = run.id
        values['request_id'] = run.request_id.id
        lines = []
        for slot in run.request_id.slot_ids:
            top = run.candidate_ids.filtered(
                lambda c, s=slot: c.eligible and c.slot_id == s
            ).sorted('rank')[:1]
            if not top:
                continue
            lines.append((0, 0, {
                'slot_id': slot.id,
                'candidate_id': top.id,
                'employee_id': top.employee_id.id,
                'score_at_decision': top.total_score,
            }))
        values['decision_ids'] = lines
        return values

    def action_assign(self):
        """Record the decisions and book the time, in one transaction.

        All of them together on purpose. Half-applied staffing - two seats
        booked and the third refused for a clash - leaves a plan nobody agreed
        to, and no screen afterwards shows that is what happened.
        """
        self.ensure_one()
        if not self.decision_ids:
            raise UserError(_(
                "Nothing is selected. Closing this without assigning anybody "
                "leaves the request exactly as it was, which is a fine outcome "
                "but not one to record as a decision."))

        decisions = self.env['aic.hrm.match.decision']
        for line in self.decision_ids:
            if not line.employee_id:
                raise UserError(_(
                    "%(slot)s has nobody chosen.", slot=line.slot_id.name))
            # The candidate row of the person actually chosen, not of the one
            # the ranking recommended. The decision snapshots their rank, and a
            # rank belonging to somebody else would make the override analysis
            # report that every choice agreed with the ranking.
            chosen = self.run_id.candidate_ids.filtered(
                lambda c, e=line.employee_id: c.employee_id == e)[:1]
            decisions |= self.env['aic.hrm.match.decision'].create({
                'request_id': self.request_id.id,
                'slot_id': line.slot_id.id,
                'run_id': self.run_id.id,
                'candidate_id': chosen.id,
                'employee_id': line.employee_id.id,
                # Somebody the ranking excluded is a different kind of
                # departure from somebody it merely ranked lower, and the two
                # are worth telling apart when the overrides are read back.
                'decision_type': 'waived' if (chosen and not chosen.eligible)
                                 else 'ranked',
                'override_reason': line.override_reason,
            })
        decisions.action_confirm()

        # Only now, and only once: the epoch rotates tie-breaks between genuine
        # staffing rounds, and a decision is what ends a round. Advancing it on
        # a re-rank would make the same request produce a different order every
        # time somebody pressed the button.
        self.request_id.sudo().write({
            'rotation_epoch': self.request_id.rotation_epoch + 1,
            'state': 'staffed',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'aic.hrm.match.request',
            'res_id': self.request_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class AicHrmMatchWizardAssignLine(models.TransientModel):
    _name = 'aic.hrm.match.wizard.assign.line'
    _description = 'Assignment To Confirm'

    wizard_id = fields.Many2one(
        'aic.hrm.match.wizard.assign', required=True, ondelete='cascade')
    slot_id = fields.Many2one('aic.hrm.match.request.slot', required=True)
    candidate_id = fields.Many2one('aic.hrm.match.candidate')
    employee_id = fields.Many2one('hr.employee', required=True)
    score_at_decision = fields.Float(readonly=True)
    is_override = fields.Boolean(compute='_compute_is_override')
    override_reason = fields.Text()

    @api.depends('employee_id', 'candidate_id')
    def _compute_is_override(self):
        """Derived, never typed: whether this is an override is a fact about
        who the ranking put first, not a box somebody remembered to tick."""
        for line in self:
            line.is_override = bool(
                line.candidate_id
                and line.employee_id != line.candidate_id.employee_id)
