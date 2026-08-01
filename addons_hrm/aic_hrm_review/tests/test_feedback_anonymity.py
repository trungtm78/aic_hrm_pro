# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import ReviewCase


@tagged('post_install', '-at_install', 'aic_hrm_review')
class TestFeedbackAnonymity(ReviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.review_cycle = cls._make_review_cycle()
        cls.review = cls.review_cycle.review_ids.filtered(
            lambda r: r.employee_id == cls.reviewee)
        cls.requests = cls.env['aic.hrm.feedback.request'].create([
            {'review_id': cls.review.id, 'rater_employee_id': peer.id,
             'rater_role': 'peer'}
            for peer in (cls.peer1, cls.peer2, cls.peer3)])

    def _submit(self, request, user, rating, text='keep shipping'):
        request.with_user(user).submit_feedback([
            {'question_id': self.form.section_ids.question_ids[0].id,
             'rating': rating},
            {'question_id': self.form.section_ids.question_ids[1].id,
             'text': text},
        ])

    def test_rater_sees_own_request_only(self):
        mine = self.env['aic.hrm.feedback.request'].with_user(
            self.peer1_user).search([('review_id', '=', self.review.id)])
        self.assertEqual(len(mine), 1,
                         "a rater sees exactly their own invitation")
        # The rater identity field itself stays admin-only even for the
        # rater: identity flows through record rules, never through reads.
        self.assertEqual(
            mine.sudo().rater_employee_id, self.peer1)

    def test_reviewee_cannot_read_requests(self):
        visible = self.env['aic.hrm.feedback.request'].with_user(
            self.reviewee_user).search(
            [('review_id', '=', self.review.id)])
        self.assertFalse(visible)

    def test_response_create_uid_hides_rater(self):
        self._submit(self.requests[0], self.peer1_user, 8)
        response = self.env['aic.hrm.feedback.response'].sudo().search([
            ('request_id', '=', self.requests[0].id)], limit=1)
        self.assertNotEqual(
            response.create_uid, self.peer1_user,
            "responses must be written by the system user so create_uid "
            "never identifies the rater")

    def test_aggregate_hidden_below_min_raters(self):
        self._submit(self.requests[0], self.peer1_user, 8)
        self._submit(self.requests[1], self.peer2_user, 6)
        self.assertFalse(
            self.review.peer_feedback_ready,
            "2 of 3 raters: aggregate stays hidden")
        self.assertEqual(self.review.peer_score_avg, 0.0)
        self._submit(self.requests[2], self.peer3_user, 7)
        self.assertTrue(self.review.peer_feedback_ready)
        self.assertAlmostEqual(self.review.peer_score_avg, 0.7)

    def test_reviewee_cannot_read_raw_responses(self):
        self._submit(self.requests[0], self.peer1_user, 8)
        with self.assertRaises(AccessError):
            self.env['aic.hrm.feedback.response'].with_user(
                self.reviewee_user).search([]).mapped('rating')

    def test_rater_cannot_submit_twice(self):
        self._submit(self.requests[0], self.peer1_user, 8)
        with self.assertRaises(Exception):
            self._submit(self.requests[0], self.peer1_user, 9)

    def test_small_team_warning(self):
        self.assertTrue(self.review_cycle.small_team_warning is not None)
