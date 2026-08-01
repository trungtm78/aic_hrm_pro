# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestOkrSecurity(OkrCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private_goal = cls._make_objective(
            name='Private member goal', level='individual',
            employee_id=cls.member_employee.id, visibility='private')
        cls.public_goal = cls._make_objective(
            name='Public department goal', visibility='public')

    def test_owner_sees_own_private_goal(self):
        goals = self.Objective.with_user(self.member_user).search(
            [('id', 'in', (self.private_goal | self.public_goal).ids)])
        self.assertIn(self.private_goal, goals)
        self.assertIn(self.public_goal, goals)

    def test_outsider_sees_public_only(self):
        goals = self.Objective.with_user(self.outsider_user).search(
            [('id', 'in', (self.private_goal | self.public_goal).ids)])
        self.assertNotIn(self.private_goal, goals)
        self.assertIn(self.public_goal, goals)

    def test_manager_sees_subordinate_private_goal(self):
        goals = self.Objective.with_user(self.manager_user).search(
            [('id', 'in', self.private_goal.ids)])
        self.assertIn(self.private_goal, goals)

    def test_owner_writes_own_goal(self):
        self.private_goal.with_user(self.member_user).write(
            {'note': 'my own update'})
        self.assertEqual(self.private_goal.note, 'my own update')

    def test_non_owner_cannot_write(self):
        with self.assertRaises(AccessError):
            self.public_goal.with_user(self.outsider_user).write(
                {'note': 'drive-by edit'})

    def test_unowned_private_hidden_from_users(self):
        hidden = self._make_objective(
            name='Unowned private plan', visibility='private')
        visible = self.Objective.with_user(self.outsider_user).search(
            [('id', '=', hidden.id)])
        self.assertFalse(visible, "unowned private goals are manager-only")
        visible_manager = self.Objective.with_user(self.manager_user).search(
            [('id', '=', hidden.id)])
        self.assertIn(hidden, visible_manager)

    def test_user_cannot_assign_goal_to_someone_else(self):
        with self.assertRaises(AccessError):
            self.Objective.with_user(self.outsider_user).create({
                'name': 'Planted goal',
                'cycle_id': self.year.id,
                'level': 'individual',
                'employee_id': self.member_employee.id,
            })

    def test_user_cannot_add_kr_to_foreign_public_goal(self):
        with self.assertRaises(AccessError):
            self.KeyResult.with_user(self.outsider_user).create({
                'name': 'Score tampering',
                'objective_id': self.public_goal.id,
                'baseline': 0.0,
                'target': 1.0,
            })

    def test_non_manager_cannot_approve(self):
        goal = self._make_objective(
            name='Member goal', level='individual',
            employee_id=self.member_employee.id)
        goal.with_user(self.member_user).action_submit()
        with self.assertRaises(Exception):
            goal.with_user(self.member_user).action_approve()
        goal.with_user(self.manager_user).action_approve()
        self.assertEqual(goal.state, 'approved')

    def test_state_rpc_bypass_blocked_for_member(self):
        goal = self._make_objective(
            name='Bypass attempt', level='individual',
            employee_id=self.member_employee.id)
        goal.with_user(self.member_user).action_submit()
        with self.assertRaises(Exception):
            goal.with_user(self.member_user).with_context(
                hrm_okr_transition=True).write({'state': 'approved'})

    def test_milestone_follows_kr_visibility(self):
        kr = self._make_kr(self.private_goal, metric_type='milestone',
                           milestone_ids=[(0, 0, {'name': 'Step 1'})])
        milestone = kr.milestone_ids
        visible = self.env['aic.hrm.kr.milestone'].with_user(
            self.outsider_user).search([('id', '=', milestone.id)])
        self.assertFalse(visible)
        with self.assertRaises(AccessError):
            milestone.with_user(self.outsider_user).write({'is_done': True})

    def test_kr_follows_objective_visibility(self):
        kr = self._make_kr(self.private_goal)
        visible = self.KeyResult.with_user(self.outsider_user).search(
            [('id', '=', kr.id)])
        self.assertFalse(visible)
        visible_owner = self.KeyResult.with_user(self.member_user).search(
            [('id', '=', kr.id)])
        self.assertIn(kr, visible_owner)
