# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class TestDecisionWorkflow(MatchCase):
    """Decision log model tests."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.match_run = cls._run_match()
    
    def test_decision_model_creates(self):
        """Decision model instantiation works."""
        # The one the ranking recommended, not whichever row came back
        # first: anybody else is an override and needs a reason, which
        # is a different test.
        candidate = self.match_run.candidate_ids.filtered(
            lambda c: c.rank == 1)[:1]
        employee = candidate.employee_id or self.employees[0]
        decision = self.env['aic.hrm.match.decision'].create({
            'request_id': self.match_run.request_id.id,
            'slot_id': self.match_run.request_id.slot_ids[0].id,
            'run_id': self.match_run.id,
            'candidate_id': candidate.id,
            'employee_id': employee.id,
            'decision_type': 'ranked',
            'state': 'draft',
        })
        self.assertIsNotNone(decision.id)
    
    def test_decision_unlink_forbidden(self):
        """Decisions can never be deleted."""
        # The one the ranking recommended, not whichever row came back
        # first: anybody else is an override and needs a reason, which
        # is a different test.
        candidate = self.match_run.candidate_ids.filtered(
            lambda c: c.rank == 1)[:1]
        employee = candidate.employee_id or self.employees[0]
        decision = self.env['aic.hrm.match.decision'].create({
            'request_id': self.match_run.request_id.id,
            'slot_id': self.match_run.request_id.slot_ids[0].id,
            'run_id': self.match_run.id,
            'candidate_id': candidate.id,
            'employee_id': employee.id,
            'decision_type': 'ranked',
            'state': 'draft',
        })
        with self.assertRaises(UserError):
            decision.unlink()


@tagged('post_install', '-at_install', 'aic_hrm_match')
class TestWaiver(MatchCase):
    """Waiver model tests."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.match_run = cls._run_match()
        cls.criterion = cls.env['aic.hrm.match.criterion'].search([('code', '=', 'availability')], limit=1)
    
    def test_waiver_model_creates(self):
        """Waiver model instantiation works."""
        waiver = self.env['aic.hrm.match.waiver'].create({
            'request_id': self.match_run.request_id.id,
            'slot_id': self.match_run.request_id.slot_ids[0].id,
            'employee_id': self.employees[0].id,
            'criterion_id': self.criterion.id,
            'reason': 'Team knowledge needed',
        })
        self.assertIsNotNone(waiver.id)
    
    def test_waiver_unlink_forbidden(self):
        """Waivers cannot be deleted."""
        waiver = self.env['aic.hrm.match.waiver'].create({
            'request_id': self.match_run.request_id.id,
            'slot_id': self.match_run.request_id.slot_ids[0].id,
            'employee_id': self.employees[0].id,
            'criterion_id': self.criterion.id,
            'reason': 'Team knowledge needed',
        })
        with self.assertRaises(AccessError):
            waiver.unlink()


@tagged('post_install', '-at_install', 'aic_hrm_match')
class TestErasureLog(MatchCase):
    """Erasure log model tests."""
    
    def test_erasure_log_creates(self):
        """Erasure log instantiation works."""
        log = self.env['aic.hrm.match.erasure.log'].create({
            'subject_key': 'ANON-001-ABCD',
            'reason': 'gdpr_article17',
            'reason_detail': 'Employee request',
        })
        self.assertIsNotNone(log.id)
    
    def test_erasure_log_unlink_forbidden(self):
        """Erasure logs cannot be deleted."""
        log = self.env['aic.hrm.match.erasure.log'].create({
            'subject_key': 'ANON-003-LMNO',
            'reason': 'data_correction',
            'reason_detail': 'Data correction request',
        })
        with self.assertRaises(AccessError):
            log.unlink()
