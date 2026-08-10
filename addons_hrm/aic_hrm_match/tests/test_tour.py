# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The screens, driven the way a person drives them.

Everything else in this suite talks to models. That catches wrong answers and
misses broken screens entirely: a view whose button names a method that does not
exist, a menu pointing at a deleted action, an asset bundle that stopped
loading. All of those pass every model test and greet the buyer with a blank
page.

Tagged separately because it needs a browser, and skipped when a backend theme
is installed - a theme rewrites the very selectors the tour steps on, and a
failure there says nothing about this module.
"""
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_match_tour')
class StaffingTourCase(HttpCase):

    def _skip_if_backend_theme(self):
        """A theme replaces the web client's markup, so the selectors below
        stop meaning what they mean here. Skipping is honest; adapting the
        selectors to every theme is not something this suite can promise."""
        themed = self.env['ir.module.module'].search_count([
            ('state', '=', 'installed'),
            ('name', 'in', ('muk_web_theme', 'web_enterprise',
                            'backend_theme_v16', 'odoo_backend_theme')),
        ])
        if themed:
            self.skipTest('a backend theme is installed; tour selectors would '
                          'be testing the theme rather than this module')

    def test_a_planner_can_reach_the_staffing_screens(self):
        """The demo tour, which is also the sales walkthrough.

        It asserts the path exists: the app appears in the menu, the requests
        list opens, and a new request accepts a name. Each of those is a
        different way the UI can be broken while every model test stays green.
        """
        self._skip_if_backend_theme()
        planner = self.env['res.users'].create({
            'name': 'Tour Planner',
            'login': 'tour_planner',
            'password': 'tour_planner',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('aic_hrm_match.group_match_planner').id,
            ])],
        })
        self.start_tour('/odoo', 'aic_hrm_match_demo',
                        login=planner.login, timeout=120)
