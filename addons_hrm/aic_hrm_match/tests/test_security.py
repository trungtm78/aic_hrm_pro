# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Who may see and change what.

Odoo's record rules have three semantics that all have to hold at once, and
every one of them can produce a system that looks locked down and is not:

1. Rules of *different groups* are ORed. One rule with a permissive domain
   therefore cancels every restrictive rule on the same model - which is how a
   department restriction becomes decorative.
2. Rules with no ``groups`` are *global* and intersect with the result. Company
   isolation must be expressed this way; give it a group and it gets ORed away.
3. A model with no applicable rule at all is unrestricted, bounded only by the
   access-control list.

These tests exercise the outcome through ``search`` and ``read`` as an actual
user, because that is the only thing that proves the rule rather than the
intention behind it.
"""
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class ConfigurationWriteAccessCase(MatchCase):
    """The vocabulary decides how everybody is ranked, so changing it is an
    administrative act, not a planning one."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls._make_user('Sam User', ['group_match_user'])
        cls.planner = cls._make_user('Pat Planner', ['group_match_planner'])
        cls.admin = cls._make_user('Ada Admin', ['group_match_admin'])

    def test_a_planner_cannot_invent_vocabulary(self):
        """A planner who can add tags can quietly reshape what "similar
        experience" means, and every future ranking inherits it."""
        with self.assertRaises(AccessError):
            self.Tag.with_user(self.planner).create({
                'name': 'Invented', 'code': 'invented',
                'category_id': self.category_tech.id})

    def test_a_planner_cannot_reweight_a_similarity_dimension(self):
        with self.assertRaises(AccessError):
            self.category_tech.with_user(self.planner).write(
                {'similarity_weight': 9.0})

    def test_an_ordinary_user_cannot_write_vocabulary_either(self):
        with self.assertRaises(AccessError):
            self.Tag.with_user(self.user).create({
                'name': 'Nope', 'code': 'nope',
                'category_id': self.category_tech.id})

    def test_everyone_may_read_the_vocabulary(self):
        """Reading is not the sensitive part: a tag is a word, and hiding it
        would only stop people describing their own skills."""
        for user in (self.user, self.planner, self.admin):
            self.assertTrue(
                self.Tag.with_user(user).search_count([]) >= 0)
            self.category_tech.with_user(user).read(['name'])

    def test_an_administrator_owns_the_vocabulary(self):
        tag = self.Tag.with_user(self.admin).create({
            'name': 'Owned', 'code': 'owned',
            'category_id': self.category_tech.id})
        self.assertTrue(tag.id)
        tag.with_user(self.admin).write({'name': 'Renamed'})
        tag.with_user(self.admin).unlink()

    def test_seniority_is_administrative_too(self):
        with self.assertRaises(AccessError):
            self.Seniority.with_user(self.planner).create(
                {'code': 'x', 'name': 'X', 'rank': 1})


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CompanyIsolationCase(MatchCase):
    """S17 of the security matrix: a company's private vocabulary stays private.

    Expressed as a *global* rule. With a ``groups`` attribute it would be ORed
    against the read rules above and disappear the moment a user holds any of
    them - which is to say, always.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tag_shared = cls._make_tag(code='shared', name='Shared',
                                       company_id=False)
        cls.tag_a = cls._make_tag(code='only_a', name='Only A',
                                  company_id=cls.company.id)
        cls.tag_b = cls._make_tag(code='only_b', name='Only B',
                                  company_id=cls.other_company.id)
        cls.user_a = cls._make_user('Ann Alpha', ['group_match_planner'],
                                    company=cls.company)
        cls.user_b = cls._make_user('Bob Beta', ['group_match_planner'],
                                    company=cls.other_company,
                                    companies=cls.other_company)
        cls.admin_a = cls._make_user('Al Admin', ['group_match_admin'],
                                     company=cls.company)

    def test_a_user_does_not_see_another_companys_tags(self):
        visible = self.Tag.with_user(self.user_a).search([]).ids
        self.assertIn(self.tag_a.id, visible)
        self.assertNotIn(self.tag_b.id, visible)

    def test_shared_vocabulary_is_visible_to_everyone(self):
        """A tag with no company is the common vocabulary; hiding it per
        company would force every company to reinvent "Python"."""
        for user in (self.user_a, self.user_b):
            self.assertIn(self.tag_shared.id,
                          self.Tag.with_user(user).search([]).ids)

    def test_reading_another_companys_tag_by_id_is_refused(self):
        """search() filtering silently is not enough. Anyone can guess an id,
        and read() is what an RPC client actually calls."""
        with self.assertRaises(AccessError):
            self.tag_b.with_user(self.user_a).read(['name'])

    def test_being_an_administrator_does_not_cross_the_company_line(self):
        """Administrator is a role inside a company, not above all of them."""
        with self.assertRaises(AccessError):
            self.tag_b.with_user(self.admin_a).read(['name'])

    def test_read_group_does_not_leak_across_companies(self):
        """Aggregates are the leak people forget: a count is still an answer
        about records the user may not read."""
        groups = self.Tag.with_user(self.user_a)._read_group(
            [], ['company_id'], ['__count'])
        seen = {company.id for company, _count in groups if company}
        self.assertNotIn(self.other_company.id, seen)

    def test_a_user_with_both_companies_active_sees_both(self):
        """Isolation follows the active companies, not the login."""
        both = self.company | self.other_company
        user = self._make_user('Cam Cross', ['group_match_planner'],
                               company=self.company, companies=both)
        visible = self.Tag.with_user(user).with_context(
            allowed_company_ids=both.ids).search([]).ids
        self.assertIn(self.tag_a.id, visible)
        self.assertIn(self.tag_b.id, visible)
