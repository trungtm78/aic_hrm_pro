# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The screens, driven the way a person drives them.

Everything else in this suite talks to models. That catches wrong answers and
misses broken screens entirely: a view whose button names a method that does not
exist, a menu pointing at a deleted action, a kanban template renamed between
Odoo versions. All of those pass every model test and greet the buyer with a
blank page - the last one does not even fail at install.

Tagged separately because it needs a browser. Two things make a tour suite lie
about itself, and both are guarded here: a backend theme rewrites the selectors
so a failure says nothing about this module, and a missing websocket-client
makes ``start_tour`` return without driving anything at all, reporting green
having checked nothing.
"""
from odoo.tests import HttpCase, tagged


class StaffingTourMixin:
    """Shared fixtures. Deliberately not a TestCase - inheriting one would run
    the desktop tours again at phone width and call it extra coverage."""

    def _skip_if_backend_theme(self):
        """A theme replaces the web client's markup, so the selectors below
        stop meaning what they mean here. Skipping is honest; adapting them to
        every theme is not something this suite can promise."""
        themed = self.env['ir.module.module'].search_count([
            ('state', '=', 'installed'),
            ('name', 'in', ('muk_web_theme', 'web_enterprise',
                            'backend_theme_v16', 'odoo_backend_theme')),
        ])
        if themed:
            self.skipTest('a backend theme is installed; tour selectors would '
                          'be testing the theme rather than this module')

    def _user(self, name, group):
        """A user holding exactly one staffing group, so the tour walks the
        screens under the access rights a real planner or administrator has
        rather than a superuser's."""
        login = name.lower().replace(' ', '_')
        return self.env['res.users'].create({
            'name': name,
            'login': login,
            'password': login,
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('aic_hrm_match.%s' % group).id,
            ])],
        })


@tagged('post_install', '-at_install', 'aic_hrm_match_tour')
class StaffingTourCase(StaffingTourMixin, HttpCase):

    def test_a_planner_can_reach_the_staffing_screens(self):
        """The demo tour, which doubles as the sales walkthrough.

        It asserts the path exists: the app appears in the menu, the Requests
        section opens, and the list renders. Each of those is a different way
        the UI breaks while every model test stays green.
        """
        self._skip_if_backend_theme()
        planner = self._user('Tour Planner', 'group_match_planner')
        self.start_tour('/odoo', 'aic_hrm_match_demo',
                        login=planner.login, timeout=120)

    def test_an_administrator_can_reach_the_scoring_policies(self):
        """The listing page promises weights somebody can read and change, so
        the screen showing them has to open - under an administrator's own
        access rights, not a superuser's."""
        self._skip_if_backend_theme()
        admin = self._user('Tour Admin', 'group_match_admin')
        self.start_tour('/odoo', 'aic_hrm_match_admin',
                        login=admin.login, timeout=120)


@tagged('post_install', '-at_install', 'aic_hrm_match_tour')
class StaffingMobileTourCase(StaffingTourMixin, HttpCase):
    """The same screens at phone width.

    A separate class because the size is a class attribute: the browser starts
    before any test body runs, so setting it inside a test has no effect, and a
    mobile check that silently ran at desktop width would pass without testing
    anything.
    """
    browser_size = '375x667'

    def test_the_screens_do_not_scroll_sideways_on_a_phone(self):
        """Measured rather than eyeballed.

        "Mobile responsive" is a claim about behaviour, and it fails the same
        way every time: a table wider than the viewport takes the whole page
        with it and the first column scrolls off. A screenshot review can miss
        that; comparing two widths cannot.
        """
        self._skip_if_backend_theme()
        planner = self._user('Tour Mobile', 'group_match_planner')
        self.start_tour(
            '/odoo/action-aic_hrm_match.action_aic_hrm_match_request',
            'aic_hrm_match_mobile', login=planner.login, timeout=120)
