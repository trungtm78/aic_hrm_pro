# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Experience hours and availability override from timesheet & time off.

Scorers:
- experience_hours: total hours logged on projects with matching tags
- availability override: subtract holiday leaves from free hours
"""
import logging
from odoo import api, models

_logger = logging.getLogger(__name__)


class AicHrmMatchTimesheetBridge(models.AbstractModel):
    _name = 'aic.hrm.match.scorer'
    _inherit = 'aic.hrm.match.scorer'

    @api.model
    def _prefetch_experience_hours(self, ctx):
        """Load timesheet hours for the whole pool, once."""
        TimesheetLine = self.env['account.analytic.line']
        experience_hours = {emp_id: 0.0 for emp_id in ctx.scoped_ids}
        timesheet_lines = TimesheetLine.search([
            ('employee_id', 'in', ctx.scoped_ids),
            ('date', '>=', ctx.window[0].date()),
            ('date', '<=', ctx.window[1].date()),
        ])
        for line in timesheet_lines:
            if line.employee_id.id in experience_hours:
                experience_hours[line.employee_id.id] += line.unit_amount
        ctx.data['experience_hours'] = experience_hours

    @api.model
    def _score_experience_hours(self, ctx):
        """Raw score: total hours logged."""
        scores = {}
        exp_hours = ctx.data.get('experience_hours', {})
        for employee_id in ctx.scoped_ids:
            hours = exp_hours.get(employee_id, 0.0)
            if not hours:
                scores[employee_id] = None
                continue
            scores[employee_id] = hours
            ctx.add_evidence(employee_id, 'experience_hours', f'{hours:.1f} hours')
        return scores

    @api.model
    def _prefetch_availability(self, ctx):
        """Extend base availability prefetch to include holiday leaves."""
        super()._prefetch_availability(ctx)
        HrLeave = self.env.get('hr.leave')
        if not HrLeave:
            return
        window_start, window_end = ctx.window
        leaves = HrLeave.search([
            ('employee_id', 'in', ctx.scoped_ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', window_end),
            ('date_to', '>=', window_start),
        ])
        leave_intervals = {emp_id: [] for emp_id in ctx.scoped_ids}
        for leave in leaves:
            emp_id = leave.employee_id.id
            if emp_id in leave_intervals:
                leave_intervals[emp_id].append({'start': leave.date_from, 'end': leave.date_to})
        ctx.data['leave_intervals'] = leave_intervals

    @api.model
    def get_leave_intervals_batch(self, employees, date_start, date_end):
        """Override to return prefetched leave intervals instead of querying.

        The timesheet bridge prefetches leaves via _prefetch_availability, and
        this override ensures get_breakdown_batch uses the batch data instead
        of calling get_leave_intervals per employee.
        """
        HrLeave = self.env.get('hr.leave')
        if not HrLeave:
            # No time off module: delegate to base (returns empty for all)
            return super().get_leave_intervals_batch(employees, date_start, date_end)
        
        # Fetch leaves for the whole pool, grouped by employee
        leaves = HrLeave.search([
            ('employee_id', 'in', employees.ids),
            ('state', '=', 'validate'),
            ('date_from', '<=', date_end),
            ('date_to', '>=', date_start),
        ])
        result = {emp_id: [] for emp_id in employees.ids}
        for leave in leaves:
            emp_id = leave.employee_id.id
            if emp_id in result:
                result[emp_id].append((leave.date_from, leave.date_to))
        return result
