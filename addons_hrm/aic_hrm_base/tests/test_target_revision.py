# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError, ValidationError
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


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestTargetRevisionRequest(TransactionCase):
    """Asking for a revision from the record itself.

    The revision form alone asks a manager to type a technical model name
    ("aic.hrm.key.result") and a field name ("target"). Requesting from the
    record fills both in and offers only the fields that are governed, by
    their labels.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cycle = cls.env['aic.hrm.cycle'].create({
            'name': 'FY 2026', 'code': 'FY26-REQ', 'cycle_type': 'year',
            'date_start': '2026-01-01', 'date_end': '2026-12-31',
        })

    def _request(self, **kw):
        action = self.cycle.action_request_target_revision()
        Request = self.env[action['res_model']].with_context(action['context'])
        vals = {'field_name': 'score_cap', 'new_value': 1.2,
                'reason': 'Sales may overachieve up to 120%.'}
        vals.update(kw)
        return Request.create(vals)

    def test_action_opens_the_request_for_this_record(self):
        action = self.cycle.action_request_target_revision()
        self.assertEqual(action['res_model'], 'aic.hrm.target.revision.request')
        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['context']['default_res_model'], 'aic.hrm.cycle')
        self.assertEqual(action['context']['default_res_id'], self.cycle.id)

    def test_only_governed_fields_are_offered_by_label(self):
        Request = self.env['aic.hrm.target.revision.request'].with_context(
            default_res_model='aic.hrm.cycle')
        selection = Request.fields_get(['field_name'])['field_name']['selection']
        self.assertEqual([tuple(option) for option in selection],
                         [('score_cap', 'Score Cap')])

    def test_request_shows_the_current_value(self):
        request = self._request()
        self.assertAlmostEqual(request.current_value, 1.0)
        self.assertEqual(request.record_name, self.cycle.display_name)

    def test_submit_files_a_requested_revision_and_opens_it(self):
        request = self._request()
        action = request.action_submit()
        revision = self.env['aic.hrm.target.revision'].browse(action['res_id'])
        self.assertEqual(action['res_model'], 'aic.hrm.target.revision')
        self.assertEqual(
            (revision.res_model, revision.res_id, revision.field_name,
             revision.new_value_float, revision.state),
            ('aic.hrm.cycle', self.cycle.id, 'score_cap', 1.2, 'requested'))
        self.assertAlmostEqual(revision.old_value_float, 1.0)
        self.assertAlmostEqual(self.cycle.score_cap, 1.0,
                               'nothing changes before approval')

    def test_a_model_without_governed_fields_cannot_ask(self):
        profile = self.env['aic.hrm.rag.profile'].search([], limit=1)
        Request = self.env['aic.hrm.target.revision.request'].with_context(
            default_res_model='aic.hrm.rag.profile', default_res_id=profile.id)
        self.assertEqual(
            Request.fields_get(['field_name'])['field_name']['selection'], [])
        with self.assertRaises(UserError):
            Request.create({'new_value': 0.8, 'reason': 'Not governed.'})
