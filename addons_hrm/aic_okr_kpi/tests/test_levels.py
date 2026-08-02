# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestObjectiveLevels(OkrCase):
    """Five organizational levels, each anchored to its own unit."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env['aic.hrm.team'].create({
            'name': 'Levels Fixture Squad',
            'department_id': cls.department.id,
            'lead_id': cls.manager_employee.id,
            'member_ids': [(6, 0, [cls.member_employee.id])],
        })

    def test_company_level_needs_no_anchor(self):
        objective = self._make_objective(
            level='company', department_id=False)
        self.assertEqual(objective.level, 'company')

    def test_branch_level_requires_branch(self):
        with self.assertRaises(ValidationError):
            self._make_objective(level='branch', department_id=False)
        branch = self.env['res.company'].create(
            {'name': 'North Branch'})
        objective = self._make_objective(
            level='branch', branch_id=branch.id, department_id=False)
        self.assertEqual(objective.branch_id, branch)

    def test_department_level_requires_department(self):
        with self.assertRaises(ValidationError):
            self._make_objective(level='department', department_id=False)

    def test_team_level_requires_team(self):
        with self.assertRaises(ValidationError):
            self._make_objective(level='team', department_id=False)
        objective = self._make_objective(
            level='team', team_id=self.team.id, department_id=False)
        self.assertEqual(objective.team_id, self.team)

    def test_individual_level_requires_owner(self):
        with self.assertRaises(ValidationError):
            self._make_objective(
                level='individual', department_id=False)
        objective = self._make_objective(
            level='individual', employee_id=self.member_employee.id)
        self.assertEqual(objective.employee_id, self.member_employee)

    def test_cascade_across_levels(self):
        company_bet = self._make_objective(
            name='Company bet', level='company', department_id=False)
        team_bet = self._make_objective(
            name='Team bet', level='team', team_id=self.team.id,
            department_id=False, parent_id=company_bet.id)
        personal = self._make_objective(
            name='My part', level='individual',
            employee_id=self.member_employee.id, parent_id=team_bet.id)
        self.assertEqual(personal.parent_id.parent_id, company_bet)

    def test_team_names_unique_per_company(self):
        with self.assertRaises(Exception):
            with self.env.cr.savepoint():
                self.env['aic.hrm.team'].create({
                    'name': 'Levels Fixture Squad',
                    'company_id': self.env.company.id,
                })
