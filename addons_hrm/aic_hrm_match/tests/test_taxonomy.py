# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The vocabulary the matching runs against.

Tags are a tree on purpose: somebody who has done React has done Frontend, and
a flat tag list makes the engine miss that. The tests below pin the two things
that go wrong quietly - a tree that lets somebody build a cycle, and a
uniqueness rule that does not actually hold for the shared (company-less)
records everybody uses.
"""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class TagCategoryCase(MatchCase):

    @mute_logger('odoo.sql_db')
    def test_category_code_is_unique(self):
        with self.assertRaises(IntegrityError):
            self._make_tag_category(code='technology', name='Duplicate')

    def test_similarity_weight_cannot_be_negative(self):
        """A negative weight would invert the meaning of a whole category:
        matching the customer's industry would count against you."""
        with self.assertRaises(ValidationError):
            self._make_tag_category(code='weird', name='Weird',
                                    similarity_weight=-1.0)

    def test_categories_order_by_sequence(self):
        first = self._make_tag_category(code='aaa', name='Aaa', sequence=1)
        last = self._make_tag_category(code='zzz', name='Zzz', sequence=99)
        ordered = (first | last).sorted()
        self.assertEqual(ordered[0], first)
        self.assertEqual(ordered[-1], last)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class TagTreeCase(MatchCase):

    def test_tag_code_is_unique_inside_a_category_and_company(self):
        self._make_tag(code='react', name='React')
        with self.assertRaises(ValidationError):
            self._make_tag(code='react', name='React again')

    def test_the_same_code_may_exist_in_another_category(self):
        """"Retail" is a legitimate industry and a legitimate domain; the code
        only has to be unique within the vocabulary it belongs to."""
        self._make_tag(code='retail', name='Retail')
        other = self._make_tag(code='retail', name='Retail',
                               category_id=self.category_industry.id)
        self.assertTrue(other.id)

    def test_shared_tags_collide_even_though_company_is_null(self):
        """The trap this guards: Postgres treats every NULL as distinct, so a
        plain unique(code, category_id, company_id) lets two shared tags with
        the same code exist and the constraint looks like it is working."""
        self._make_tag(code='python', name='Python', company_id=False)
        with self.assertRaises(ValidationError):
            self._make_tag(code='python', name='Python too', company_id=False)

    def test_a_company_may_shadow_a_shared_code(self):
        self._make_tag(code='sap', name='SAP', company_id=False)
        owned = self._make_tag(code='sap', name='SAP',
                               company_id=self.company.id)
        self.assertTrue(owned.id)

    @mute_logger('odoo.sql_db')
    def test_the_database_holds_the_line_for_shared_tags(self):
        """The Python check races: two transactions both pass it and both
        commit. The index is what actually prevents the duplicate."""
        self._make_tag(code='rust', name='Rust', company_id=False)
        with self.assertRaises(IntegrityError):
            # `name` is a translated field, so the column is jsonb.
            self.env.cr.execute(
                """INSERT INTO aic_hrm_match_tag
                       (name, code, category_id, company_id, active,
                        create_uid, write_uid, create_date, write_date)
                   VALUES (%s::jsonb, 'rust', %s, NULL, true,
                           1, 1, now(), now())""",
                ('{"en_US": "Rust again"}', self.category_tech.id))

    def test_parent_path_is_maintained(self):
        frontend = self._make_tag(code='frontend', name='Frontend')
        react = self._make_tag(code='reactjs', name='React',
                               parent_id=frontend.id)
        self.assertTrue(react.parent_path.startswith(frontend.parent_path))

    def test_a_tag_cannot_become_its_own_ancestor(self):
        parent = self._make_tag(code='p', name='Parent')
        child = self._make_tag(code='c', name='Child', parent_id=parent.id)
        with self.assertRaises(UserError):
            parent.parent_id = child

    def test_renaming_a_code_onto_an_existing_one_is_refused(self):
        """The write path needs the same guard as create: otherwise a rename
        reaches the index and the user meets a database traceback."""
        self._make_tag(code='go', name='Go')
        other = self._make_tag(code='golang', name='Golang')
        with self.assertRaises(ValidationError):
            other.code = 'go'

    def test_renaming_a_tag_to_its_own_code_is_allowed(self):
        """A no-op write must not accuse the record of colliding with itself."""
        tag = self._make_tag(code='kotlin', name='Kotlin')
        tag.write({'code': 'kotlin', 'name': 'Kotlin (JVM)'})
        self.assertEqual(tag.code, 'kotlin')

    def test_a_batch_cannot_contain_its_own_duplicate(self):
        """Two identical codes in one create() never touch an existing row, so
        only a check of the batch against itself catches them."""
        with self.assertRaises(ValidationError):
            self.Tag.create([
                {'name': 'Scala', 'code': 'scala',
                 'category_id': self.category_tech.id},
                {'name': 'Scala again', 'code': 'scala',
                 'category_id': self.category_tech.id},
            ])

    @mute_logger('odoo.sql_db')
    def test_missing_required_values_are_left_to_the_orm(self):
        """Our duplicate check must not turn a missing-field error into a
        confusing message about uniqueness."""
        with self.assertRaises(Exception) as caught:
            self.Tag.create({'name': 'No category', 'code': 'orphan'})
        self.assertNotIn('already used', str(caught.exception))

    def test_a_child_must_stay_inside_its_parents_category(self):
        """A technology nested under an industry makes ancestor credit
        meaningless: the distance would cross two unrelated vocabularies."""
        industry = self._make_tag(code='manufacturing', name='Manufacturing',
                                  category_id=self.category_industry.id)
        with self.assertRaises(ValidationError):
            self._make_tag(code='plc', name='PLC', parent_id=industry.id)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class TagDistanceCase(MatchCase):
    """Ancestor credit is what lets experience in React count towards a
    Frontend requirement. Distance is computed from parent_path, once."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.frontend = cls._make_tag(code='fe', name='Frontend')
        cls.react = cls._make_tag(code='react', name='React',
                                  parent_id=cls.frontend.id)
        cls.hooks = cls._make_tag(code='hooks', name='React Hooks',
                                  parent_id=cls.react.id)
        cls.backend = cls._make_tag(code='be', name='Backend')

    def test_distance_to_itself_is_zero(self):
        self.assertEqual(self.react.ancestor_distance(self.react), 0)

    def test_distance_to_a_parent(self):
        self.assertEqual(self.hooks.ancestor_distance(self.react), 1)
        self.assertEqual(self.hooks.ancestor_distance(self.frontend), 2)

    def test_distance_to_a_descendant_counts_the_same(self):
        """Credit runs both ways: a Frontend requirement is partly met by
        React experience, and a React requirement is partly met by somebody
        who has done Frontend work generally."""
        self.assertEqual(self.frontend.ancestor_distance(self.hooks), 2)

    def test_unrelated_tags_have_no_distance(self):
        self.assertIsNone(self.react.ancestor_distance(self.backend))

    def test_expand_related_returns_one_map_for_the_whole_request(self):
        """Built once per run. Comparing parent_path prefixes inside the
        scoring loop is a million string comparisons for two thousand people."""
        related = self.frontend.expand_related()
        self.assertEqual(related[self.frontend.id], 0)
        self.assertEqual(related[self.react.id], 1)
        self.assertEqual(related[self.hooks.id], 2)
        self.assertNotIn(self.backend.id, related)

    def test_expand_related_merges_several_tags_keeping_the_closest(self):
        related = (self.frontend | self.react).expand_related()
        self.assertEqual(related[self.react.id], 0)
        self.assertEqual(related[self.hooks.id], 1)

    def test_expand_related_of_nothing_is_an_empty_map(self):
        """A request with no tags is ordinary - it just scores nothing on
        similarity - so this has to answer rather than raise."""
        self.assertEqual(self.Tag.browse().expand_related(), {})


@tagged('post_install', '-at_install', 'aic_hrm_match')
class SeniorityCase(MatchCase):

    @mute_logger('odoo.sql_db')
    def test_seniority_code_is_unique(self):
        self._make_seniority(code='junior', name='Junior', rank=10)
        with self.assertRaises(IntegrityError):
            self._make_seniority(code='junior', name='Junior again', rank=11)

    def test_rank_orders_the_ladder(self):
        junior = self._make_seniority(code='jr', name='Junior', rank=10)
        senior = self._make_seniority(code='sr', name='Senior', rank=30)
        self.assertLess(junior.rank, senior.rank)
        self.assertEqual((senior | junior).sorted()[0], junior)

    def test_rank_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._make_seniority(code='neg', name='Negative', rank=-5)
