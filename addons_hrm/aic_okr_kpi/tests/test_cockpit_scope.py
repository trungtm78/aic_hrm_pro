# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What the leadership desk reads for each cycle in its selector.

The desk used to read only the objectives whose cycle is exactly the one
selected. The customer sets objectives per quarter and assigns KPIs per
month, so of the five cycles in the selector only the quarter showed
anything: the year and each month were empty although the months carried
nineteen or twenty scorecards with real figures, and no cycle showed a
single KPI.

A cycle is read through its tree: its own objectives, or else those of the
cycles inside it (a year gathers its quarters), or else those of the nearest
cycle above it (a month works towards its quarter). Scorecards are gathered
from the cycle and every cycle inside it. The answer always says which
cycles it came from.
"""
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestCockpitScope(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The customer's tree: a year, a quarter under it, months under that.
        cls.q3 = cls.Cycle.create({
            'name': 'Q3 2026', 'code': 'SCOPE-Q3', 'cycle_type': 'quarter',
            'date_start': '2026-07-01', 'date_end': '2026-09-30',
            'parent_id': cls.year.id})
        cls.july = cls.Cycle.create({
            'name': 'July 2026', 'code': 'SCOPE-M7', 'cycle_type': 'month',
            'date_start': '2026-07-01', 'date_end': '2026-07-31',
            'parent_id': cls.q3.id})
        cls.august = cls.Cycle.create({
            'name': 'August 2026', 'code': 'SCOPE-M8', 'cycle_type': 'month',
            'date_start': '2026-08-01', 'date_end': '2026-08-31',
            'parent_id': cls.q3.id})

        cls.revenue = cls._make_objective(name='Revenue', cycle_id=cls.q3.id, weight=50.0)
        cls._make_kr(cls.revenue, baseline=0, target=100, current=70, weight=100.0)
        cls.mau = cls._make_objective(name='MAU', cycle_id=cls.q3.id, weight=50.0)
        cls._make_kr(cls.mau, baseline=10, target=15, current=0, weight=100.0,
                     progress_reported_on=False)

        # July: the member is measured at 80%, the manager has no figure yet.
        cls.july_member = cls._scorecard(cls.member_employee, cls.july, actual=80.0)
        cls.july_manager = cls._scorecard(cls.manager_employee, cls.july, actual=None)
        # August: the member is measured at 30% - off track (red is below 40%).
        cls.august_member = cls._scorecard(cls.member_employee, cls.august, actual=30.0)

    @classmethod
    def _scorecard(cls, employee, cycle, actual):
        target = cls._make_target(cycle_id=cycle.id, employee_id=employee.id,
                                  target_value=100.0)
        if actual is not None:
            cls._add_result(target, cycle.date_start, cycle.date_end, actual)
        return cls.env['aic.hrm.kpi.assignment'].create({
            'employee_id': employee.id, 'cycle_id': cycle.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': 100.0})]})

    def _read(self, cycle, user=None):
        Cycle = self.Cycle.with_user(user) if user else self.Cycle
        return Cycle.browse(cycle.id).cockpit_data()

    # ---- objectives: own, inside, above --------------------------------

    def test_a_quarter_reads_its_own_objectives(self):
        data = self._read(self.q3)
        self.assertEqual(data['okr']['source'], 'own')
        self.assertEqual([c['id'] for c in data['okr']['cycles']], [self.q3.id])
        self.assertEqual({o['id'] for o in data['okr']['objectives']},
                         {self.revenue.id, self.mau.id})
        self.assertEqual(len(data['okr']['key_results']), 2)

    def test_a_month_works_towards_the_quarter_above_it(self):
        data = self._read(self.july)
        self.assertEqual(data['okr']['source'], 'parent',
                         'a month has no objectives of its own; its quarter does')
        self.assertEqual([c['id'] for c in data['okr']['cycles']], [self.q3.id])
        self.assertEqual(len(data['okr']['objectives']), 2)

    def test_a_year_gathers_the_quarters_inside_it(self):
        data = self._read(self.year)
        self.assertEqual(data['okr']['source'], 'children')
        self.assertIn(self.q3.id, [c['id'] for c in data['okr']['cycles']])
        self.assertTrue({self.revenue.id, self.mau.id}
                        <= {o['id'] for o in data['okr']['objectives']})

    def test_own_objectives_win_over_the_ones_inside(self):
        yearly = self._make_objective(name='Strategy', cycle_id=self.year.id, weight=100.0)
        data = self._read(self.year)
        self.assertEqual(data['okr']['source'], 'own')
        self.assertEqual([o['id'] for o in data['okr']['objectives']], [yearly.id])

    def test_a_cycle_with_nothing_anywhere_says_so(self):
        data = self._read(self.other_cycle)
        self.assertEqual(data['okr']['source'], 'none')
        self.assertEqual(data['okr']['objectives'], [])
        self.assertEqual(data['kpi']['source'], 'none')
        self.assertEqual(data['kpi']['scorecard_count'], 0)

    def test_the_risk_queue_follows_the_same_cycles(self):
        data = self._read(self.july)
        codes = {risk['id'] for risk in data['okr']['risks']}
        self.assertNotIn(self.mau.kr_ids.id, codes,
                         'nothing reported is not scored, so it is not a risk')

    # ---- scorecards: the cycle and everything inside it ----------------

    def test_a_month_reads_its_own_scorecards(self):
        kpi = self._read(self.july)['kpi']
        self.assertEqual(kpi['source'], 'own')
        self.assertEqual(kpi['scorecard_count'], 2)
        self.assertEqual(kpi['measured_count'], 1,
                         'the manager has no confirmed figure yet')
        self.assertAlmostEqual(kpi['score_covered'], 0.8, places=4,
                               msg='scored on what has figures only')
        self.assertAlmostEqual(kpi['coverage'], 50.0, places=4)

    def test_a_quarter_gathers_the_months_inside_it(self):
        kpi = self._read(self.q3)['kpi']
        self.assertEqual(kpi['source'], 'children')
        self.assertEqual({c['id'] for c in kpi['cycles']}, {self.july.id, self.august.id})
        self.assertEqual(kpi['scorecard_count'], 3)
        self.assertEqual(kpi['measured_count'], 2)
        self.assertAlmostEqual(kpi['score_covered'], 0.55, places=4)
        per_cycle = {row['cycle_id']: row for row in kpi['by_cycle']}
        self.assertEqual(per_cycle[self.july.id]['count'], 2)
        self.assertAlmostEqual(per_cycle[self.august.id]['score_covered'], 0.3, places=4)

    def test_off_track_counts_only_measured_scorecards(self):
        kpi = self._read(self.q3)['kpi']
        self.assertEqual(kpi['red_count'], 1, 'August at 30% is off track')
        self.assertEqual(kpi['unmeasured_count'], 1,
                         'the manager without figures is unmeasured, not red')

    def test_departments_and_weakest_scorecards(self):
        kpi = self._read(self.q3)['kpi']
        [row] = [row for row in kpi['by_department']
                 if row['department_id'] == self.department.id]
        self.assertEqual(row['count'], 3)
        self.assertEqual(row['measured_count'], 2)
        weakest = kpi['weakest']
        self.assertEqual(weakest[0]['id'], self.august_member.id,
                         'worst measured scorecard first')
        self.assertNotIn(self.july_manager.id, [w['id'] for w in weakest],
                         'an unmeasured scorecard is not "weak"')

    # ---- access ----------------------------------------------------------

    def test_a_member_reads_only_what_the_record_rules_let_them_see(self):
        data = self._read(self.q3, user=self.member_user)
        visible = self.env['aic.hrm.kpi.assignment'].with_user(self.member_user).search_count(
            [('cycle_id', 'in', [self.july.id, self.august.id])])
        self.assertEqual(data['kpi']['scorecard_count'], visible)

    # ---- the band matches the figure shown -----------------------------

    def test_a_scorecard_is_banded_on_what_has_figures(self):
        """The desk shows the score on measured KPIs; the colour must be that
        score's band. Banded on the full score, a card at 100% on everything
        reported showed amber and one at 57% showed red - on the customer's
        own July - because every KPI still waiting for a figure counted as 0."""
        reported = self._make_target(cycle_id=self.august.id,
                                     employee_id=self.manager_employee.id,
                                     target_value=100.0)
        waiting = self._make_target(cycle_id=self.august.id,
                                    employee_id=self.manager_employee.id,
                                    target_value=100.0,
                                    kpi_id=self.Kpi.create({'name': 'Waiting',
                                                            'code': 'KPI-WAIT'}).id)
        self._add_result(reported, '2026-08-01', '2026-08-31', 60.0)
        card = self.env['aic.hrm.kpi.assignment'].create({
            'employee_id': self.manager_employee.id, 'cycle_id': self.august.id,
            'line_ids': [(0, 0, {'kpi_target_id': reported.id, 'weight': 50.0}),
                         (0, 0, {'kpi_target_id': waiting.id, 'weight': 50.0})]})
        self.assertAlmostEqual(card.score, 0.3, places=4)
        self.assertAlmostEqual(card.score_covered, 0.6, places=4)
        self.assertEqual(card.rag, 'amber', '60% on what was reported is at risk, not off track')
        kpi = self._read(self.august)['kpi']
        self.assertEqual(kpi['red_count'], 1, 'only the 30% card is off track')
