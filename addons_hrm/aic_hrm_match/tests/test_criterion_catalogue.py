# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What the product ships with, and what it promises about it.

The catalogue is the product. "Twelve criteria you can read, change and defend -
seven on by default" is the sentence on the listing page, and a customer who
installs this and finds an empty configuration screen has been sold something
that does not exist.

So the shipped data is tested like code: every criterion has to be one this
database can actually score, the default policy has to activate, and the count
has to match what the marketing copy says. Data files are the part of a module
nobody runs before shipping, which is exactly why they need a test.
"""
from odoo.tests import tagged

from .common import MatchCase

# The number the listing page quotes. Changing either of these means changing
# the copy in static/description/index.html in the same commit.
SHIPPED_CRITERIA = 12
ENABLED_BY_DEFAULT = 7


@tagged('post_install', '-at_install', 'aic_hrm_match')
class CriterionCatalogueCase(MatchCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Criterion = cls.env['aic.hrm.match.criterion']
        cls.shipped = cls.Criterion.search([
            ('id', 'in', cls._shipped_ids())])

    @classmethod
    def _shipped_ids(cls):
        """The catalogue entries this module's data file created.

        Found through ir.model.data rather than by searching every criterion in
        the database, so a criterion a customer added themselves - or one a
        connector brought - does not make the shipped count wrong.
        """
        records = cls.env['ir.model.data'].search([
            ('module', '=', 'aic_hrm_match'),
            ('model', '=', 'aic.hrm.match.criterion'),
        ])
        return records.mapped('res_id')

    def test_the_catalogue_ships_the_criteria_the_listing_promises(self):
        self.assertEqual(len(self.shipped), SHIPPED_CRITERIA)

    def test_every_shipped_criterion_can_actually_be_scored(self):
        """A criterion in the catalogue with no scorer behind it is a
        configuration screen that offers something the engine cannot do.
        Activation refuses it, so a customer who ticks it gets an error rather
        than a ranking - after they have already changed their weights."""
        codes = self.env['aic.hrm.match.scorer'].get_scorer_codes()
        unimplemented = [c.code for c in self.shipped if c.code not in codes]
        self.assertFalse(unimplemented,
                         'shipped but not implemented: %s' % unimplemented)

    def test_each_criterion_explains_itself(self):
        """These are read by whoever tunes the weights, and a name alone does
        not say what "continuity" measures or which way is better."""
        for criterion in self.shipped:
            self.assertTrue(criterion.description, criterion.code)
            self.assertTrue(criterion.name, criterion.code)

    def test_no_two_criteria_share_a_code(self):
        codes = self.shipped.mapped('code')
        self.assertEqual(len(codes), len(set(codes)))

    def test_the_parameters_are_valid_json(self):
        """Parsed once per run. A typo here surfaces as a failed ranking rather
        than as a configuration error, and only for the policies that use it."""
        for criterion in self.shipped.filtered('param_json'):
            self.assertIsInstance(criterion.get_params(), dict, criterion.code)

    def test_sensitive_criteria_are_marked_as_such(self):
        """Past performance is a personnel record, not a staffing attribute.
        Shipping it unmarked would put appraisal figures in front of every
        planner the moment the connector is installed."""
        performance = self.shipped.filtered(
            lambda c: c.category == 'performance')
        for criterion in performance:
            self.assertTrue(criterion.is_sensitive, criterion.code)

    # -- the default policy --------------------------------------------------

    def test_a_default_policy_ships_and_is_active(self):
        """Installing the app has to leave something that can rank. A first run
        that fails with "no policy applies" is indistinguishable from a broken
        install."""
        policy = self.env.ref('aic_hrm_match.policy_default')
        self.assertEqual(policy.state, 'active')
        self.assertTrue(policy.is_default)

    def test_the_default_policy_enables_the_number_the_copy_claims(self):
        policy = self.env.ref('aic_hrm_match.policy_default')
        self.assertEqual(len(policy.line_ids.filtered('enabled')),
                         ENABLED_BY_DEFAULT)

    def test_the_default_policy_lists_every_criterion(self):
        """Disabled rather than absent, so turning one on is a tick rather than
        a lookup through a catalogue the planner has not seen."""
        self.assertEqual(len(policy_lines := self.env.ref(
            'aic_hrm_match.policy_default').line_ids), SHIPPED_CRITERIA)
        self.assertTrue(policy_lines)

    def test_the_enabled_weights_add_up_to_a_hundred(self):
        """The screen shows a checksum row. Shipping a default that does not
        total 100% teaches every reader to ignore it."""
        policy = self.env.ref('aic_hrm_match.policy_default')
        total = sum(policy.line_ids.filtered('enabled').mapped('weight'))
        self.assertAlmostEqual(total, 100.0, places=4)

    def test_the_default_policy_ranks_without_further_configuration(self):
        """The end-to-end claim: install, press the button, get a shortlist."""
        employee = self._make_employee('Straight Out Of The Box')
        request = self.env['aic.hrm.match.request'].create({
            'name': 'First run',
            'date_start': '2026-09-14 00:00:00',
            'date_end': '2026-09-18 23:59:59'})
        self.env['aic.hrm.match.request.slot'].create({
            'request_id': request.id, 'name': 'Anyone', 'required_hours': 8.0})

        run = self.env['aic.hrm.match.engine'].run_match(
            request, policy=self.env.ref('aic_hrm_match.policy_default'))
        self.assertEqual(run.state, 'computed')
        self.assertTrue(run.candidate_ids.filtered(
            lambda c: c.employee_id == employee))

    def test_load_balancing_and_the_workload_criterion_are_not_both_on(self):
        """They measure the same thing from two directions. Shipping both
        enabled would count one signal twice while the weights say otherwise -
        and the activation guard refuses the combination anyway."""
        policy = self.env.ref('aic_hrm_match.policy_default')
        workload_on = policy.line_ids.filtered(
            lambda l: l.enabled and l.criterion_code == 'workload_balance')
        self.assertFalse(workload_on and policy.fairness_mode == 'load_balance')
