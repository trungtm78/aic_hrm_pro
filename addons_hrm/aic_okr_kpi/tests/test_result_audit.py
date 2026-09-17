# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Governance of the figures a score is made of.

A person's score is only as trustworthy as the actual figures behind it, so
every change to a period result leaves an append-only audit event (who, when,
before, after, why), confirming and un-confirming is a manager's act, a
confirmed figure cannot be edited or deleted behind the score, and undoing a
confirmed figure demands a written reason.
"""
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestResultAudit(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Audit = cls.env['aic.hrm.kpi.result.audit']

    def audit_of(self, result):
        return self.Audit.search([('result_id', '=', result.id)], order='id')

    def test_entering_a_figure_is_recorded(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        [event] = self.audit_of(result)
        self.assertEqual((event.action, event.new_actual, event.new_state), ('create', 80.0, 'draft'))
        self.assertEqual(event.user_id, self.env.user)
        self.assertEqual(event.kpi_target_id, target)
        self.assertTrue(event.event_date)
        self.assertEqual(len(event.evidence_checksum), 64)

    def test_editing_a_draft_figure_records_before_and_after(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        result.actual = 95.0
        event = self.audit_of(result)[-1]
        self.assertEqual((event.action, event.old_actual, event.new_actual), ('edit', 80.0, 95.0))

    def test_confirming_stamps_who_and_when_and_is_recorded(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        result.with_user(self.manager_user).action_confirm()
        result.invalidate_recordset()
        self.assertEqual(result.confirmed_by, self.manager_user)
        self.assertTrue(result.confirmed_on)
        event = self.audit_of(result)[-1]
        self.assertEqual((event.action, event.old_state, event.new_state), ('confirm', 'draft', 'confirmed'))
        self.assertEqual(event.user_id, self.manager_user)

    def test_a_member_cannot_confirm_even_by_writing_the_field(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        with self.assertRaises(UserError):
            result.with_user(self.member_user).action_confirm()
        with self.assertRaises(UserError):
            result.with_user(self.member_user).write({'state': 'confirmed'})
        self.assertEqual(result.state, 'draft')

    def test_a_member_cannot_create_an_already_confirmed_figure(self):
        target = self._make_target()
        with self.assertRaises(UserError):
            self.PeriodResult.with_user(self.member_user).create({
                'kpi_target_id': target.id, 'date_from': '2026-02-01', 'date_to': '2026-02-28',
                'actual': 50.0, 'state': 'confirmed'})

    def test_a_confirmed_figure_cannot_be_edited_or_deleted_behind_the_score(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0)
        self.assertEqual(result.state, 'confirmed')
        for vals in ({'actual': 10.0}, {'date_to': '2026-02-05'}):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                result.write(vals)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            result.unlink()

    def test_undoing_a_confirmed_figure_needs_a_reason(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0)
        with self.assertRaises(UserError):
            result.with_user(self.manager_user).action_reset_to_draft()

    def test_undoing_through_the_wizard_records_the_reason(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0)
        result.confirmed_by = self.manager_user
        action = result.with_user(self.manager_user).action_open_reset_wizard()
        wizard = Form(self.env[action['res_model']].with_user(self.manager_user)
                      .with_context(action['context']))
        self.assertIn(target.kpi_id.name, wizard.affected_summary)
        wizard.reason = 'Kế toán phát hiện hoá đơn ghi sai kỳ, cần nhập lại số tháng 1.'
        wizard.save().action_reset()
        result.invalidate_recordset()
        self.assertEqual(result.state, 'draft')
        self.assertFalse(result.confirmed_by)
        event = self.audit_of(result)[-1]
        self.assertEqual((event.action, event.old_state, event.new_state), ('reset', 'confirmed', 'draft'))
        self.assertIn('hoá đơn ghi sai kỳ', event.reason)
        self.assertTrue(event.same_user, 'the resetter is the one who confirmed')

    def test_a_short_reason_is_refused(self):
        """A three-word reason is no reason; the wizard refuses to be saved."""
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0)
        with self.assertRaises(ValidationError):
            self.env['aic.hrm.kpi.result.reset.wizard'].with_user(self.manager_user).create(
                {'result_ids': [(6, 0, result.ids)], 'reason': 'sai'})
        self.assertEqual(result.state, 'confirmed')

    def test_undoing_is_written_on_the_kpi_target_chatter(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0)
        wizard = self.env['aic.hrm.kpi.result.reset.wizard'].with_user(self.manager_user).create(
            {'result_ids': [(6, 0, result.ids)],
             'reason': 'Số liệu nguồn được kế toán điều chỉnh sau khi rà soát.'})
        wizard.action_reset()
        body = ' '.join(target.message_ids.mapped('body'))
        self.assertIn('rà soát', body)

    def test_deleting_a_draft_figure_is_recorded_before_it_goes(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        result.unlink()
        [_created, deleted] = self.Audit.search([('kpi_target_id', '=', target.id)], order='id')
        self.assertEqual((deleted.action, deleted.old_actual), ('delete', 80.0))

    def test_the_audit_trail_cannot_be_rewritten_or_erased(self):
        target = self._make_target()
        result = self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        [event] = self.audit_of(result)
        for record in (event, event.sudo()):
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                record.write({'reason': 'sửa lại'})
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                record.unlink()

    def test_members_may_read_but_never_write_the_trail(self):
        target = self._make_target()
        self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        trail = self.Audit.with_user(self.member_user).search([('kpi_target_id', '=', target.id)])
        self.assertTrue(trail)
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.Audit.with_user(self.member_user).create({
                'result_id': trail.result_id.id, 'kpi_target_id': target.id, 'action': 'confirm'})

    def test_a_period_outside_its_cycle_is_refused(self):
        target = self._make_target(cycle_id=self.quarter.id)
        with self.assertRaises(ValidationError):
            self._add_result(target, '2026-01-01', '2026-01-31', 10.0, state='draft')

    def test_the_target_lists_its_own_trail(self):
        target = self._make_target()
        self._add_result(target, '2026-01-01', '2026-01-31', 80.0, state='draft')
        action = target.action_open_result_audit()
        self.assertEqual(action['res_model'], 'aic.hrm.kpi.result.audit')
        self.assertEqual(action['domain'], [('kpi_target_id', '=', target.id)])
        self.assertGreaterEqual(target.audit_count, 1)
