# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Weighted KPI groups on a personal scorecard.

Assignment sheets commonly split a scorecard into groups - e.g. revenue KPIs
worth 80 % and management KPIs worth 20 % - and weigh each KPI inside its
group. The scorecard must keep both levels as entered, derive each line's
share of the whole, and refuse submission unless both levels add up.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestScorecardGroups(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Assignment = cls.env['aic.hrm.kpi.assignment']
        cls.Group = cls.env['aic.hrm.kpi.group']
        cls.revenue = cls.Group.create({'name': 'Revenue KPI', 'code': 'B.I'})
        cls.management = cls.Group.create({'name': 'Management KPI', 'code': 'B.II'})
        kpis = cls.Kpi.create([
            {'name': 'Revenue %s' % i, 'code': 'KPI-GRP-%s' % i} for i in range(4)])
        cls.targets = cls.KpiTarget.create([{
            'kpi_id': kpi.id, 'cycle_id': cls.year.id,
            'employee_id': cls.member_employee.id, 'target_value': 100.0,
        } for kpi in kpis])

    def _scorecard(self, group_weights=(80.0, 20.0), in_group=((40.0, 60.0), (70.0, 30.0))):
        groups = [(self.revenue, group_weights[0]), (self.management, group_weights[1])]
        lines = []
        for index, (group, _weight) in enumerate(groups):
            for offset, share in enumerate(in_group[index]):
                lines.append((0, 0, {
                    'kpi_target_id': self.targets[index * 2 + offset].id,
                    'group_id': group.id,
                    'weight_in_group': share,
                }))
        return self.Assignment.create({
            'employee_id': self.member_employee.id,
            'cycle_id': self.year.id,
            'group_ids': [(0, 0, {'group_id': group.id, 'weight': weight})
                          for group, weight in groups],
            'line_ids': lines,
        })

    def test_line_weight_is_the_share_of_the_whole_scorecard(self):
        card = self._scorecard()
        self.assertEqual(card.line_ids.mapped('weight'), [32.0, 48.0, 14.0, 6.0])
        self.assertAlmostEqual(card.total_weight, 100.0)
        self.assertTrue(card.weight_ok)
        self.assertEqual(card.group_ids.mapped('total_in_group'), [100.0, 100.0])

    def test_changing_a_group_weight_reweighs_its_lines(self):
        card = self._scorecard()
        card.group_ids.filtered(lambda g: g.group_id == self.revenue).weight = 60.0
        card.group_ids.filtered(lambda g: g.group_id == self.management).weight = 40.0
        self.assertEqual(card.line_ids.mapped('weight'), [24.0, 36.0, 28.0, 12.0])
        self.assertTrue(card.weight_ok)

    def test_groups_not_totalling_100_block_submission(self):
        card = self._scorecard(group_weights=(80.0, 30.0))
        self.assertFalse(card.weight_ok)
        with self.assertRaisesRegex(UserError, 'groups'):
            card.action_submit()

    def test_a_group_whose_lines_miss_100_blocks_submission(self):
        card = self._scorecard(in_group=((50.0, 60.0), (70.0, 30.0)))
        self.assertFalse(card.weight_ok)
        with self.assertRaisesRegex(UserError, 'Revenue KPI'):
            card.action_submit()

    def test_groups_that_cancel_out_still_block(self):
        """50 x 120 % + 50 x 80 % is exactly 100 over the whole scorecard,
        yet neither group adds up. A total-only check would let it through."""
        card = self._scorecard(group_weights=(50.0, 50.0),
                               in_group=((60.0, 60.0), (40.0, 40.0)))
        self.assertAlmostEqual(card.total_weight, 100.0)
        self.assertFalse(card.weight_ok)

    def test_ungrouped_line_on_a_grouped_scorecard_blocks_submission(self):
        card = self._scorecard()
        extra_kpi = self.Kpi.create({'name': 'Extra', 'code': 'KPI-GRP-X'})
        extra = self.KpiTarget.create({'kpi_id': extra_kpi.id, 'cycle_id': self.year.id,
                                       'employee_id': self.member_employee.id,
                                       'target_value': 1.0})
        card.write({'line_ids': [(0, 0, {'kpi_target_id': extra.id, 'weight': 1.0})]})
        self.assertFalse(card.weight_ok)
        with self.assertRaisesRegex(UserError, 'group'):
            card.action_submit()

    def test_well_formed_grouped_scorecard_submits(self):
        card = self._scorecard()
        card.action_submit()
        self.assertEqual(card.state, 'submitted')

    def test_a_group_is_listed_once_per_scorecard(self):
        card = self._scorecard()
        with self.assertRaises(Exception), self.env.cr.savepoint():
            card.write({'group_ids': [(0, 0, {'group_id': self.revenue.id, 'weight': 1.0})]})

    def test_line_group_must_be_declared_on_the_scorecard(self):
        card = self._scorecard()
        stray = self.Group.create({'name': 'Stray'})
        with self.assertRaisesRegex(UserError, 'Stray'):
            card.line_ids[0].group_id = stray
            card.action_submit()

    def test_rollover_carries_groups_and_shares(self):
        card = self._scorecard()
        next_year = self.other_cycle
        self.env['aic.hrm.rollover.wizard'].create({
            'source_cycle_id': self.year.id, 'target_cycle_id': next_year.id,
            'copy_objectives': False,
        }).action_rollover()
        copy = self.Assignment.search([('cycle_id', '=', next_year.id),
                                       ('employee_id', '=', card.employee_id.id)])
        self.assertEqual(copy.group_ids.mapped('weight'), [80.0, 20.0])
        self.assertEqual(copy.line_ids.mapped('weight'), [32.0, 48.0, 14.0, 6.0])
        self.assertTrue(copy.weight_ok)
