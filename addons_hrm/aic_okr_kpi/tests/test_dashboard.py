# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestDashboardWiring(TransactionCase):
    """Server-side wiring of the OWL dashboards: actions, menus, assets."""

    def test_client_actions_registered(self):
        cockpit = self.env.ref('aic_okr_kpi.action_aic_hrm_cockpit')
        self.assertEqual(cockpit.tag, 'aic_hrm_cockpit')
        tree = self.env.ref('aic_okr_kpi.action_aic_hrm_alignment_tree')
        self.assertEqual(tree.tag, 'aic_hrm_alignment_tree')

    def test_menus_wired(self):
        cockpit_menu = self.env.ref('aic_okr_kpi.menu_aic_hrm_cockpit')
        self.assertEqual(cockpit_menu.action.tag, 'aic_hrm_cockpit')
        tree_menu = self.env.ref('aic_okr_kpi.menu_aic_hrm_alignment_tree')
        self.assertEqual(tree_menu.action.tag, 'aic_hrm_alignment_tree')

    def test_assets_declared(self):
        manifest_assets = self.env['ir.module.module']._get(
            'aic_okr_kpi')
        self.assertTrue(manifest_assets)
        from odoo.modules.module import get_manifest
        assets = get_manifest('aic_okr_kpi').get('assets', {})
        backend = assets.get('web.assets_backend', [])
        self.assertTrue(
            any('cockpit.js' in path for path in backend),
            'cockpit component must ship in the backend bundle')
        self.assertTrue(
            any('aic_hrm_tokens.scss' in path for path in backend),
            'design tokens must ship in the backend bundle')
