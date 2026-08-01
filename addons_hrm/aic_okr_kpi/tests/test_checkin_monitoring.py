# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestCheckin(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Checkin = cls.env['aic.hrm.checkin']
        cls.objective = cls._make_objective(
            employee_id=cls.member_employee.id)
        cls.kr = cls._make_kr(
            cls.objective, baseline=0, target=100, current=20,
            employee_id=cls.member_employee.id)
        cls.kpi_target = cls._make_target()

    def test_kr_checkin_writes_through(self):
        checkin = self.Checkin.create({
            'kr_id': self.kr.id,
            'value_current': 55.0,
            'confidence': 7,
            'note': 'Steady progress',
        })
        self.assertAlmostEqual(self.kr.current, 55.0)
        self.assertAlmostEqual(checkin.progress_snapshot, 0.55)
        self.assertEqual(checkin.rag_snapshot, 'amber')
        self.assertEqual(self.kr.confidence, 7)
        self.assertEqual(self.kr.last_checkin_date,
                         fields.Date.context_today(self.kr))

    def test_kpi_checkin_creates_draft_period_result(self):
        checkin = self.Checkin.create({
            'kpi_target_id': self.kpi_target.id,
            'value_current': 70.0,
            'confidence': 6,
        })
        result = self.kpi_target.period_result_ids
        self.assertEqual(len(result), 1)
        self.assertEqual(result.state, 'draft')
        self.assertEqual(result.source, 'checkin')
        self.assertAlmostEqual(result.actual, 70.0)
        self.assertTrue(checkin.id)

    def test_exactly_one_parent(self):
        with self.assertRaises(ValidationError):
            self.Checkin.create({'value_current': 1.0, 'confidence': 5})
        with self.assertRaises(ValidationError):
            self.Checkin.create({
                'kr_id': self.kr.id, 'kpi_target_id': self.kpi_target.id,
                'value_current': 1.0, 'confidence': 5})

    def test_confidence_bounds(self):
        with self.assertRaises(ValidationError):
            self.Checkin.create({
                'kr_id': self.kr.id, 'value_current': 1.0, 'confidence': 11})

    def test_stale_kr_detection(self):
        self.Checkin.create({
            'kr_id': self.kr.id, 'value_current': 30.0, 'confidence': 5})
        self.assertFalse(self.kr.is_stale)
        stale_date = fields.Date.context_today(self.kr) - timedelta(days=30)
        self.kr.write({'last_checkin_date': stale_date})
        self.assertTrue(self.kr.is_stale)


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestAlertRules(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AlertRule = cls.env['aic.hrm.alert.rule']
        cls.objective = cls._make_objective(
            employee_id=cls.member_employee.id)
        cls.kr = cls._make_kr(
            cls.objective, baseline=0, target=100, current=5,
            employee_id=cls.member_employee.id)
        # Alert rules only watch OPEN cycles — that is the monitoring window.
        cls.year.action_open()

    def test_stale_rule_creates_activity(self):
        rule = self.AlertRule.create({
            'name': 'Stale goals', 'rule_type': 'stale_kr',
            'escalation_days': 3,
        })
        stale_date = fields.Date.context_today(self.kr) - timedelta(days=40)
        self.kr.write({'last_checkin_date': stale_date})
        rule.run()
        activity = self.env['mail.activity'].search([
            ('res_model', '=', 'aic.hrm.key.result'),
            ('res_id', '=', self.kr.id),
        ])
        self.assertTrue(activity, "stale KR must get a follow-up activity")
        # Running twice must not duplicate the open activity.
        rule.run()
        activity_after = self.env['mail.activity'].search([
            ('res_model', '=', 'aic.hrm.key.result'),
            ('res_id', '=', self.kr.id),
        ])
        self.assertEqual(len(activity_after), len(activity))

    def test_confidence_drop_rule(self):
        Checkin = self.env['aic.hrm.checkin']
        for confidence in (8, 6, 4):
            Checkin.create({
                'kr_id': self.kr.id, 'value_current': 10.0,
                'confidence': confidence})
        rule = self.AlertRule.create({
            'name': 'Confidence sliding', 'rule_type': 'confidence_drop',
            'streak_length': 3,
        })
        matches = rule._find_matches()
        self.assertIn(self.kr, matches)

    def test_red_rag_rule(self):
        rule = self.AlertRule.create({
            'name': 'Red goals', 'rule_type': 'rag_red',
        })
        matches = rule._find_matches()
        self.assertIn(self.kr, matches, "KR at 5% of target is red")

    def test_cron_runs_all_active_rules(self):
        self.AlertRule.create({
            'name': 'Cron stale', 'rule_type': 'stale_kr'})
        self.AlertRule._cron_run_alert_rules()


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestReviewMeeting(KpiCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Meeting = cls.env['aic.hrm.review.meeting']
        cls.objective = cls._make_objective(
            employee_id=cls.member_employee.id)
        cls.red_kr = cls._make_kr(
            cls.objective, name='Red KR', baseline=0, target=100, current=5,
            employee_id=cls.member_employee.id)

    def test_agenda_lists_red_goals(self):
        meeting = self.Meeting.create({
            'name': 'Monthly review 2026-03',
            'cycle_id': self.year.id,
            'date': '2026-03-31',
        })
        meeting.action_build_agenda()
        self.assertIn('Red KR', meeting.agenda)

    def test_action_items_lifecycle(self):
        meeting = self.Meeting.create({
            'name': 'Review with actions',
            'cycle_id': self.year.id,
            'date': '2026-04-30',
            'action_item_ids': [(0, 0, {
                'name': 'Unblock data pipeline',
                'owner_id': self.member_employee.id,
                'deadline': '2026-05-15',
            })],
        })
        item = meeting.action_item_ids
        self.assertEqual(item.state, 'todo')
        item.action_done()
        self.assertEqual(item.state, 'done')
        self.assertEqual(meeting.open_action_count, 0)

    def test_meeting_states(self):
        meeting = self.Meeting.create({
            'name': 'State test', 'cycle_id': self.year.id,
            'date': '2026-05-31',
        })
        self.assertEqual(meeting.state, 'draft')
        meeting.action_hold()
        self.assertEqual(meeting.state, 'held')
        meeting.action_close()
        self.assertEqual(meeting.state, 'done')
