# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestTargetRevision(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Revision = cls.env['aic.hrm.target.revision']
        cls.cycle = cls.env['aic.hrm.cycle'].create({
            'name': 'FY 2026', 'code': 'FY26-REV', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })

    def _make_revision(self, **kw):
        vals = {
            'res_model': 'aic.hrm.cycle',
            'res_id': self.cycle.id,
            'field_name': 'score_cap',
            'new_value_float': 1.2,
            'reason': 'Sales cycles may overachieve up to 120%.',
        }
        vals.update(kw)
        return self.Revision.create(vals)

    def test_reason_is_mandatory(self):
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self._make_revision(reason=False)

    def test_old_value_captured_on_create(self):
        revision = self._make_revision()
        self.assertAlmostEqual(revision.old_value_float, 1.0)
        self.assertEqual(revision.state, 'requested')

    def test_approve_applies_value(self):
        revision = self._make_revision()
        revision.action_approve()
        self.assertEqual(revision.state, 'approved')
        self.assertAlmostEqual(self.cycle.score_cap, 1.2)
        self.assertEqual(revision.approved_by, self.env.user)

    def test_reject_leaves_target_untouched(self):
        revision = self._make_revision()
        revision.action_reject()
        self.assertEqual(revision.state, 'rejected')
        self.assertAlmostEqual(self.cycle.score_cap, 1.0)

    def test_approve_requires_requested_state(self):
        revision = self._make_revision()
        revision.action_approve()
        with self.assertRaises(ValidationError):
            revision.action_approve()
        rejected = self._make_revision(new_value_float=1.1)
        rejected.action_reject()
        with self.assertRaises(ValidationError):
            rejected.action_approve()

    def test_field_must_be_governed(self):
        profile = self.env['aic.hrm.rag.profile'].create(
            {'name': 'Gov', 'green_from': 0.7, 'amber_from': 0.4})
        with self.assertRaises(ValidationError):
            self._make_revision(
                res_model='aic.hrm.rag.profile', res_id=profile.id,
                field_name='green_from', new_value_float=0.8)

    def test_target_must_exist(self):
        with self.assertRaises(ValidationError):
            self._make_revision(res_id=99999999)

    def test_unknown_field_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_revision(field_name='not_a_field')

    def test_non_float_field_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_revision(field_name='name')
