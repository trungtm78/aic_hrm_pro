# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestMetricSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Source = cls.env['aic.hrm.metric.source']
        cls.Allowed = cls.env['aic.hrm.metric.allowed.model']
        cls.rag_model = cls.env['ir.model']._get('aic.hrm.rag.profile')
        cls.Allowed.create({'model_id': cls.rag_model.id})
        cls.env['aic.hrm.rag.profile'].create(
            {'name': 'MS-A', 'green_from': 0.8, 'amber_from': 0.4})
        cls.env['aic.hrm.rag.profile'].create(
            {'name': 'MS-B', 'green_from': 0.6, 'amber_from': 0.3})

    def _make_source(self, **kw):
        vals = {
            'name': 'Avg green threshold',
            'model_id': self.rag_model.id,
            'domain': "[('name', 'like', 'MS-')]",
            'field_name': 'green_from',
            'aggregate': 'avg',
        }
        vals.update(kw)
        return self.Source.create(vals)

    def test_model_must_be_allowlisted(self):
        cycle_model = self.env['ir.model']._get('aic.hrm.cycle')
        with self.assertRaises(ValidationError):
            self._make_source(model_id=cycle_model.id)

    def test_field_must_be_stored_numeric(self):
        with self.assertRaises(ValidationError):
            self._make_source(field_name='name')
        with self.assertRaises(ValidationError):
            self._make_source(field_name='no_such_field')

    def test_compute_value_aggregates(self):
        avg_source = self._make_source()
        self.assertAlmostEqual(avg_source.compute_value(), 0.7)
        sum_source = self._make_source(name='Sum', aggregate='sum')
        self.assertAlmostEqual(sum_source.compute_value(), 1.4)
        count_source = self._make_source(name='Count', aggregate='count')
        self.assertAlmostEqual(count_source.compute_value(), 2.0)

    def test_bad_domain_raises_validation(self):
        with self.assertRaises(ValidationError):
            self._make_source(domain="[('nonexistent', '=', 1)]").compute_value()
