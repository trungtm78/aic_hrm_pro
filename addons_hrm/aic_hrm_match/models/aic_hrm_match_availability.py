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
from datetime import datetime

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
        if isinstance(value, datetime) and value.tzinfo is not None:
            # Already in the space this service works in. Passing it through
            # fields.Datetime.to_datetime would raise, because that helper
            # exists to keep aware values *out* of the database - the opposite
            # of what is wanted for a value being handed back to the calendar.
            return value
        moment = fields.Datetime.to_datetime(value)
        if moment is None:
            return None
        return pytz.utc.localize(moment)

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
        return self.get_gross_intervals_batch(
            employee, date_start, date_end).get(employee.id, [])

    @api.model
    def get_gross_intervals_batch(self, employees, date_start, date_end):
        """``{employee_id: intervals}``, one calendar pass per calendar.

        This is where the performance budget is won or lost. Called once per
        employee, ``_work_intervals_batch`` is two thousand round trips for a
        pool of two thousand, and the three-second ranking becomes a minute.

        Grouped by calendar and passed every resource that shares it, which is
        what the "batch" in the method's name is for. Note what is *not* done:
        the answer is not computed once per calendar and reused. Two people on
        the same calendar can still differ - leave is recorded per resource,
        time zones are per resource, and fortnightly patterns land on different
        weeks - so each resource keeps its own answer. The saving is in the
        number of calls, not in pretending colleagues are interchangeable.
        """
        result = {}
        by_calendar = {}
        for employee in employees:
            calendar = self._calendar_for(employee)
            if not calendar or not employee.resource_id:
                result[employee.id] = []
                continue
            by_calendar.setdefault(calendar, []).append(employee)

        start = self._to_datetime(date_start)
        end = self._to_datetime(date_end)
        for calendar, group in by_calendar.items():
            resources = self.env['resource.resource'].browse(
                [employee.resource_id.id for employee in group])
            intervals = calendar._work_intervals_batch(
                start, end, resources=resources, compute_leaves=False)
            for employee in group:
                result[employee.id] = self._plain(
                    intervals.get(employee.resource_id.id, []))
        return result

    @api.model
    def get_leave_intervals(self, employee, date_start, date_end):
        """Approved absence, as intervals.

        Empty here on purpose: this app depends on Employees and Project, not
        on Time Off. The connector overrides this one method and the rest of
        the calculation picks it up unchanged.
        """
        return []

    @api.model
    def _blocking_allocations_batch(self, employees, window_start, window_end):
        """Every commitment that touches the window, for the whole pool, in one
        search - then grouped in Python. One query, not one per person."""
        allocations = self.env['aic.hrm.match.allocation'].search([
            ('employee_id', 'in', employees.ids),
            ('is_blocking', '=', True),
            ('date_start', '<=', window_end.replace(tzinfo=None)),
            ('date_end', '>=', window_start.replace(tzinfo=None)),
        ])
        grouped = {}
        for allocation in allocations:
            grouped.setdefault(allocation.employee_id.id, []).append(allocation)
        return grouped

    @api.model
    def _blocking_allocations(self, employee, window_start, window_end):
        return self._blocking_allocations_batch(
            employee, window_start, window_end).get(employee.id, [])

    @api.model
    def _split_bookings(self, allocations, working):
        """Separate the commitments that fill their span from the ones that
        merely reduce it.

        Two commitments are not the same kind of thing, and treating them alike
        breaks the calculation in one direction or the other. Sixty-four hours
        booked across a forty-hour week means the person is *gone*: the span is
        theirs, and a second booking overlapping it costs nothing extra because
        there is nothing left to take. Twelve hours across the same week means
        the person is *reduced*: no day is closed, and a second twelve-hour
        booking does cost another twelve hours.

        So the dense ones are unioned as intervals - the union is what stops
        two overlapping full bookings from removing the same afternoon twice -
        and the partial ones are prorated as hours against the time the dense
        ones left behind.

        ``working`` is the employee's attendance minus leave over a range wide
        enough to contain every booking, because intensity is measured against
        the working time of the booking's *own* span: a two-week booking judged
        against one week of capacity would look twice as intense as it is.
        """
        dense, partial = [], []
        for allocation in allocations:
            span = (pytz.utc.localize(allocation.date_start),
                    pytz.utc.localize(allocation.date_end))
            span_hours = self.to_hours(
                utils.intersect_intervals(working, [span]))
            if span_hours <= 0.0:
                # Booked entirely outside the person's working time - a
                # weekend placeholder, or a calendar that changed after the
                # booking was made. It takes nothing from a week it never
                # touches, and dividing by its span would divide by zero.
                continue
            # A booking with no hours on it consumes none, which is what the
            # clash guard also concludes when it prorates. The two must agree:
            # a booking the guard lets through as costless cannot be the reason
            # somebody disappears from a shortlist.
            intensity = min(1.0, allocation.allocated_hours / span_hours)
            if intensity >= 1.0:
                dense.append(span)
            elif intensity > 0.0:
                partial.append((span, intensity))
        return utils.merge_intervals(dense), partial

    @api.model
    def get_booked_intervals(self, employee, date_start, date_end):
        """Time a commitment has taken over completely.

        Returned as a union, so two bookings sharing an hour occupy one hour of
        the person's day rather than two. A part-time commitment is not here -
        it reduces the hours without closing any particular day, and appears in
        ``get_free_hours`` instead.
        """
        window_start = self._to_datetime(date_start)
        window_end = self._to_datetime(date_end)
        allocations = self._blocking_allocations(
            employee, window_start, window_end)
        if not allocations:
            return []
        span_start = min([window_start] + [pytz.utc.localize(a.date_start)
                                           for a in allocations])
        span_end = max([window_end] + [pytz.utc.localize(a.date_end)
                                       for a in allocations])
        working = utils.subtract_intervals(
            self.get_gross_intervals(employee, span_start, span_end),
            self.get_leave_intervals(employee, span_start, span_end))
        dense, _partial = self._split_bookings(allocations, working)
        return utils.intersect_intervals(dense, [(window_start, window_end)])

    # -- the answer ---------------------------------------------------------

    @api.model
    def get_free_intervals(self, employee, date_start, date_end):
        """*When* the person is open: working time with leave and the
        commitments that fill their span taken out, once each.

        Deliberately not the same question as ``get_free_hours``. This one
        drives the calendar and the capacity board, where a day someone is 30%
        booked is still a day they can be asked about.
        """
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
        """*How much* the person has left, which is what the gate and the score
        are about.

        Never larger than the free intervals are long, and usually smaller:
        part-time commitments take hours out without closing days.
        """
        return self.get_breakdown(employee, date_start, date_end)['free_hours']

    @api.model
    def get_breakdown(self, employee, date_start, date_end):
        """``capacity - leave - booked = free``, as the four numbers a reader
        needs to check the arithmetic themselves.
        """
        return self.get_breakdown_batch(
            employee, date_start, date_end)[employee.id]

    @api.model
    def get_breakdown_batch(self, employees, date_start, date_end):
        """The four numbers for a whole pool, reading each source once.

        This is the method the engine calls, and the reason the other forms
        delegate to it rather than the other way round. Asking per employee
        means one calendar pass and one allocation search each; for two
        thousand people that is four thousand round trips, and it is the whole
        difference between a three-second ranking and a minute.

        Derived from the same interval algebra that produces the free hours
        rather than recomputed alongside it. A second calculation that agrees
        most of the time is worse than none: the row would stop adding up in
        exactly the awkward cases - a booking overlapping a public holiday -
        and look authoritative doing it.
        """
        window_start = self._to_datetime(date_start)
        window_end = self._to_datetime(date_end)
        window = [(window_start, window_end)]

        allocations_by_employee = self._blocking_allocations_batch(
            employees, window_start, window_end)

        # One calendar pass over a range wide enough to hold every booking any
        # of them has: an allocation's intensity is measured against the
        # working time of its own span, which may start before the window or
        # end after it. Widening here costs nothing extra and saves a second
        # pass per employee.
        span_start, span_end = window_start, window_end
        for allocations in allocations_by_employee.values():
            for allocation in allocations:
                span_start = min(span_start,
                                 pytz.utc.localize(allocation.date_start))
                span_end = max(span_end,
                               pytz.utc.localize(allocation.date_end))
        gross_by_employee = self.get_gross_intervals_batch(
            employees, span_start, span_end)

        result = {}
        for employee in employees:
            gross_span = gross_by_employee.get(employee.id, [])
            leave_span = self.get_leave_intervals(
                employee, span_start, span_end)
            working = utils.subtract_intervals(gross_span, leave_span)

            gross = utils.intersect_intervals(gross_span, window)
            leave = utils.intersect_intervals(leave_span, window)
            available = utils.intersect_intervals(working, window)

            dense, partial = self._split_bookings(
                allocations_by_employee.get(employee.id, []), working)
            remaining = utils.subtract_intervals(available, dense)
            free = self.to_hours(remaining)
            for span, intensity in partial:
                free -= intensity * self.to_hours(
                    utils.intersect_intervals(remaining, [span]))
            # Over-booking is a real state a deliberate tolerance can reach,
            # but a negative figure would rank an overloaded person above a
            # merely full one once it is normalised.
            free = max(0.0, free)

            available_hours = self.to_hours(available)
            result[employee.id] = {
                'capacity_hours': self.to_hours(gross),
                'leave_hours': self.to_hours(leave),
                # What the bookings took, by difference. Capped at what there
                # was to take - a row reading "booked 60 of 40" invites the
                # reader to conclude the report is broken rather than the
                # schedule.
                'booked_hours': max(0.0, available_hours - free),
                'free_hours': free,
            }
        return result

    @api.model
    def get_free_hours_batch(self, employees, date_start, date_end):
        """``{employee_id: free_hours}`` for a whole pool."""
        return {
            employee_id: row['free_hours']
            for employee_id, row in self.get_breakdown_batch(
                employees, date_start, date_end).items()
        }
