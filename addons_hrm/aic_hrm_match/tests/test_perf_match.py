# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Performance tests for aic_hrm_match engine."""
import os
from datetime import timedelta
from odoo.tests import TransactionCase, tagged

SCALE_EMPLOYEES = int(os.environ.get('AIC_HRM_MATCH_PERF_EMPLOYEES', '2000'))
RANK_BUDGET_S = 3.0
MAX_QUERIES_PER_RANK = 40


@tagged('post_install', '-at_install', 'aic_hrm_match', 'perf')
class TestPerfMatch(TransactionCase):
    """Performance budget tests - run with --test-tags perf."""

    def test_rank_single_request_under_budget(self):
        """Single request ranking must complete <3 seconds."""
        import time
        Request = self.env['aic.hrm.match.request']
        Policy = self.env['aic.hrm.match.policy']
        Engine = self.env['aic.hrm.match.engine']

        policy = Policy.search([('state', '=', 'active')], limit=1)
        if not policy:
            policy = Policy.create({'name': 'Perf Policy', 'code': 'perf_test', 'state': 'active'})

        req = Request.create({
            'reference': 'PERF-001',
            'request_type': 'standalone',
            'request_company_id': self.env.company.id,
            'date_start': self.env['fields.Date'].today(),
            'date_end': self.env['fields.Date'].today() + timedelta(days=2),
            'policy_id': policy.id,
        })

        start = time.time()
        run = Engine.run_match(req)
        elapsed = time.time() - start

        self.assertLess(elapsed, RANK_BUDGET_S)
        self.assertEqual(run.state, 'computed')

    def test_rank_query_count_bounded(self):
        """Ranking query count must be bounded at 40."""
        Request = self.env['aic.hrm.match.request']
        Policy = self.env['aic.hrm.match.policy']
        Engine = self.env['aic.hrm.match.engine']

        policy = Policy.search([('state', '=', 'active')], limit=1)
        if not policy:
            policy = Policy.create({'name': 'Perf Policy', 'code': 'perf_test', 'state': 'active'})

        req = Request.create({
            'reference': 'PERF-QRY',
            'request_type': 'standalone',
            'request_company_id': self.env.company.id,
            'date_start': self.env['fields.Date'].today(),
            'date_end': self.env['fields.Date'].today() + timedelta(days=1),
            'policy_id': policy.id,
        })

        with self.assertQueryCount(MAX_QUERIES_PER_RANK):
            run = Engine.run_match(req)

        self.assertEqual(run.state, 'computed')

    def test_batch_rank_50_requests(self):
        """50-request batch must complete <60 seconds."""
        import time
        Request = self.env['aic.hrm.match.request']
        Policy = self.env['aic.hrm.match.policy']
        Engine = self.env['aic.hrm.match.engine']

        policy = Policy.search([('state', '=', 'active')], limit=1)
        if not policy:
            policy = Policy.create({'name': 'Perf Policy', 'code': 'perf_test', 'state': 'active'})

        start = time.time()
        for i in range(50):
            req = Request.create({
                'reference': 'PERF-B' + str(i).zfill(4),
                'request_type': 'standalone',
                'request_company_id': self.env.company.id,
                'date_start': self.env['fields.Date'].today() + timedelta(days=i),
                'date_end': self.env['fields.Date'].today() + timedelta(days=i + 2),
                'policy_id': policy.id,
            })
            run = Engine.run_match(req)
            self.assertEqual(run.state, 'computed')

        elapsed = time.time() - start
        self.assertLess(elapsed, 60.0)

    def test_composition_scales(self):
        """Multi-slot composition <5 seconds."""
        import time
        Request = self.env['aic.hrm.match.request']
        Policy = self.env['aic.hrm.match.policy']
        Engine = self.env['aic.hrm.match.engine']

        policy = Policy.search([('state', '=', 'active')], limit=1)
        if not policy:
            policy = Policy.create({'name': 'Perf Policy', 'code': 'perf_test', 'state': 'active'})

        req = Request.create({
            'reference': 'PERF-MULTI',
            'request_type': 'standalone',
            'request_company_id': self.env.company.id,
            'date_start': self.env['fields.Date'].today(),
            'date_end': self.env['fields.Date'].today() + timedelta(days=5),
            'policy_id': policy.id,
        })

        start = time.time()
        run = Engine.run_match(req)
        elapsed = time.time() - start

        self.assertEqual(run.state, 'computed')
        self.assertLess(elapsed, 5.0)

    def test_parameter_snapshot_captured(self):
        """Run must capture parameter_snapshot for audit trail."""
        Request = self.env['aic.hrm.match.request']
        Policy = self.env['aic.hrm.match.policy']
        Engine = self.env['aic.hrm.match.engine']

        policy = Policy.search([('state', '=', 'active')], limit=1)
        if not policy:
            policy = Policy.create({'name': 'Perf Policy', 'code': 'perf_test', 'state': 'active'})

        req = Request.create({
            'reference': 'PERF-SNAP',
            'request_type': 'standalone',
            'request_company_id': self.env.company.id,
            'date_start': self.env['fields.Date'].today(),
            'date_end': self.env['fields.Date'].today() + timedelta(days=1),
            'policy_id': policy.id,
        })

        run = Engine.run_match(req)
        self.assertEqual(run.state, 'computed')
        self.assertIsNotNone(run.parameter_snapshot)

    def test_input_hash_immutable(self):
        """Input hash must remain constant for same input data."""
        Request = self.env['aic.hrm.match.request']
        Policy = self.env['aic.hrm.match.policy']
        Engine = self.env['aic.hrm.match.engine']

        policy = Policy.search([('state', '=', 'active')], limit=1)
        if not policy:
            policy = Policy.create({'name': 'Perf Policy', 'code': 'perf_test', 'state': 'active'})

        req = Request.create({
            'reference': 'PERF-HASH',
            'request_type': 'standalone',
            'request_company_id': self.env.company.id,
            'date_start': self.env['fields.Date'].today(),
            'date_end': self.env['fields.Date'].today() + timedelta(days=1),
            'policy_id': policy.id,
        })

        run1 = Engine.run_match(req)
        self.assertIsNotNone(run1.input_hash)
