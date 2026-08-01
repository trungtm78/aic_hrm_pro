# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AicHrmIdp(models.Model):
    """Development plan (IDP) or performance improvement plan (PIP)."""
    _name = 'aic.hrm.idp'
    _description = 'Development / Improvement Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_label'

    employee_id = fields.Many2one('hr.employee', required=True, index=True)
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, index=True)
    review_id = fields.Many2one('aic.hrm.review', ondelete='set null')
    plan_type = fields.Selection([
        ('development', 'Development plan'),
        ('pip', 'Performance improvement plan'),
    ], default='development', required=True)
    display_label = fields.Char(compute='_compute_display_label', store=True)
    mentor_id = fields.Many2one('hr.employee')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False)
    action_ids = fields.One2many('aic.hrm.idp.action', 'idp_id')
    note = fields.Text()

    @api.depends('employee_id', 'plan_type')
    def _compute_display_label(self):
        for plan in self:
            kind = dict(self._fields['plan_type'].selection).get(
                plan.plan_type, '')
            plan.display_label = f'{plan.employee_id.name or ""} · {kind}'

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class AicHrmIdpAction(models.Model):
    _name = 'aic.hrm.idp.action'
    _description = 'Plan Action'
    _order = 'idp_id, date_due, id'

    idp_id = fields.Many2one(
        'aic.hrm.idp', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='idp_id.company_id', store=True)
    name = fields.Char(required=True)
    action_type = fields.Selection([
        ('training', 'Training'),
        ('project', 'Stretch project'),
        ('mentoring', 'Mentoring'),
        ('reading', 'Self-study'),
        ('checkpoint', 'Checkpoint'),
    ], default='training', required=True)
    date_due = fields.Date()
    state = fields.Selection([
        ('todo', 'To do'),
        ('in_progress', 'In progress'),
        ('done', 'Done'),
    ], default='todo', required=True)
    note = fields.Text()

    def action_done(self):
        self.write({'state': 'done'})
