# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestStrategyLayer(OkrCase):
    """BSC perspectives and key success factors wire strategy to goals."""

    def test_bsc_perspectives_seeded(self):
        perspectives = self.env['aic.hrm.perspective'].search(
            [('company_id', '=', False)])
        self.assertGreaterEqual(len(perspectives), 4,
                                'the four BSC perspectives ship built in')
        codes = set(perspectives.mapped('code'))
        self.assertTrue({'FIN', 'CUST', 'PROC', 'LEARN'} <= codes)

    def test_ksf_catalog_seeded_per_perspective(self):
        factors = self.env['aic.hrm.ksf'].search(
            [('company_id', '=', False)])
        self.assertGreaterEqual(len(factors), 12)
        perspectives = self.env['aic.hrm.perspective'].search(
            [('code', 'in', ['FIN', 'CUST', 'PROC', 'LEARN'])])
        for perspective in perspectives:
            self.assertTrue(
                factors.filtered(
                    lambda f: f.perspective_id == perspective),
                f'{perspective.name}: every perspective has at least one '
                'built-in success factor')

    def test_objective_and_kpi_link_to_strategy(self):
        financial = self.env['aic.hrm.perspective'].search(
            [('code', '=', 'FIN')], limit=1)
        growth = self.env['aic.hrm.ksf'].search(
            [('code', '=', 'KSF-FIN-01')], limit=1)
        objective = self._make_objective(
            perspective_id=financial.id, ksf_id=growth.id)
        kpi = self.env['aic.hrm.kpi'].create({
            'name': 'Strategy-linked revenue', 'code': 'STRAT-REV',
            'perspective_id': financial.id, 'ksf_id': growth.id,
            'default_target': 100.0,
        })
        target = self.env['aic.hrm.kpi.target'].create({
            'kpi_id': kpi.id, 'cycle_id': self.year.id,
            'employee_id': self.member_employee.id,
            'target_value': 100.0,
        })
        self.assertEqual(target.perspective_id, financial,
                         'targets inherit the KPI perspective for '
                         'grouping and BSC reads')
        self.assertIn(objective, growth.objective_ids)
        self.assertIn(kpi, growth.kpi_ids)

    def test_balance_read_by_perspective(self):
        financial = self.env['aic.hrm.perspective'].search(
            [('code', '=', 'FIN')], limit=1)
        learning = self.env['aic.hrm.perspective'].search(
            [('code', '=', 'LEARN')], limit=1)
        self._make_objective(name='Fin bet', perspective_id=financial.id)
        self._make_objective(name='People bet', perspective_id=learning.id)
        grouped = self.env['aic.hrm.objective']._read_group(
            [('cycle_id', '=', self.year.id)],
            groupby=['perspective_id'], aggregates=['__count'])
        counts = {perspective.id if perspective else False: count
                  for perspective, count in grouped}
        self.assertEqual(counts.get(financial.id), 1)
        self.assertEqual(counts.get(learning.id), 1)
