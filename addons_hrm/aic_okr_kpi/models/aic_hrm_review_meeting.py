# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError

from markupsafe import escape, Markup


class AicHrmReviewMeeting(models.Model):
    """Periodic review ritual: agenda auto-built from what is red, stale or
    blocked; minutes and tracked action items close the loop."""
    _name = 'aic.hrm.review.meeting'
    _description = 'Review Meeting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(required=True)
    cycle_id = fields.Many2one(
        'aic.hrm.cycle', required=True, ondelete='restrict')
    company_id = fields.Many2one(
        related='cycle_id.company_id', store=True, index=True)
    date = fields.Date(required=True)
    attendee_ids = fields.Many2many('hr.employee', string='Attendees')
    agenda = fields.Html(readonly=True, copy=False)
    minutes = fields.Html()
    action_item_ids = fields.One2many(
        'aic.hrm.meeting.action', 'meeting_id')
    open_action_count = fields.Integer(compute='_compute_open_actions')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('held', 'Held'),
        ('done', 'Done'),
    ], default='draft', required=True, tracking=True, copy=False)

    @api.depends('action_item_ids.state')
    def _compute_open_actions(self):
        for meeting in self:
            meeting.open_action_count = len(
                meeting.action_item_ids.filtered(
                    lambda a: a.state == 'todo'))

    def action_build_agenda(self):
        """Agenda = everything that needs management attention right now."""
        for meeting in self:
            cycle_domain = [('cycle_id', '=', meeting.cycle_id.id)]
            red_krs = self.env['aic.hrm.key.result'].search(
                cycle_domain + [('rag', '=', 'red')])
            stale_krs = self.env['aic.hrm.key.result'].search(
                cycle_domain + [('is_stale', '=', True)])
            blockers = self.env['aic.hrm.checkin'].search([
                ('kr_id.cycle_id', '=', meeting.cycle_id.id),
                ('blocker', '!=', False),
            ], order='date desc', limit=20)
            parts = [Markup('<h3>%s</h3>') % _("Auto-generated agenda")]

            def section(title, lines):
                if lines:
                    parts.append(Markup('<h4>%s</h4><ul>%s</ul>') % (
                        title, Markup('').join(
                            Markup('<li>%s</li>') % line for line in lines)))

            section(_("Red key results"), [
                f'{kr.code} {kr.name} — {kr.employee_id.name or "-"}'
                for kr in red_krs])
            section(_("Stale key results (no recent check-in)"), [
                f'{kr.code} {kr.name} — last {kr.last_checkin_date or "-"}'
                for kr in stale_krs])
            section(_("Open blockers from check-ins"), [
                f'{c.kr_id.code}: {c.blocker}' for c in blockers])
            if len(parts) == 1:
                parts.append(Markup('<p>%s</p>') % _(
                    "Nothing is red, stale or blocked. Confirm scores and "
                    "move on."))
            meeting.agenda = Markup('').join(parts)

    def action_hold(self):
        for meeting in self:
            if meeting.state != 'draft':
                raise UserError(_("Only draft meetings can be held."))
            if not meeting.agenda:
                meeting.action_build_agenda()
        self.write({'state': 'held'})

    def action_close(self):
        if any(meeting.state != 'held' for meeting in self):
            raise UserError(_("Only held meetings can be closed."))
        self.write({'state': 'done'})


class AicHrmMeetingAction(models.Model):
    _name = 'aic.hrm.meeting.action'
    _description = 'Meeting Action Item'
    _order = 'deadline, id'

    meeting_id = fields.Many2one(
        'aic.hrm.review.meeting', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='meeting_id.company_id', store=True)
    name = fields.Char(required=True)
    owner_id = fields.Many2one('hr.employee', required=True)
    deadline = fields.Date()
    state = fields.Selection([
        ('todo', 'To do'), ('done', 'Done'), ('cancelled', 'Cancelled'),
    ], default='todo', required=True)

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})
