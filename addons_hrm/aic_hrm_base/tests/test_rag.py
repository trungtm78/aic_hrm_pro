# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestRagProfile(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Profile = cls.env['aic.hrm.rag.profile']

    def test_default_profile_from_data(self):
        default = self.env.ref('aic_hrm_base.rag_profile_default')
        self.assertAlmostEqual(default.green_from, 0.7)
        self.assertAlmostEqual(default.amber_from, 0.4)

    def test_resolve_bands(self):
        profile = self.Profile.create(
            {'name': 'Strict', 'green_from': 0.8, 'amber_from': 0.5})
        self.assertEqual(profile.resolve(0.85), 'green')
        self.assertEqual(profile.resolve(0.8), 'green')   # boundary inclusive
        self.assertEqual(profile.resolve(0.79), 'amber')
        self.assertEqual(profile.resolve(0.5), 'amber')   # boundary inclusive
        self.assertEqual(profile.resolve(0.49), 'red')
        self.assertEqual(profile.resolve(0.0), 'red')

    def test_threshold_ordering_constraint(self):
        with self.assertRaises(ValidationError):
            self.Profile.create(
                {'name': 'Broken', 'green_from': 0.4, 'amber_from': 0.7})
        with self.assertRaises(ValidationError):
            self.Profile.create(
                {'name': 'OutOfRange', 'green_from': 1.2, 'amber_from': 0.4})
