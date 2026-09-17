# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import ReviewCase


@tagged('post_install', '-at_install', 'aic_hrm_review')
class TestReviewFlow(ReviewCase):

    def test_generate_one_review_per_employee(self):
        review_cycle = self._make_review_cycle()
        reviews = review_cycle.review_ids
        self.assertEqual(
            set(reviews.mapped('employee_id')),
            {self.manager_employee, self.reviewee,
             self.peer1, self.peer2, self.peer3})
        # generation is idempotent
        review_cycle.action_generate_reviews()
        self.assertEqual(len(review_cycle.review_ids), len(reviews))

    def test_goal_score_is_live_until_it_is_fixed(self):
        """A review generated while the period is still running must not
        freeze a premature figure: it reads the scorecards live, and the
        snapshot is taken when the appraisal is signed."""
        review_cycle = self._make_review_cycle()
        review = review_cycle.review_ids.filtered(
            lambda r: r.employee_id == self.reviewee)
        self.assertAlmostEqual(review.goal_score_live, 0.9, places=2)
        self.assertFalse(review.goal_score_snapshot_on)
        review.action_refresh_goal_score()
        self.assertAlmostEqual(review.goal_score, 0.9, places=2)
        # once fixed, later scorecard changes never rewrite the appraisal
        results = self.assignment.line_ids.kpi_target_id.period_result_ids
        results.action_reset_to_draft(reason='Rà soát lại số liệu của kỳ đánh giá.')
        results.write({'actual': 10.0})
        results.action_confirm()
        review.invalidate_recordset()
        self.assertAlmostEqual(review.goal_score_live, 0.1, places=2)
        self.assertAlmostEqual(review.goal_score, 0.9, places=2)

    def test_stage_progression(self):
        review_cycle = self._make_review_cycle()
        review = review_cycle.review_ids.filtered(
            lambda r: r.employee_id == self.reviewee)
        self.assertEqual(review.stage_id.stage_type, 'self')
        review.write({'self_score': 0.8})
        review.action_next_stage()
        self.assertEqual(review.stage_id.stage_type, 'peer_feedback')
        review.action_next_stage()
        self.assertEqual(review.stage_id.stage_type, 'manager')
        review.write({'manager_score': 0.85, 'potential_rating': '2'})
        review.action_next_stage()
        self.assertEqual(review.stage_id.stage_type, 'final')
        self.assertTrue(review.is_final)

    def test_final_score_prefers_calibrated(self):
        review_cycle = self._make_review_cycle()
        review = review_cycle.review_ids.filtered(
            lambda r: r.employee_id == self.reviewee)
        review.write({'manager_score': 0.7})
        self.assertAlmostEqual(review.final_score, 0.7)
        review.write({'calibrated_score': 0.75})
        self.assertAlmostEqual(review.final_score, 0.75)

    def test_manager_score_manager_only(self):
        review_cycle = self._make_review_cycle()
        review = review_cycle.review_ids.filtered(
            lambda r: r.employee_id == self.reviewee)
        with self.assertRaises(UserError):
            review.with_user(self.reviewee_user).write(
                {'manager_score': 1.0})
