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


class ResCompanyMatch(models.Model):
    _inherit = 'res.company'

    match_over_allocation_tolerance = fields.Float(
        string='Over-allocation tolerance',
        default=0.0,
        help="How far past somebody's working hours a booking may go, as a "
             "fraction. 0.0 refuses anything beyond capacity; 0.1 allows ten "
             "per cent. Some organisations plan deliberately above capacity "
             "and absorb it, which is a business decision rather than "
             "something to hard-code as allowed or forbidden.")


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

    # -- clash prevention ----------------------------------------------------

    # Our own advisory-lock namespace ('AIC1'), so a lock taken here can never
    # be confused with one taken by another module on the same integer.
    _LOCK_NAMESPACE = 0x41494331

    def _lock_employees(self, employee_ids):
        """Serialise capacity checks for the given people.

        Sorted ascending: two batches touching an overlapping set in opposite
        orders deadlock, and a fixed acquisition order is what removes the
        cycle.

        Transaction-scoped on purpose. ``pg_advisory_xact_lock`` is not
        released by a savepoint rollback, so an ORM retry cannot silently drop
        the guarantee halfway through the write it was protecting.
        """
        for employee_id in sorted({i for i in employee_ids if i}):
            self.env.cr.execute('SELECT pg_advisory_xact_lock(%s, %s)',
                                (self._LOCK_NAMESPACE, employee_id))

    def _prorated_hours(self, allocation, window_start, window_end):
        """How much of one booking lands inside a window.

        Prorated by *working* hours, not calendar time: a booking spanning a
        weekend costs its owner nothing on the Saturday, and dividing by
        elapsed days would quietly move effort onto days nobody works.

        Comparing whole booking totals against the capacity of a narrower
        window is the mistake this replaces - two four-hour bookings on one
        eight-hour day both overlap a 10:00-14:00 window and would together
        report eight committed hours against four available ones.
        """
        availability = self.env['aic.hrm.match.availability']
        employee = allocation.employee_id
        whole = availability.get_gross_hours(
            employee, allocation.date_start, allocation.date_end)
        if whole <= 0.0:
            # No working time under the booking at all: it is either entirely
            # outside the calendar or the calendar is empty. Charge it in full
            # so a booking across a weekend is still refused rather than
            # silently costing nothing.
            return allocation.allocated_hours
        inside = availability.get_gross_hours(
            employee,
            max(allocation.date_start, fields.Datetime.to_datetime(window_start)),
            min(allocation.date_end, fields.Datetime.to_datetime(window_end)))
        return allocation.allocated_hours * inside / whole

    def _assert_within_capacity(self, employee_ids, windows):
        """Refuse a commitment that puts somebody past their working hours.

        Must be called *after* the lock and *after* a flush, because it is the
        re-read that makes the lock worth taking: the numbers cached before
        acquiring it are exactly the stale ones the other transaction was
        about to invalidate.
        """
        availability = self.env['aic.hrm.match.availability']
        for employee in self.env['hr.employee'].browse(sorted(employee_ids)):
            tolerance = employee.company_id.match_over_allocation_tolerance
            for window_start, window_end in windows:
                capacity = availability.get_gross_hours(
                    employee, window_start, window_end)
                clashing = self.search([
                    ('employee_id', '=', employee.id),
                    ('is_blocking', '=', True),
                    ('date_start', '<=', window_end),
                    ('date_end', '>=', window_start),
                ])
                committed = sum(
                    self._prorated_hours(a, window_start, window_end)
                    for a in clashing)
                if committed > capacity * (1.0 + tolerance):
                    raise ValidationError(_(
                        "%(employee)s is committed to %(committed).1f hours "
                        "between %(start)s and %(end)s but only has "
                        "%(capacity).1f working hours there. Clashing "
                        "bookings: %(ids)s.",
                        employee=employee.display_name,
                        committed=committed, capacity=capacity,
                        start=window_start, end=window_end,
                        ids=', '.join(str(i) for i in clashing.ids)))

    def _guard_capacity(self, employee_ids, windows):
        """Lock, flush, re-read, validate - in that order.

        Any other order leaves a window where the check runs on data another
        transaction is already changing, which is the whole failure this
        exists to prevent.
        """
        if not employee_ids or not windows:
            return
        self._lock_employees(employee_ids)
        self.env.flush_all()
        self.invalidate_model(['allocated_hours', 'is_blocking',
                               'date_start', 'date_end', 'employee_id'])
        self._assert_within_capacity(employee_ids, windows)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('task_id') and not vals.get('task_ref_snapshot'):
                task = self.env['project.task'].browse(vals['task_id'])
                vals['task_ref_snapshot'] = task.display_name
        records = super().create(vals_list)
        blocking = records.filtered('is_blocking')
        blocking._guard_capacity(
            blocking.mapped('employee_id').ids,
            [(a.date_start, a.date_end) for a in blocking])
        return records

    def write(self, vals):
        # Both ends of a move: reassigning a booking frees capacity for one
        # person and consumes it for another, and locking only the new owner
        # leaves the old one's total wrong under concurrency.
        touched = set(self.mapped('employee_id').ids)
        windows = [(a.date_start, a.date_end) for a in self]
        result = super().write(vals)
        touched |= set(self.mapped('employee_id').ids)
        windows += [(a.date_start, a.date_end) for a in self]
        relevant = self.filtered('is_blocking')
        if relevant:
            relevant._guard_capacity(touched, windows)
        return result
