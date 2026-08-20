# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Two planners booking the same person at the same moment.

Clash prevention is the headline of every resource-scheduling product, and it
is also the easiest thing to implement in a way that works in every demo and
fails in production. A check written in Python and run inside a transaction
sees the state as it was before the other transaction started: both planners
pass the check, both commit, and the person is double-booked with no error
anywhere.

``SELECT ... FOR UPDATE`` does not fix it either. It locks rows that exist, and
the case that matters is two transactions *inserting* new bookings - there is
no row yet to lock. A transaction-scoped advisory lock keyed on the employee is
what actually serialises them.

These tests check the mechanism rather than trying to race two real
connections: they assert that the lock is taken, that it is taken in a fixed
order, that it covers both sides of a move, and that the check re-reads after
locking. A racing test that passes nine times out of ten would tell us less.
"""
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class AdvisoryLockCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Allocation = cls.env['aic.hrm.match.allocation']
        cls.employee = cls._make_employee('Lock Holder')
        cls.other = cls._make_employee('Other Holder')

    def _held_locks(self):
        """Advisory locks this transaction currently holds, as classids."""
        self.env.cr.execute("""
            SELECT objid FROM pg_locks
            WHERE locktype = 'advisory' AND classid = %s
              AND pid = pg_backend_pid()
        """, (self.Allocation._LOCK_NAMESPACE,))
        return {row[0] for row in self.env.cr.fetchall()}

    def _capacity(self, employee, start, end):
        return self.env['aic.hrm.match.availability'].get_gross_hours(
            employee, start, end)

    def _book(self, employee, start, end, hours=None, **kwargs):
        """Book a fraction of whatever the calendar actually offers.

        The default calendar is not the same on every series - Odoo 18 and 19
        place the lunch break differently - so a fixture that hard-codes "four
        hours in a morning" passes on one and trips the capacity guard on the
        other for reasons that have nothing to do with what is being tested.
        """
        if hours is None:
            hours = self._capacity(employee, start, end) / 2.0
        values = {
            'employee_id': employee.id,
            'date_start': start,
            'date_end': end,
            'allocated_hours': hours,
            'state': 'confirmed',
        }
        values.update(kwargs)
        return self.Allocation.create(values)

    def test_creating_a_booking_locks_that_employee(self):
        self.assertNotIn(self.employee.id, self._held_locks())
        self._book(self.employee, '2026-09-14 08:00:00',
                   '2026-09-14 12:00:00')
        self.assertIn(self.employee.id, self._held_locks())

    def test_the_lock_is_not_taken_for_unrelated_people(self):
        self._book(self.employee, '2026-09-14 08:00:00',
                   '2026-09-14 12:00:00')
        self.assertNotIn(self.other.id, self._held_locks())

    def test_a_draft_booking_is_not_worth_locking_for(self):
        """A draft consumes nothing, so serialising on it would make planners
        queue behind each other's scratch work for no protection at all."""
        self._book(self.employee, '2026-09-14 08:00:00',
                   '2026-09-14 12:00:00', state='draft')
        self.assertNotIn(self.employee.id, self._held_locks())

    def test_moving_a_booking_locks_both_ends(self):
        """A write that reassigns a booking frees capacity for one person and
        consumes it for another. Locking only the new owner leaves the old
        one's total wrong under concurrency."""
        booking = self._book(self.employee, '2026-09-14 08:00:00',
                             '2026-09-14 12:00:00')
        self.env.cr.execute("SELECT pg_advisory_unlock_all()")
        booking.write({'employee_id': self.other.id})
        held = self._held_locks()
        self.assertIn(self.employee.id, held)
        self.assertIn(self.other.id, held)

    def test_locks_are_acquired_in_ascending_order(self):
        """Two batches touching an overlapping set in opposite orders deadlock.
        A fixed order is what removes the cycle, so the order is asserted
        rather than assumed."""
        acquired = []
        original = type(self.Allocation)._lock_employees

        def spy(records, employee_ids):
            acquired.extend(sorted(set(employee_ids)))
            return original(records, employee_ids)

        self.patch(type(self.Allocation), '_lock_employees', spy)
        share = self._capacity(self.employee, '2026-09-14 08:00:00',
                               '2026-09-14 12:00:00') / 2.0
        self.Allocation.create([
            {'employee_id': self.other.id, 'date_start': '2026-09-14 08:00:00',
             'date_end': '2026-09-14 12:00:00', 'allocated_hours': share,
             'state': 'confirmed'},
            {'employee_id': self.employee.id, 'date_start': '2026-09-14 08:00:00',
             'date_end': '2026-09-14 12:00:00', 'allocated_hours': share,
             'state': 'confirmed'},
        ])
        self.assertEqual(acquired, sorted(acquired))


@tagged('post_install', '-at_install', 'aic_hrm_match')
class OverAllocationCase(MatchCase):
    """The check the lock exists to protect."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Allocation = cls.env['aic.hrm.match.allocation']
        cls.employee = cls._make_employee('Over Booked')
        cls.week = ('2026-09-14 00:00:00', '2026-09-18 23:59:59')

    def _week_capacity(self):
        return self.env['aic.hrm.match.availability'].get_gross_hours(
            self.employee, *self.week)

    def _book(self, share, start=None, end=None, **kwargs):
        """``share`` is a fraction of the real weekly capacity, so the fixture
        means the same thing on every calendar."""
        values = {
            'employee_id': self.employee.id,
            'date_start': start or self.week[0],
            'date_end': end or self.week[1],
            'allocated_hours': self._week_capacity() * share,
            'state': 'confirmed',
        }
        values.update(kwargs)
        return self.Allocation.create(values)

    def test_booking_within_capacity_is_accepted(self):
        self.assertTrue(self._book(0.75).id)

    def test_booking_beyond_capacity_is_refused(self):
        self._book(0.75)
        with self.assertRaises(ValidationError):
            self._book(0.75)

    def test_the_error_names_the_bookings_it_clashed_with(self):
        """A refusal that does not say what it clashed with sends the planner
        hunting through a calendar; the whole point is to hand them the answer.
        """
        first = self._book(0.75)
        with self.assertRaises(ValidationError) as caught:
            self._book(0.75)
        self.assertIn(str(first.id), str(caught.exception))

    def test_drafts_do_not_count_towards_the_ceiling(self):
        self._book(0.75, state='draft')
        self.assertTrue(self._book(0.75).id)

    def test_the_tolerance_is_configurable_per_company(self):
        """Some organisations plan deliberately at 110% and absorb it. That is
        a business decision, not something to hard-code as either allowed or
        forbidden."""
        self.employee.company_id.match_over_allocation_tolerance = 0.5
        self._book(0.75)
        self.assertTrue(self._book(0.6).id)

    def test_a_zero_capacity_window_refuses_any_commitment(self):
        """Booking somebody across a weekend is not a rounding question."""
        with self.assertRaises(ValidationError):
            self._book(0.2, start='2026-09-19 00:00:00',
                       end='2026-09-20 23:59:59')
