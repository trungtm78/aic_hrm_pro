# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""How people are ranked, expressed as data a customer owns.

Two ideas carry this file.

**Weights are data, not code.** A consultancy that cares more about customer
history than about technology depth should be able to say so without a
developer, and the criteria catalogue plus a weight per criterion is how.

**Changing how people are ranked is a decision, not an edit.** An active policy
is frozen; altering it means forking a new version, and the old one stays
readable so a ranking from last quarter can still be explained. An archived
version is frozen too - history that can be rewritten is not history.
"""
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import MatchCase


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CriterionCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Criterion = cls.env['aic.hrm.match.criterion']

    def _criterion(self, **kwargs):
        values = {'code': 'availability', 'name': 'Availability',
                  'category': 'availability'}
        values.update(kwargs)
        return self.Criterion.create(values)

    @mute_logger('odoo.sql_db')
    def test_a_code_is_unique_within_its_scope(self):
        self._criterion()
        with self.assertRaises(IntegrityError):
            self._criterion()

    def test_shared_criteria_collide_even_though_company_is_null(self):
        """Same NULL trap as everywhere else: without COALESCE two shared
        criteria could carry one code while the constraint appeared to work."""
        self._criterion(code='shared_one', company_id=False)
        with self.assertRaises(Exception):
            self._criterion(code='shared_one', company_id=False)

    def test_the_code_is_what_binds_a_criterion_to_its_scorer(self):
        """Discovery is by naming convention, so a criterion whose code has no
        matching _score_<code> is visibly unimplemented rather than silently
        contributing nothing."""
        known = self._criterion(code='availability')
        unknown = self._criterion(code='vibes_based', name='Vibes')
        self.assertTrue(known.implemented)
        self.assertFalse(unknown.implemented)

    def test_a_weight_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._criterion(weight=-1.0)

    def test_param_json_must_parse(self):
        """Malformed parameters would surface deep inside the scoring loop, on
        one candidate, as something that looks like a data problem."""
        with self.assertRaises(ValidationError):
            self._criterion(param_json='{not json')

    def test_param_json_must_be_an_object(self):
        with self.assertRaises(ValidationError):
            self._criterion(param_json='[1, 2, 3]')

    def test_parameters_are_read_as_a_mapping(self):
        criterion = self._criterion(param_json='{"half_life_days": 540}')
        self.assertEqual(criterion.get_params()['half_life_days'], 540)

    def test_a_criterion_with_no_parameters_reads_as_empty(self):
        self.assertEqual(self._criterion().get_params(), {})

    def test_a_hard_criterion_declares_it(self):
        """Hard eliminates, soft ranks. The distinction decides whether a
        failure removes somebody or merely costs them points."""
        gate = self._criterion(mode='hard')
        self.assertEqual(gate.mode, 'hard')


@tagged('post_install', '-at_install', 'aic_hrm_match')
class PolicyVersioningCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['aic.hrm.match.policy']
        cls.Criterion = cls.env['aic.hrm.match.criterion']
        cls.availability = cls.Criterion.create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability'})

    def _policy(self, **kwargs):
        values = {'name': 'Delivery Staffing', 'code': 'delivery'}
        values.update(kwargs)
        policy = self.Policy.create(values)
        self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': self.availability.id,
            'weight': 1.0})
        return policy

    def test_a_policy_starts_in_draft_at_version_one(self):
        policy = self._policy()
        self.assertEqual(policy.state, 'draft')
        self.assertEqual(policy.version, 1)

    def test_two_versions_share_a_code(self):
        """The code names the policy; the version names the revision. A unique
        constraint on code alone would make versioning impossible."""
        first = self._policy()
        first.action_activate()
        second = first.action_new_version()
        self.assertEqual(second.code, first.code)
        self.assertEqual(second.version, first.version + 1)

    @mute_logger('odoo.sql_db')
    def test_the_same_version_cannot_exist_twice(self):
        self._policy()
        with self.assertRaises(IntegrityError):
            self.Policy.create({'name': 'Clash', 'code': 'delivery',
                                'version': 1})

    def test_activating_freezes_the_policy(self):
        """A ranking has to stay explainable. If the weights behind it can be
        edited afterwards, the explanation is fiction."""
        policy = self._policy()
        policy.action_activate()
        with self.assertRaises(UserError):
            policy.write({'top_n': 5})

    def test_an_archived_policy_is_frozen_too(self):
        """History that can be rewritten is not history."""
        policy = self._policy()
        policy.action_activate()
        successor = policy.action_new_version()
        successor.action_activate()
        self.assertEqual(policy.state, 'archived')
        with self.assertRaises(UserError):
            policy.write({'top_n': 5})

    def test_the_lines_of_a_frozen_policy_are_frozen(self):
        """Locking the policy while leaving its weights editable would protect
        the wrapper and not the thing that decides the ranking."""
        policy = self._policy()
        policy.action_activate()
        with self.assertRaises(UserError):
            policy.line_ids[0].write({'weight': 9.0})

    def test_new_lines_cannot_be_added_to_a_frozen_policy(self):
        policy = self._policy()
        policy.action_activate()
        other = self.Criterion.create({
            'code': 'skill_fit', 'name': 'Skill fit', 'category': 'skill'})
        with self.assertRaises(UserError):
            self.env['aic.hrm.match.policy.line'].create({
                'policy_id': policy.id, 'criterion_id': other.id})

    def test_lines_of_a_frozen_policy_cannot_be_removed(self):
        policy = self._policy()
        policy.action_activate()
        with self.assertRaises(UserError):
            policy.line_ids[0].unlink()

    def test_a_draft_policy_is_freely_editable(self):
        policy = self._policy()
        policy.write({'top_n': 5})
        policy.line_ids[0].write({'weight': 2.0})
        self.assertEqual(policy.top_n, 5)

    def test_a_new_version_copies_the_weights(self):
        policy = self._policy()
        policy.line_ids[0].weight = 3.0
        policy.action_activate()
        successor = policy.action_new_version()
        self.assertEqual(len(successor.line_ids), 1)
        self.assertAlmostEqual(successor.line_ids[0].weight, 3.0)
        self.assertEqual(successor.state, 'draft')

    def test_only_one_version_may_be_active(self):
        policy = self._policy()
        policy.action_activate()
        successor = policy.action_new_version()
        successor.action_activate()
        self.assertEqual(policy.state, 'archived')
        self.assertEqual(
            self.Policy.search_count([('code', '=', 'delivery'),
                                      ('state', '=', 'active')]), 1)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class PolicyActivationCase(MatchCase):
    """Activation is the gate. Everything it refuses would otherwise become a
    ranking run under rules that never executed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['aic.hrm.match.policy']
        cls.Criterion = cls.env['aic.hrm.match.criterion']

    def _policy_with(self, criterion, weight=1.0, **kwargs):
        values = {'name': 'Test policy', 'code': 'testing'}
        values.update(kwargs)
        policy = self.Policy.create(values)
        self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': criterion.id,
            'weight': weight})
        return policy

    def test_a_criterion_without_a_scorer_blocks_activation(self):
        """Fail closed. Ignoring it would produce a staffing decision made
        under a rule that never ran, and nothing on screen would say so."""
        orphan = self.Criterion.create({
            'code': 'no_such_scorer', 'name': 'Orphan', 'category': 'custom'})
        policy = self._policy_with(orphan)
        with self.assertRaises(UserError) as caught:
            policy.action_activate()
        self.assertIn('no_such_scorer', str(caught.exception))

    def test_a_disabled_line_does_not_block_activation(self):
        """Only what will actually run has to be implemented. A criterion
        parked for later must not stop the policy it sits in from publishing.
        """
        working = self.Criterion.create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability'})
        orphan = self.Criterion.create({
            'code': 'future_idea', 'name': 'Future', 'category': 'custom'})
        policy = self._policy_with(working)
        self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': orphan.id,
            'weight': 1.0, 'enabled': False})
        policy.action_activate()
        self.assertEqual(policy.state, 'active')

    def test_a_policy_with_no_weight_at_all_is_refused(self):
        """Dividing by a zero weight sum is the crash; ranking everybody
        identically is the subtler failure it becomes if guarded carelessly."""
        criterion = self.Criterion.create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability'})
        policy = self._policy_with(criterion, weight=0.0)
        with self.assertRaises(UserError):
            policy.action_activate()

    def test_an_empty_policy_is_refused(self):
        policy = self.Policy.create({'name': 'Nothing', 'code': 'empty'})
        with self.assertRaises(UserError):
            policy.action_activate()

    def test_load_balance_and_the_workload_criterion_are_mutually_exclusive(self):
        """Both measure the same thing. Running them together counts one
        signal twice, and neither screen says so."""
        workload = self.Criterion.create({
            'code': 'workload_balance', 'name': 'Workload balance',
            'category': 'fairness'})
        policy = self._policy_with(workload, fairness_mode='load_balance')
        with self.assertRaises(UserError):
            policy.action_activate()

    def test_sensitivity_is_visible_on_the_policy(self):
        """The record rules that hide performance figures key on this, so it
        has to be stored rather than computed on the fly."""
        sensitive = self.Criterion.create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability', 'is_sensitive': True})
        policy = self._policy_with(sensitive)
        self.assertTrue(policy.has_sensitive_criterion)

    def test_a_policy_of_ordinary_criteria_is_not_sensitive(self):
        plain = self.Criterion.create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability'})
        self.assertFalse(self._policy_with(plain).has_sensitive_criterion)


