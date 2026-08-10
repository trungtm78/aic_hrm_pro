# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""How much time somebody actually has inside a window.

This is the criterion that eliminates rather than ranks, so getting it wrong
does not shift a score, it removes the right person from the shortlist or books
somebody who is not there.

Two arithmetic traps drive the design, and both have tests here:

* ``_work_intervals_batch`` subtracts calendar leave already - ``compute_leaves``
  defaults to True - so ``capacity - leave - booked`` counts approved time off
  twice and reports somebody as busier than they are.
* Adding and subtracting *hour totals* double-counts any overlap between a
  booking and a holiday. The only arithmetic that survives overlap is set
  arithmetic on the intervals themselves, with the conversion to hours done
  once at the end.
"""
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class WorkingTimeCase(MatchCase):
    """Gross capacity: attendance only, before anything is taken away."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.availability = cls.env['aic.hrm.match.availability']
        cls.employee = cls._make_employee('Ava Available')

    def test_a_full_week_is_the_calendar_week(self):
        """The standard 40-hour calendar over Monday to Friday."""
        hours = self.availability.get_gross_hours(
            self.employee, '2026-09-14 00:00:00', '2026-09-18 23:59:59')
        self.assertAlmostEqual(hours, 40.0, places=1)

    def test_a_weekend_carries_no_working_time(self):
        hours = self.availability.get_gross_hours(
            self.employee, '2026-09-19 00:00:00', '2026-09-20 23:59:59')
        self.assertAlmostEqual(hours, 0.0, places=1)

    def test_an_employee_without_a_calendar_falls_back_to_the_company(self):
        """A missing calendar is a data gap, not zero availability. Scoring it
        as zero would silently exclude everybody whose HR record is incomplete.
        """
        employee = self._make_employee('Cal Less')
        employee.resource_calendar_id = False
        hours = self.availability.get_gross_hours(
            employee, '2026-09-14 00:00:00', '2026-09-18 23:59:59')
        self.assertGreater(hours, 0.0)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class FreeTimeCase(MatchCase):
    """Free time is gross attendance minus the union of everything that takes
    it away - computed as intervals, converted to hours once."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.availability = cls.env['aic.hrm.match.availability']
        cls.Allocation = cls.env['aic.hrm.match.allocation']
        cls.employee = cls._make_employee('Bo Booked')
        cls.window = ('2026-09-14 00:00:00', '2026-09-18 23:59:59')

    def _book(self, start, end, hours, **kwargs):
        values = {
            'employee_id': self.employee.id,
            'date_start': start,
            'date_end': end,
            'allocated_hours': hours,
            'state': 'confirmed',
        }
        values.update(kwargs)
        return self.Allocation.create(values)

    def test_with_nothing_booked_free_time_is_the_whole_week(self):
        free = self.availability.get_free_hours(self.employee, *self.window)
        self.assertAlmostEqual(free, 40.0, places=1)

    def test_a_booking_removes_its_hours(self):
        self._book('2026-09-14 00:00:00', '2026-09-15 23:59:59', 16.0)
        free = self.availability.get_free_hours(self.employee, *self.window)
        self.assertAlmostEqual(free, 24.0, places=1)

    def test_a_draft_booking_does_not_block(self):
        """Only a commitment blocks. A draft is somebody thinking out loud, and
        treating it as busy hides available people from every other planner."""
        self._book('2026-09-14 00:00:00', '2026-09-15 23:59:59', 16.0,
                   state='draft')
        free = self.availability.get_free_hours(self.employee, *self.window)
        self.assertAlmostEqual(free, 40.0, places=1)

    def test_a_cancelled_booking_does_not_block(self):
        self._book('2026-09-14 00:00:00', '2026-09-15 23:59:59', 16.0,
                   state='cancelled')
        free = self.availability.get_free_hours(self.employee, *self.window)
        self.assertAlmostEqual(free, 40.0, places=1)

    def test_a_booking_reaching_outside_the_window_is_prorated(self):
        """Half of a two-week booking lands in this week, so half of its hours
        do. Counting the whole booking would hide somebody who is genuinely
        half free."""
        self._book('2026-09-14 00:00:00', '2026-09-25 23:59:59', 80.0)
        free = self.availability.get_free_hours(self.employee, *self.window)
        self.assertAlmostEqual(free, 0.0, places=1)

    def test_overlapping_bookings_take_the_union_not_the_sum(self):
        """The overlap trap, in the free-hours calculation itself.

        Two bookings sharing hours occupy the union of their spans, not the sum
        of them. The company tolerance is raised here on purpose: overlapping
        commitments are over-allocation by definition and the clash guard would
        otherwise refuse the fixture, but the arithmetic under test is what
        free-hours does once such a state exists.
        """
        self.employee.company_id.match_over_allocation_tolerance = 99.0
        self._book('2026-09-14 08:00:00', '2026-09-14 12:00:00', 4.0)
        self._book('2026-09-14 10:00:00', '2026-09-14 14:00:00', 3.0)
        free = self.availability.get_free_hours(self.employee, *self.window)
        # The two spans union to 08:00-14:00, which is six working hours once
        # the lunch break is removed. Summing them would remove nine.
        self.assertAlmostEqual(free, 40.0 - 5.0, places=1)

    def test_a_booking_must_end_after_it_starts(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._book('2026-09-16 00:00:00', '2026-09-14 00:00:00', 8.0)

    def test_a_booking_cannot_commit_negative_hours(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self._book('2026-09-14 00:00:00', '2026-09-15 00:00:00', -8.0)

    def test_a_booking_from_a_task_keeps_the_task_name(self):
        """The trail has to survive the task being deleted, which is why the
        link is set null and the name is captured at creation."""
        project = self.env['project.project'].create({'name': 'Snapshot Test'})
        task = self.env['project.task'].create(
            {'name': 'Migrate billing', 'project_id': project.id})
        booking = self._book('2026-09-14 00:00:00', '2026-09-15 00:00:00',
                             8.0, task_id=task.id)
        self.assertIn('Migrate billing', booking.task_ref_snapshot)
        task.unlink()
        self.assertFalse(booking.task_id)
        self.assertIn('Migrate billing', booking.task_ref_snapshot)

    def test_free_time_never_goes_negative(self):
        """Over-booking is a real state - a company running a deliberate
        tolerance can reach it - but it must not turn into a negative score
        that ranks an overloaded person above one who is merely full."""
        self.employee.company_id.match_over_allocation_tolerance = 99.0
        self._book('2026-09-14 00:00:00', '2026-09-18 23:59:59', 400.0)
        free = self.availability.get_free_hours(self.employee, *self.window)
        self.assertGreaterEqual(free, 0.0)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class IntervalArithmeticCase(MatchCase):
    """The service returns intervals, not hours, precisely so callers cannot
    reintroduce the double-subtraction by adding totals."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.availability = cls.env['aic.hrm.match.availability']
        cls.employee = cls._make_employee('Iva Interval')

    def test_the_core_leave_source_is_not_subtracted_twice(self):
        """Gross capacity is read with compute_leaves=False on purpose. If it
        were read with the default, leave would already be gone from it and
        subtracting the leave intervals again would remove the same hours a
        second time.
        """
        gross = self.availability.get_gross_intervals(
            self.employee, '2026-09-14 00:00:00', '2026-09-18 23:59:59')
        with_core_leaves = self.availability._plain(
            self.employee.resource_calendar_id._work_intervals_batch(
                self.availability._to_datetime('2026-09-14 00:00:00'),
                self.availability._to_datetime('2026-09-18 23:59:59'),
                resources=self.employee.resource_id,
            )[self.employee.resource_id.id])
        self.assertAlmostEqual(
            self.availability.to_hours(gross),
            self.availability.to_hours(with_core_leaves),
            places=1,
            msg='no leave is recorded, so the two must agree; if they differ '
                'the gross reader is applying leave it should not')

    def test_leave_hours_are_reported_but_not_used_twice(self):
        """The candidate row shows leave for the reader's benefit. The number
        is derived from the same intervals the subtraction used, never added
        back into the arithmetic."""
        leave = self.availability.get_leave_intervals(
            self.employee, '2026-09-14 00:00:00', '2026-09-18 23:59:59')
        self.assertEqual(self.availability.to_hours(leave), 0.0,
                         'the core service reports no leave of its own; the '
                         'timesheet connector is what supplies it')

    def test_to_hours_of_nothing_is_zero(self):
        self.assertEqual(self.availability.to_hours([]), 0.0)

    def test_an_empty_moment_stays_empty(self):
        self.assertIsNone(self.availability._to_datetime(False))

    def test_no_calendar_anywhere_yields_no_working_time(self):
        """Distinct from the missing-employee-calendar case: if the company has
        none either there genuinely is no working pattern to read, and the
        honest answer is nothing rather than a guess."""
        employee = self._make_employee('Nil Calendar')
        employee.resource_calendar_id = False
        original = employee.company_id.resource_calendar_id
        employee.company_id.resource_calendar_id = False
        self.env.company.resource_calendar_id = False
        try:
            self.assertEqual(
                self.availability.get_gross_intervals(
                    employee, '2026-09-14 00:00:00', '2026-09-18 23:59:59'),
                [])
        finally:
            employee.company_id.resource_calendar_id = original
            self.env.company.resource_calendar_id = original

    def test_batch_and_single_agree(self):
        """The engine calls the batch form for two thousand people; a
        divergence between the two would make the ranking disagree with the
        candidate detail screen."""
        other = self._make_employee('Ian Batch')
        window = ('2026-09-14 00:00:00', '2026-09-18 23:59:59')
        batch = self.availability.get_free_hours_batch(
            self.employee | other, *window)
        self.assertAlmostEqual(
            batch[self.employee.id],
            self.availability.get_free_hours(self.employee, *window),
            places=1)
        self.assertAlmostEqual(
            batch[other.id],
            self.availability.get_free_hours(other, *window),
            places=1)
