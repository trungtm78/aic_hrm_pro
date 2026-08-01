# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'aic_hrm_base')
class TestCycle(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cycle = cls.env['aic.hrm.cycle']

    def _make_cycle(self, **kw):
        vals = {
            'name': 'FY 2026',
            'code': kw.pop('code', 'FY26'),
            'cycle_type': 'year',
            'date_start': '2026-01-01',
            'date_end': '2026-12-31',
        }
        vals.update(kw)
        return self.Cycle.create(vals)

    def test_create_defaults(self):
        cycle = self._make_cycle()
        self.assertEqual(cycle.state, 'draft')
        self.assertEqual(cycle.check_in_frequency, 'weekly')
        self.assertEqual(cycle.stale_days, 14)
        self.assertAlmostEqual(cycle.score_cap, 1.0)
        self.assertTrue(cycle.rag_profile_id, "cycle must default to the default RAG profile")

    def test_stale_days_follows_frequency(self):
        cycle = self._make_cycle(check_in_frequency='monthly')
        self.assertEqual(cycle.stale_days, 60)

    def test_date_constraint(self):
        with self.assertRaises(ValidationError):
            self._make_cycle(code='BAD', date_start='2026-12-31', date_end='2026-01-01')

    def test_code_unique_per_company(self):
        self._make_cycle(code='Q1-26')
        with self.assertRaises(Exception), self.env.cr.savepoint():
            self._make_cycle(code='Q1-26')

    def test_parent_containment(self):
        year = self._make_cycle()
        quarter = self._make_cycle(
            code='Q2-26', name='Q2 2026', cycle_type='quarter',
            date_start='2026-04-01', date_end='2026-06-30', parent_id=year.id)
        self.assertEqual(quarter.parent_id, year)
        with self.assertRaises(ValidationError):
            self._make_cycle(
                code='QX-26', cycle_type='quarter', parent_id=year.id,
                date_start='2026-11-01', date_end='2027-01-31')

    def test_no_parent_recursion(self):
        year = self._make_cycle()
        with self.assertRaises(ValidationError):
            year.parent_id = year

    def test_state_flow(self):
        cycle = self._make_cycle()
        cycle.action_open()
        self.assertEqual(cycle.state, 'open')
        cycle.action_start_review()
        self.assertEqual(cycle.state, 'review')
        cycle.action_close()
        self.assertEqual(cycle.state, 'closed')
        cycle.action_lock()
        self.assertEqual(cycle.state, 'locked')

    def test_illegal_transitions_blocked(self):
        cycle = self._make_cycle()
        with self.assertRaises(UserError):
            cycle.action_lock()  # draft -> locked is not allowed
        with self.assertRaises(UserError):
            cycle.action_close()  # draft -> closed is not allowed

    def test_state_direct_write_blocked(self):
        cycle = self._make_cycle()
        with self.assertRaises(UserError):
            cycle.write({'state': 'locked'})

    def test_locked_cycle_immutable(self):
        cycle = self._make_cycle()
        cycle.action_open()
        cycle.action_start_review()
        cycle.action_close()
        cycle.action_lock()
        with self.assertRaises(UserError):
            cycle.write({'name': 'Tampered'})

    def test_unlink_only_draft(self):
        cycle = self._make_cycle()
        cycle.action_open()
        with self.assertRaises(UserError):
            cycle.unlink()
        draft = self._make_cycle(code='DRAFT-DEL')
        draft.unlink()
        self.assertFalse(draft.exists())

    def test_parent_company_must_match(self):
        other_company = self.env['res.company'].create({'name': 'Cycle Co 2'})
        year = self._make_cycle()
        with self.assertRaises(ValidationError):
            self._make_cycle(
                code='Q-OTHER', parent_id=year.id, company_id=other_company.id,
                date_start='2026-04-01', date_end='2026-06-30')

    def test_rag_profile_company_must_match(self):
        other_company = self.env['res.company'].create({'name': 'Cycle Co 3'})
        foreign_profile = self.env['aic.hrm.rag.profile'].create({
            'name': 'Foreign', 'green_from': 0.7, 'amber_from': 0.4,
            'company_id': other_company.id,
        })
        with self.assertRaises(ValidationError):
            self._make_cycle(code='RAGX', rag_profile_id=foreign_profile.id)

    def test_ensure_editable_guard(self):
        cycle = self._make_cycle()
        cycle.action_open()
        cycle.ensure_editable()  # open: no error
        cycle.action_start_review()
        cycle.action_close()
        cycle.ensure_editable()  # closed still allows corrective edits via revisions
        cycle.action_lock()
        with self.assertRaises(UserError):
            cycle.ensure_editable()
