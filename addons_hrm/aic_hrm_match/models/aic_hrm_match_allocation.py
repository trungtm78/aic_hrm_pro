# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What somebody has already been committed to.

An allocation is the difference between "this person looks free" and "this
person is free". Without it the engine ranks on skills alone and cheerfully
proposes the one developer every other project is already relying on.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# States that actually consume somebody's time. A draft is a planner thinking
# out loud; treating it as busy hides available people from every other planner,
# which is how a booking system ends up being worked around in a spreadsheet.
BLOCKING_STATES = ('proposed', 'confirmed', 'done')


class AicHrmMatchAllocation(models.Model):
    _name = 'aic.hrm.match.allocation'
    _description = 'Staffing Allocation'
    _order = 'date_start, id'

    employee_id = fields.Many2one(
        'hr.employee', required=True, index=True, ondelete='cascade')
    resource_id = fields.Many2one(
        'resource.resource', related='employee_id.resource_id', store=True)
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)

    date_start = fields.Datetime(required=True, index=True)
    date_end = fields.Datetime(required=True, index=True)
    allocated_hours = fields.Float(
        required=True, default=0.0,
        help="Effort committed inside the window. Prorated when only part of "
             "the booking falls inside the period being looked at.")

    booking_type = fields.Selection([
        ('soft', 'Soft (pencilled in)'),
        ('hard', 'Hard (committed)'),
        ('actual', 'Actual (already worked)'),
    ], default='hard', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('proposed', 'Proposed'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, index=True)
    is_blocking = fields.Boolean(
        compute='_compute_is_blocking', store=True, index=True,
        help="Whether this booking consumes availability. Stored so the "
             "engine can filter on it in SQL rather than in Python.")

    # `set null` rather than cascade throughout: deleting a task must not
    # silently delete the record that a staffing decision was based on.
    task_id = fields.Many2one('project.task', ondelete='set null', index=True)
    task_ref_snapshot = fields.Char(
        readonly=True,
        help="The task this booking came from, captured at creation so the "
             "trail survives the task being deleted.")
    project_id = fields.Many2one('project.project', ondelete='set null')
    partner_id = fields.Many2one('res.partner', ondelete='set null', index=True)

    source = fields.Selection([
        ('manual', 'Entered by hand'),
        ('match_run', 'From a staffing decision'),
        ('task_sync', 'Derived from a task'),
        ('import', 'Imported'),
        ('bridge', 'From a connector'),
    ], default='manual', required=True)
    role_note = fields.Char()

    @api.depends('state')
    def _compute_is_blocking(self):
        for allocation in self:
            allocation.is_blocking = allocation.state in BLOCKING_STATES

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for allocation in self:
            if allocation.date_end <= allocation.date_start:
                raise ValidationError(_(
                    "A booking must end after it starts. Check %(name)s.",
                    name=allocation.display_name))

    @api.constrains('allocated_hours')
    def _check_hours(self):
        for allocation in self:
            if allocation.allocated_hours < 0.0:
                raise ValidationError(_(
                    "A booking cannot commit negative hours."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('task_id') and not vals.get('task_ref_snapshot'):
                task = self.env['project.task'].browse(vals['task_id'])
                vals['task_ref_snapshot'] = task.display_name
        return super().create(vals_list)
