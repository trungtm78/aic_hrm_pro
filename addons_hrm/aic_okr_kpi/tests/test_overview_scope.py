# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Which measurements the executive overview reads for the cycle on screen.

The overview read only the rows whose cycle is exactly the one selected.
The customer sets objectives per quarter and assigns KPIs per month, so
picking the quarter showed one measurement out of thirty-nine: a single
month bar, "100% achieved", "nothing is behind plan". A screen made for a
director to judge a quarter by was hiding thirty-eight measurements and
reporting the remaining one as the whole truth.

A measurement belongs to the period it was taken in, so the periods inside
a cycle belong to it and add up: a quarter is its own rows plus its months,
a year is everything under it. Nothing is ever borrowed from above - a
quarterly measurement is not a September measurement - so a period nobody
has measured reads empty rather than borrowing a figure and dating it to
the wrong month. That is where this screen parts company with the
leadership desk, which does borrow upwards: the desk reads a commitment,
this one reads a period.
"""
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestOverviewScope(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Report = cls.env['aic.hrm.progress.report']
        # The customer's tree: a year, a quarter, months under the quarter.
        cls.q3 = cls.Cycle.create({
            'name': 'Q3 2026', 'code': 'OVW-Q3', 'cycle_type': 'quarter',
            'date_start': '2026-07-01', 'date_end': '2026-09-30',
            'parent_id': cls.year.id})
        cls.july = cls.Cycle.create({
            'name': 'July 2026', 'code': 'OVW-M7', 'cycle_type': 'month',
            'date_start': '2026-07-01', 'date_end': '2026-07-31',
            'parent_id': cls.q3.id})
        cls.august = cls.Cycle.create({
            'name': 'August 2026', 'code': 'OVW-M8', 'cycle_type': 'month',
            'date_start': '2026-08-01', 'date_end': '2026-08-31',
            'parent_id': cls.q3.id})
        cls.september = cls.Cycle.create({
            'name': 'September 2026', 'code': 'OVW-M9', 'cycle_type': 'month',
            'date_start': '2026-09-01', 'date_end': '2026-09-30',
            'parent_id': cls.q3.id})

    @classmethod
    def _measure(cls, cycle, actual, day):
        """One confirmed monthly figure, which is one row on the report."""
        target = cls._make_target(cycle_id=cycle.id,
                                  employee_id=cls.member_employee.id,
                                  target_value=100.0)
        cls._add_result(target, day, day, actual)
        return target

    def scope(self, cycle):
        self.env.flush_all()
        return self.Report.overview_scope(cycle.id)

    def rows(self, scope):
        return self.Report.search_count([('cycle_id', 'in', scope['cycle_ids'])])

    def test_a_quarter_reads_its_months_as_well_as_its_own_rows(self):
        self._measure(self.july, 80.0, '2026-07-31')
        self._measure(self.august, 30.0, '2026-08-31')
        scope = self.scope(self.q3)
        self.assertEqual(set(scope['cycle_ids']), {self.july.id, self.august.id},
                         'the months the quarter was measured in')
        self.assertEqual(scope['source'], 'children')
        self.assertEqual(self.rows(scope), 2)

    def test_a_quarter_measured_in_its_own_right_keeps_that_row(self):
        """A key result sits on the quarter, so a check-in on it is a
        measurement of the quarter. It belongs with the months, not instead
        of them - the customer's live quarter has exactly one such row
        against thirty-eight monthly ones, and reading only it reported the
        quarter as finished."""
        self._measure(self.july, 80.0, '2026-07-31')
        objective = self._make_objective(cycle_id=self.q3.id, weight=100.0)
        kr = self._make_kr(objective, baseline=0, target=100, current=0,
                           weight=100.0)
        self.env['aic.hrm.checkin'].create({'kr_id': kr.id, 'value_current': 50.0})
        scope = self.scope(self.q3)
        self.assertIn(self.q3.id, scope['cycle_ids'])
        self.assertIn(self.july.id, scope['cycle_ids'])
        self.assertEqual(self.rows(scope), 2)

    def test_a_month_reads_only_itself(self):
        """What happened in July is July's rows. A quarterly measurement is
        not a July measurement, and counting it in every month would state
        the same figure three times."""
        self._measure(self.july, 80.0, '2026-07-31')
        self._measure(self.august, 30.0, '2026-08-31')
        scope = self.scope(self.july)
        self.assertEqual(scope['cycle_ids'], [self.july.id])
        self.assertEqual(scope['source'], 'own')
        self.assertEqual(self.rows(scope), 1)

    def test_a_year_gathers_everything_under_it(self):
        self._measure(self.july, 80.0, '2026-07-31')
        self._measure(self.august, 30.0, '2026-08-31')
        scope = self.scope(self.year)
        self.assertEqual(set(scope['cycle_ids']), {self.july.id, self.august.id})
        self.assertEqual(scope['source'], 'children')

    def test_a_period_nobody_has_measured_yet_reads_empty(self):
        """September has no figures, so September shows none. Lifting the
        quarter's rows into it would date a July measurement to September
        and tell a director the month is running at 80%."""
        self._measure(self.july, 80.0, '2026-07-31')
        scope = self.scope(self.september)
        self.assertEqual(scope['source'], 'none')
        self.assertEqual(scope['cycle_ids'], [])

    def test_an_empty_tree_reads_nothing_rather_than_guessing(self):
        alone = self.Cycle.create({
            'name': 'Untouched 2027', 'code': 'OVW-EMPTY', 'cycle_type': 'year',
            'date_start': '2027-01-01', 'date_end': '2027-12-31'})
        scope = self.scope(alone)
        self.assertEqual(scope['source'], 'none')
        self.assertEqual(scope['cycle_ids'], [])

    def test_the_scope_names_the_cycles_it_read(self):
        """The overview states where its figures came from, the way the
        leadership desk does: a director reading '39 measurements' has to be
        able to see which periods that is."""
        self._measure(self.july, 80.0, '2026-07-31')
        self._measure(self.august, 30.0, '2026-08-31')
        scope = self.scope(self.q3)
        names = [cycle['name'] for cycle in scope['cycles']]
        self.assertEqual(names, ['July 2026', 'August 2026'],
                         'oldest first, the order a period chart reads in')

    def test_the_cycles_come_back_in_calendar_order(self):
        self._measure(self.august, 30.0, '2026-08-31')
        self._measure(self.july, 80.0, '2026-07-31')
        scope = self.scope(self.q3)
        self.assertEqual(scope['cycle_ids'], [self.july.id, self.august.id])


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestAlignmentScope(KpiCase):
    """Which objectives the alignment tree draws for the cycle on screen.

    Same fault as the overview, other half of the data: the tree read only
    the objectives whose cycle is exactly the one selected. The customer
    sets objectives on the quarter, so four of the five cycles in the
    selector - the year and all three months - drew "this cycle has no
    objectives" on a system holding four of them.

    Objectives are a commitment rather than a measurement, so here the tree
    does look upwards: a month works towards its quarter's objectives, which
    is the same rule the leadership desk beside it already applies. The two
    screens must not disagree about what a month is about.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Objective = cls.env['aic.hrm.objective']
        cls.q3 = cls.Cycle.create({
            'name': 'Q3 2026', 'code': 'ALN-Q3', 'cycle_type': 'quarter',
            'date_start': '2026-07-01', 'date_end': '2026-09-30',
            'parent_id': cls.year.id})
        cls.july = cls.Cycle.create({
            'name': 'July 2026', 'code': 'ALN-M7', 'cycle_type': 'month',
            'date_start': '2026-07-01', 'date_end': '2026-07-31',
            'parent_id': cls.q3.id})
        cls.revenue = cls._make_objective(name='Revenue', cycle_id=cls.q3.id,
                                          weight=100.0)

    def scope(self, cycle):
        self.env.flush_all()
        return self.Objective.alignment_scope(cycle.id)

    def test_a_quarter_draws_its_own_objectives(self):
        scope = self.scope(self.q3)
        self.assertEqual(scope['source'], 'own')
        self.assertEqual(scope['cycle_ids'], [self.q3.id])

    def test_a_month_draws_the_objectives_of_its_quarter(self):
        """The month is not empty; it is working towards something."""
        scope = self.scope(self.july)
        self.assertEqual(scope['source'], 'parent')
        self.assertEqual(scope['cycle_ids'], [self.q3.id])

    def test_a_year_gathers_the_quarters_inside_it(self):
        scope = self.scope(self.year)
        self.assertEqual(scope['source'], 'children')
        self.assertIn(self.q3.id, scope['cycle_ids'])

    def test_a_tree_with_no_objectives_anywhere_says_so(self):
        alone = self.Cycle.create({
            'name': 'Untouched 2027', 'code': 'ALN-EMPTY', 'cycle_type': 'year',
            'date_start': '2027-01-01', 'date_end': '2027-12-31'})
        scope = self.scope(alone)
        self.assertEqual(scope['source'], 'none')
        self.assertEqual(scope['cycle_ids'], [])

    def test_the_tree_and_the_leadership_desk_agree_about_a_month(self):
        """Two screens side by side disagreeing about which objectives a
        month is about is worse than either being wrong."""
        desk = self.Cycle.browse(self.july.id).cockpit_data()
        scope = self.scope(self.july)
        self.assertEqual([c['id'] for c in desk['okr']['cycles']],
                         scope['cycle_ids'])
        self.assertEqual(desk['okr']['source'], scope['source'])
