# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The KPI score a quarterly review is built on.

KPIs are assigned per month while a review covers the quarter, so the review
has to look down the cycle tree, not only at the quarter itself, or every
quarterly review starts at zero. What it reads is a live figure until the
review reaches the manager stage; from then on it is a snapshot with a name
and a timestamp on it, because an appraisal must not move under the person
who signed it.
"""
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ReviewCase


@tagged('post_install', '-at_install', 'aic_hrm_review')
class TestGoalSnapshot(ReviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.quarter = env['aic.hrm.cycle'].create({
            'name': 'Q1 2026', 'code': 'REV-Q1', 'cycle_type': 'quarter',
            'date_start': '2026-01-01', 'date_end': '2026-03-31'})
        cls.january = env['aic.hrm.cycle'].create({
            'name': 'January 2026', 'code': 'REV-01', 'cycle_type': 'month',
            'date_start': '2026-01-01', 'date_end': '2026-01-31',
            'parent_id': cls.quarter.id})
        cls.february = env['aic.hrm.cycle'].create({
            'name': 'February 2026', 'code': 'REV-02', 'cycle_type': 'month',
            'date_start': '2026-02-01', 'date_end': '2026-02-28',
            'parent_id': cls.quarter.id})
        cls.kpi = env['aic.hrm.kpi'].create({'name': 'Doanh thu quý', 'code': 'REV-KPI-Q'})

    def _scorecard(self, cycle, actual, date_from, date_to, weight=100.0):
        target = self.env['aic.hrm.kpi.target'].create({
            'kpi_id': self.kpi.id, 'cycle_id': cycle.id,
            'employee_id': self.reviewee.id, 'target_value': 100.0})
        self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': target.id, 'date_from': date_from, 'date_to': date_to,
            'actual': actual, 'state': 'confirmed'})
        return self.env['aic.hrm.kpi.assignment'].create({
            'employee_id': self.reviewee.id, 'cycle_id': cycle.id,
            'line_ids': [(0, 0, {'kpi_target_id': target.id, 'weight': weight})]})

    def _review_cycle(self):
        return self.env['aic.hrm.review.cycle'].create({
            'name': 'Đánh giá Quý I/2026', 'perf_cycle_id': self.quarter.id,
            'template_id': self.template.id, 'date_start': '2026-04-01',
            'date_end': '2026-04-15'})

    def test_a_quarterly_review_reads_the_monthly_scorecards(self):
        self._scorecard(self.january, 60.0, '2026-01-01', '2026-01-31')
        self._scorecard(self.february, 80.0, '2026-02-01', '2026-02-28')
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        review = cycle.review_ids.filtered(lambda r: r.employee_id == self.reviewee)
        self.assertAlmostEqual(review.goal_score_live, 0.7, places=4,
                               msg='average of the January and February scorecards')
        self.assertAlmostEqual(review.goal_coverage_live, 100.0, places=2)

    def test_the_live_figure_follows_the_scorecards_until_it_is_frozen(self):
        card = self._scorecard(self.january, 60.0, '2026-01-01', '2026-01-31')
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        review = cycle.review_ids.filtered(lambda r: r.employee_id == self.reviewee)
        self.assertAlmostEqual(review.goal_score_live, 0.6, places=4)
        self._scorecard(self.february, 100.0, '2026-02-01', '2026-02-28')
        review.invalidate_recordset()
        self.assertAlmostEqual(review.goal_score_live, 0.8, places=4)
        self.assertFalse(review.goal_score_snapshot_on, 'nothing frozen yet')
        self.assertTrue(card)

    def test_reaching_the_manager_stage_freezes_the_figure(self):
        self._scorecard(self.january, 60.0, '2026-01-01', '2026-01-31')
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        review = cycle.review_ids.filtered(lambda r: r.employee_id == self.reviewee)
        manager_stage = self.template.stage_ids.filtered(
            lambda s: s.stage_type == 'manager')[:1]
        review.with_user(self.manager_user).stage_id = manager_stage
        review.invalidate_recordset()
        self.assertAlmostEqual(review.goal_score, 0.6, places=4)
        self.assertEqual(review.goal_score_snapshot_by, self.manager_user)
        self.assertTrue(review.goal_score_snapshot_on)
        # The scorecards keep moving; the appraisal does not.
        self._scorecard(self.february, 100.0, '2026-02-01', '2026-02-28')
        review.invalidate_recordset()
        self.assertAlmostEqual(review.goal_score, 0.6, places=4)
        self.assertAlmostEqual(review.goal_score_live, 0.8, places=4)

    def test_a_manager_can_refresh_the_snapshot_and_it_is_logged(self):
        self._scorecard(self.january, 60.0, '2026-01-01', '2026-01-31')
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        review = cycle.review_ids.filtered(lambda r: r.employee_id == self.reviewee)
        review.with_user(self.manager_user).action_refresh_goal_score()
        review.invalidate_recordset()
        self.assertAlmostEqual(review.goal_score, 0.6, places=4)
        body = ' '.join(review.message_ids.mapped('body'))
        self.assertIn('60', body, 'the snapshot is written in the review log')

    def test_only_managers_refresh_the_snapshot(self):
        self._scorecard(self.january, 60.0, '2026-01-01', '2026-01-31')
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        review = cycle.review_ids.filtered(lambda r: r.employee_id == self.reviewee)
        with self.assertRaises(UserError):
            review.with_user(self.reviewee_user).action_refresh_goal_score()

    def test_a_review_cannot_be_finalised_without_a_frozen_figure(self):
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        review = cycle.review_ids.filtered(lambda r: r.employee_id == self.reviewee)
        with self.assertRaises(UserError):
            review.with_user(self.manager_user).action_finalize_review()

    def test_the_review_cycle_moves_one_step_at_a_time(self):
        cycle = self._review_cycle()
        self.assertEqual(cycle.state, 'draft')
        with self.assertRaises(UserError):
            cycle.with_user(self.manager_user).write({'state': 'closed'})
        cycle.action_generate_reviews()
        self.assertEqual(cycle.state, 'open')
        cycle.with_user(self.manager_user).write({'state': 'calibration'})
        self.assertEqual(cycle.state, 'calibration')

    def test_closing_a_cycle_with_unfinished_reviews_is_refused(self):
        self._scorecard(self.january, 60.0, '2026-01-01', '2026-01-31')
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        cycle.with_user(self.manager_user).write({'state': 'calibration'})
        with self.assertRaises(UserError):
            cycle.with_user(self.manager_user).write({'state': 'closed'})

    def test_generating_reviews_is_logged_and_never_duplicates(self):
        cycle = self._review_cycle()
        cycle.action_generate_reviews()
        first = len(cycle.review_ids)
        self.assertTrue(first)
        cycle.action_generate_reviews()
        self.assertEqual(len(cycle.review_ids), first)
        body = ' '.join(cycle.message_ids.mapped('body'))
        self.assertIn(str(first), body)
