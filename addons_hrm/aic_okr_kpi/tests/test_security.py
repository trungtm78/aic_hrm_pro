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

    def test_kr_follows_objective_visibility(self):
        kr = self._make_kr(self.private_goal)
        visible = self.KeyResult.with_user(self.outsider_user).search(
            [('id', '=', kr.id)])
        self.assertFalse(visible)
        visible_owner = self.KeyResult.with_user(self.member_user).search(
            [('id', '=', kr.id)])
        self.assertIn(kr, visible_owner)