@tagged('post_install', '-at_install', 'aic_hrm_match')
class PolicyLineSnapshotCase(MatchCase):
    """A line remembers what it was pointing at, so uninstalling a connector
    does not erase the history of rankings that used its criteria."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Policy = cls.env['aic.hrm.match.policy']
        cls.criterion = cls.env['aic.hrm.match.criterion'].create({
            'code': 'availability', 'name': 'Availability',
            'category': 'availability'})

    def test_a_line_snapshots_the_criterion_it_points_at(self):
        policy = self.Policy.create({'name': 'Snap', 'code': 'snap'})
        line = self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': self.criterion.id})
        self.assertEqual(line.criterion_code, 'availability')
        self.assertTrue(line.criterion_name)

    def test_removing_a_criterion_leaves_the_line_readable(self):
        """restrict here would block uninstalling a connector; cascade would
        erase the record of what a past ranking was configured with."""
        policy = self.Policy.create({'name': 'Snap', 'code': 'snap2'})
        line = self.env['aic.hrm.match.policy.line'].create({
            'policy_id': policy.id, 'criterion_id': self.criterion.id})
        self.criterion.unlink()
        self.assertTrue(line.exists())
        self.assertFalse(line.criterion_id)
        self.assertEqual(line.criterion_code, 'availability')
