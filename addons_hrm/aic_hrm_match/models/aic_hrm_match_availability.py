# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""How much time somebody actually has inside a window.

This is the criterion that eliminates rather than ranks, so an error here does
not shift a score by a little - it removes the right person from the shortlist,
or books somebody who is not there.

The whole calculation is interval algebra and converts to hours exactly once,
at the very end. That is not stylistic. Two things break the moment hours are
added and subtracted instead:

* ``resource.calendar._work_intervals_batch`` subtracts calendar leave already
  (``compute_leaves`` defaults to True), so reading it that way and then
  subtracting leave again removes approved time off twice.
* A booking that overlaps a public holiday costs the person that time once.
  Subtracting two totals charges them for it twice and can report somebody as
  busier than the week is long.

An abstract model rather than a helper module so a connector can replace one
piece - the Time Off connector overrides ``get_leave_intervals`` and nothing
else changes.
"""
import pytz

from odoo import api, fields, models

from . import utils


class AicHrmMatchAvailability(models.AbstractModel):
    _name = 'aic.hrm.match.availability'
    _description = 'Staffing Availability Service'

    # -- plumbing -----------------------------------------------------------

    @api.model
    def _to_datetime(self, value):
        """Accept a string or a datetime and return it UTC-aware.

        Odoo stores datetimes naive in UTC, but ``_attendance_intervals_batch``
        asserts on ``tzinfo`` - a naive value fails there with a bare
        AssertionError that says nothing about what was wrong. Localising here
        keeps every caller from having to remember.
        """
        moment = fields.Datetime.to_datetime(value)
        if moment is None:
            return None
        return pytz.utc.localize(moment) if moment.tzinfo is None else moment

    @api.model
    def to_hours(self, intervals):
        """The single place where intervals become a number."""
        return utils.interval_hours(intervals)

    @api.model
    def _plain(self, intervals):
        """Odoo's interval containers carry a third element (the records that
        produced them). Everything below is pure time algebra, so it is
        dropped here rather than being carried through every operation.
        """
        return [(item[0], item[1]) for item in intervals]

    @api.model
    def _calendar_for(self, employee):
        """A missing calendar is a data gap, not zero availability.

        Scoring an employee without a calendar as unavailable would silently
        exclude everybody whose HR record is incomplete - the people most
        likely to be new, and least likely to have someone noticing.
        """
        return (employee.resource_calendar_id
                or employee.company_id.resource_calendar_id
                or self.env.company.resource_calendar_id)

    # -- the three sources --------------------------------------------------

    @api.model
    def get_gross_intervals(self, employee, date_start, date_end):
        """Attendance only, before anything is taken away.

        ``compute_leaves=False`` is the load-bearing argument: with the default
        this would already have leave removed, and the subtraction below would
        remove it a second time.
        """
        calendar = self._calendar_for(employee)
        if not calendar:
            return []
        intervals = calendar._work_intervals_batch(
            self._to_datetime(date_start), self._to_datetime(date_end),
            resources=employee.resource_id, compute_leaves=False)
        return self._plain(intervals.get(employee.resource_id.id, []))

    @api.model
    def get_leave_intervals(self, employee, date_start, date_end):
        """Approved absence, as intervals.

        Empty here on purpose: this app depends on Employees and Project, not
        on Time Off. The connector overrides this one method and the rest of
        the calculation picks it up unchanged.
        """
        return []

    @api.model
    def get_booked_intervals(self, employee, date_start, date_end):
        """Time already committed by a blocking allocation.

        Returned as a union, so two bookings sharing an hour occupy one hour of
        the person's day rather than two.
        """
        window_start = self._to_datetime(date_start)
        window_end = self._to_datetime(date_end)
        allocations = self.env['aic.hrm.match.allocation'].search([
            ('employee_id', '=', employee.id),
            ('is_blocking', '=', True),
            ('date_start', '<=', window_end.replace(tzinfo=None)),
            ('date_end', '>=', window_start.replace(tzinfo=None)),
        ])
        # Allocation columns are naive UTC; the window is aware. Bring the
        # bookings into the window's space rather than the other way round, so
        # every interval that leaves this service is comparable with the
        # calendar's.
        return utils.merge_intervals(
            (max(pytz.utc.localize(a.date_start), window_start),
             min(pytz.utc.localize(a.date_end), window_end))
            for a in allocations)

    # -- the answer ---------------------------------------------------------

    @api.model
    def get_free_intervals(self, employee, date_start, date_end):
        """Working time with leave and bookings taken out, once each."""
        gross = self.get_gross_intervals(employee, date_start, date_end)
        unavailable = (
            self.get_leave_intervals(employee, date_start, date_end)
            + self.get_booked_intervals(employee, date_start, date_end))
        return utils.subtract_intervals(gross, unavailable)

    @api.model
    def get_gross_hours(self, employee, date_start, date_end):
        return self.to_hours(
            self.get_gross_intervals(employee, date_start, date_end))

    @api.model
    def get_free_hours(self, employee, date_start, date_end):
        return self.to_hours(
            self.get_free_intervals(employee, date_start, date_end))

    @api.model
    def get_free_hours_batch(self, employees, date_start, date_end):
        """``{employee_id: free_hours}`` for a whole pool.

        The engine calls this once for two thousand people. It must agree with
        the single-employee form to the decimal, or the ranking and the
        candidate detail screen tell the reader different stories about the
        same person.
        """
        return {
            employee.id: self.get_free_hours(employee, date_start, date_end)
            for employee in employees
        }
