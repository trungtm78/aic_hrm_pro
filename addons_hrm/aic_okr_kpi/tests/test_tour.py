# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'aic_okr_kpi_tour')
class TestDemoTour(HttpCase):
    """Browser E2E: menu -> objectives -> cockpit. Runs under its own tag
    (needs Chrome); the same tour doubles as the customer demo script."""

    def _skip_if_backend_theme(self):
        """Third-party backend themes replace the app-menu shell, so the
        product's own tours cannot run against them. The suite ships no
        theme; skip rather than assert someone else's markup."""
        theme = self.env['ir.module.module'].search([
            ('name', 'in', ('spiffy_theme_backend', 'aic_sale_pro_theme')),
            ('state', '=', 'installed'),
        ], limit=1)
        if theme:
            self.skipTest(
                f'a backend theme ({theme.name}) replaces the app menu')

    def test_demo_tour(self):
        self._skip_if_backend_theme()
        cycle = self.env['aic.hrm.cycle'].create({
            'name': 'Tour FY', 'code': 'TOUR-FY', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })
        cycle.action_open()
        objective = self.env['aic.hrm.objective'].create({
            'name': 'Tour objective', 'cycle_id': cycle.id,
            'level': 'company', 'weight': 100,
        })
        self.env['aic.hrm.key.result'].create({
            'name': 'Tour KR', 'objective_id': objective.id,
            'baseline': 0, 'target': 100, 'current': 40,
        })
        self.start_tour('/odoo', 'aic_okr_demo', login='admin')

    def test_screens_tour(self):
        """Every core menu opens and renders in a real browser."""
        self._skip_if_backend_theme()
        self.start_tour('/odoo', 'aic_okr_screens', login='admin')
