# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestObjectiveWorkflow(OkrCase):

    def test_happy_path(self):
        objective = self._make_objective(employee_id=self.member_employee.id)
        self.assertEqual(objective.state, 'draft')
        objective.action_submit()
        self.assertEqual(objective.state, 'submitted')
        objective.action_approve()
        self.assertEqual(objective.state, 'approved')
        objective.action_start()
        self.assertEqual(objective.state, 'in_progress')
        objective.action_self_assess()
        self.assertEqual(objective.state, 'self_assessed')
        objective.action_manager_review()
        self.assertEqual(objective.state, 'manager_review')
        objective.action_finalize()
        self.assertEqual(objective.state, 'done')

    def test_illegal_jump_blocked(self):
        objective = self._make_objective()
        with self.assertRaises(UserError):
            objective.action_finalize()
        with self.assertRaises(UserError):
            objective.action_approve()

    def test_state_direct_write_blocked(self):
        objective = self._make_objective()
        with self.assertRaises(UserError):
            objective.write({'state': 'done'})

    def test_reset_to_draft_from_submitted(self):
        objective = self._make_objective()
        objective.action_submit()
        objective.action_reset_to_draft()
        self.assertEqual(objective.state, 'draft')

    def test_governed_fields_locked_after_approval(self):
        objective = self._make_objective(weight=20.0)
        kr = self._make_kr(objective)
        objective.action_submit()
        objective.action_approve()
        with self.assertRaises(UserError):
            objective.write({'weight': 50.0})
        with self.assertRaises(UserError):
            kr.write({'target': 500.0})
        # current value stays freely editable (check-ins write it)
        kr.write({'current': 10.0})
        self.assertAlmostEqual(kr.current, 10.0)

    def test_revision_updates_governed_field(self):
        objective = self._make_objective(weight=20.0)
        kr = self._make_kr(objective)
        objective.action_submit()
        objective.action_approve()
        revision = self.env['aic.hrm.target.revision'].create({
            'res_model': 'aic.hrm.key.result',
            'res_id': kr.id,
            'field_name': 'target',
            'new_value_float': 120.0,
            'reason': 'Scope grew after the mid-quarter review.',
        })
        revision.action_approve()
        self.assertAlmostEqual(kr.target, 120.0)

    def test_draft_fields_stay_editable(self):
        objective = self._make_objective(weight=20.0)
        objective.write({'weight': 30.0})
        self.assertAlmostEqual(objective.weight, 30.0)
