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
    def _blocking_allocations(self, employee, window_start, window_end):
        return self.env['aic.hrm.match.allocation'].search([
            ('employee_id', '=', employee.id),
            ('is_blocking', '=', True),
            ('date_start', '<=', window_end.replace(tzinfo=None)),
            ('date_end', '>=', window_start.replace(tzinfo=None)),
        ])

    @api.model
    def _split_bookings(self, employee, window_start, window_end):
        """Separate the commitments that fill their span from the ones that
        merely reduce it, and return both with the working time they are
        measured against.

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

        Intensity is measured against the working time of the booking's *own*
        span, which may start before the window or end after it. That is why
        the calendar is read once over a range wide enough to hold every
        booking rather than over the window: a two-week booking judged against
        one week of capacity would look twice as intense as it is.
        """
        allocations = self._blocking_allocations(
            employee, window_start, window_end)
        if not allocations:
            return [], []

        spans = [(pytz.utc.localize(a.date_start), pytz.utc.localize(a.date_end))
                 for a in allocations]
        span_start = min([window_start] + [s for s, _e in spans])
        span_end = max([window_end] + [e for _s, e in spans])
        working = utils.subtract_intervals(
            self.get_gross_intervals(employee, span_start, span_end),
            self.get_leave_intervals(employee, span_start, span_end))

        dense, partial = [], []
        for allocation, span in zip(allocations, spans):
            span_hours = self.to_hours(
                utils.intersect_intervals(working, [span]))
            if span_hours <= 0.0:
                # Booked entirely outside the person's working time - a
                # weekend placeholder, say. It takes nothing from a week it
                # never touches.
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
        dense, _partial = self._split_bookings(
            employee, window_start, window_end)
        # Allocation columns are naive UTC; the window is aware. Bring the
        # bookings into the window's space rather than the other way round, so
        # every interval that leaves this service is comparable with the
        # calendar's.
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
        window_start = self._to_datetime(date_start)
        window_end = self._to_datetime(date_end)
        window = [(window_start, window_end)]
        available = utils.intersect_intervals(
            utils.subtract_intervals(
                self.get_gross_intervals(employee, date_start, date_end),
                self.get_leave_intervals(employee, date_start, date_end)),
            window)
        dense, partial = self._split_bookings(
            employee, window_start, window_end)
        remaining = utils.subtract_intervals(available, dense)

        free = self.to_hours(remaining)
        for span, intensity in partial:
            free -= intensity * self.to_hours(
                utils.intersect_intervals(remaining, [span]))
        # Over-booking is a real state a deliberate tolerance can reach, but a
        # negative figure would rank an overloaded person above a merely full
        # one once it is normalised.
        return max(0.0, free)

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
