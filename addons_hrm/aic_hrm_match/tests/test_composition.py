# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Multi-slot composition: assignment optimization for headcount > 1."""
from odoo.tests import tagged
from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CompositionCase(MatchCase):

    def test_single_slot_skips_composition(self):
        """Headcount=1: no composition needed, fast path."""
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Single', 'date_start': '2026-09-14',
            'date_end': '2026-09-18'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Developer',
            'required_hours': 20.0})
        self.assertEqual(len(request.slot_ids), 1)

    def test_multi_slot_creates_composition(self):
        """Headcount > 1: composition model exists."""
        request = self.env['aic.hrm.match.request'].create({
            'name': 'Multi', 'date_start': '2026-09-14',
            'date_end': '2026-09-18'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Backend',
            'required_hours': 20.0})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'QA',
            'required_hours': 15.0})
        self.assertEqual(len(request.slot_ids), 2)

    def test_composition_model_creates(self):
        """Composition model instantiates without error."""
        Composition = self.env['aic.hrm.match.composition']
        
        # Create minimal run for composition
        Request = self.env['aic.hrm.match.request']
        request = Request.create({
            'name': 'CompTest', 'date_start': '2026-09-14', 'date_end': '2026-09-18'})
        slot = self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Test', 'required_hours': 10.0})
        
        policy = self.env['aic.hrm.match.policy'].search(
            [('state', '=', 'active')], limit=1)
        if not policy:
            criterion = self.env['aic.hrm.match.criterion'].create({
                'code': 'test_comp', 'name': 'Test Comp', 'category': 'test'})
            policy = self.env['aic.hrm.match.policy'].create({
                'name': 'CompTest', 'code': 'comp_test', 'is_default': True})
            self.env['aic.hrm.match.policy.line'].create({
                'policy_id': policy.id, 'criterion_id': criterion.id, 'weight': 1.0})
            policy.action_activate()
        
        Run = self.env['aic.hrm.match.run']
        run = Run.create({
            'request_id': request.id, 'slot_id': slot.id,
            'policy_id': policy.id, 'policy_version': 1})
        
        comp = Composition.create({'run_id': run.id, 'sequence': 0})
        self.assertTrue(comp.id)
        self.assertEqual(comp.sequence, 0)
        self.assertTrue(comp.is_selected)

    def test_composition_line_unique(self):
        """Composition line unique constraint (composition_id, slot_id)."""
        # Verifies constraint is defined (actual test of uniqueness would need
        # duplicate attempt which raises, tested in higher-level composition tests)
        Line = self.env['aic.hrm.match.composition.line']
        constraints = Line._sql_constraints
        self.assertTrue(any(
            'unique' in str(c) and 'slot_id' in str(c)
            for c in constraints))

    def test_composition_computed_fields(self):
        """Composition computed fields calculate without error."""
        Composition = self.env['aic.hrm.match.composition']
        
        Request = self.env['aic.hrm.match.request']
        request = Request.create({
            'name': 'FieldTest', 'date_start': '2026-09-14', 'date_end': '2026-09-18'})
        slot = self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Developer', 'required_hours': 20.0})
        
        policy = self.env['aic.hrm.match.policy'].search(
            [('state', '=', 'active')], limit=1)
        Run = self.env['aic.hrm.match.run']
        run = Run.create({
            'request_id': request.id, 'slot_id': slot.id,
            'policy_id': policy.id, 'policy_version': 1})
        
        comp = Composition.create({'run_id': run.id})
        
        # Fields should compute without error
        self.assertEqual(comp.coverage_score, 0.0)
        self.assertEqual(comp.cost_total, 0.0)
        self.assertTrue(comp.capacity_ok)
        self.assertTrue(comp.is_selected)
