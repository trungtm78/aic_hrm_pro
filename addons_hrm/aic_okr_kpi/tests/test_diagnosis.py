# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestProgressDiagnosis(OkrCase):
    """The improvement engine: expected pace vs reality, plus concrete
    recommendations derived from REAL signals (blockers, confidence,
    check-in cadence) - never invented ones."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        today = fields.Date.context_today(cls.env.user)
        # A cycle exactly at its halfway point (100 days in, 200 total).
        cls.live_cycle = cls.Cycle.create({
            'name': 'Diag FY', 'code': 'DIAG-FY', 'cycle_type': 'custom',
            'date_start': today - timedelta(days=100),
            'date_end': today + timedelta(days=100),
        })
        cls.objective = cls.Objective.create({
            'name': 'Diagnosed objective', 'cycle_id': cls.live_cycle.id,
            'weight': 100, 'employee_id': cls.member_employee.id})

    def _make_live_kr(self, current, **kw):
        vals = {
            'name': 'Diag KR', 'objective_id': self.objective.id,
            'baseline': 0.0, 'target': 100.0, 'current': current,
            'employee_id': self.member_employee.id,
        }
        vals.update(kw)
        return self.KeyResult.create(vals)

    def test_expected_progress_tracks_cycle_elapsed(self):
        kr = self._make_live_kr(current=50.0)
        self.assertAlmostEqual(kr.expected_progress, 0.5, places=2)
        self.assertAlmostEqual(kr.pace_gap, 0.0, places=2)
        self.assertEqual(kr.pace_status, 'on_pace')

    def test_behind_pace_detected(self):
        kr = self._make_live_kr(current=20.0)
        self.assertAlmostEqual(kr.pace_gap, -0.3, places=2)
        self.assertEqual(kr.pace_status, 'behind')

    def test_ahead_of_pace_detected(self):
        kr = self._make_live_kr(current=80.0)
        self.assertEqual(kr.pace_status, 'ahead')

    def test_recommendation_from_open_blocker(self):
        kr = self._make_live_kr(current=20.0)
        self.env['aic.hrm.checkin'].create({
            'kr_id': kr.id, 'value_current': 20.0, 'confidence': 4,
            'blocker': 'Partner API keys still missing'})
        diagnosis = kr._diagnose()
        self.assertTrue(any('Partner API keys' in line
                            for line in diagnosis),
                        'the REAL blocker text appears in the diagnosis')

    def test_recommendation_from_falling_confidence(self):
        kr = self._make_live_kr(current=30.0)
        for confidence in (8, 6, 4):
            self.env['aic.hrm.checkin'].create({
                'kr_id': kr.id, 'value_current': 30.0,
                'confidence': confidence})
        diagnosis = ' '.join(kr._diagnose())
        self.assertIn('confidence', diagnosis.lower())

    def test_recommendation_missing_cadence(self):
        kr = self._make_live_kr(current=10.0)
        diagnosis = ' '.join(kr._diagnose())
        self.assertIn('check-in', diagnosis.lower())

    def test_required_run_rate_math(self):
        kr = self._make_live_kr(current=20.0)
        # 80 remaining over the last half: run-rate must be 1.6x the
        # average pace so far (20 done in the first half).
        self.assertGreater(kr.required_run_rate_factor, 1.5)

    def test_recommendations_field_renders(self):
        kr = self._make_live_kr(current=20.0)
        self.assertTrue(kr.recommendations)
        self.assertIn('behind', kr.pace_status)
