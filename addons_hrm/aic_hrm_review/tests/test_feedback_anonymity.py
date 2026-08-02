# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, UserError
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

    def test_write_uid_hides_rater_on_submit(self):
        self._submit(self.requests[0], self.peer1_user, 8)
        self.assertNotEqual(
            self.requests[0].sudo().write_uid, self.peer1_user,
            "state flips are written by the system user - write_uid must "
            "not identify the rater either")

    def test_manager_cannot_read_requests(self):
        visible = self.env['aic.hrm.feedback.request'].with_user(
            self.manager_user).search(
            [('review_id', '=', self.review.id)])
        self.assertFalse(
            visible,
            "per-invite status pre-threshold would leak who has spoken")
        self.assertEqual(self.review.with_user(
            self.manager_user).feedback_invited_count, 3,
            "managers follow progress through aggregate counts")

    def test_answer_outside_form_rejected(self):
        foreign_question = self.env['aic.hrm.review.question'].create({
            'section_id': self.env['aic.hrm.review.section'].create({
                'form_id': self.env['aic.hrm.review.form'].create(
                    {'name': 'Other form'}).id,
                'name': 'Other section'}).id,
            'name': 'Not in this template',
        })
        with self.assertRaises(Exception):
            self.requests[0].with_user(self.peer1_user).submit_feedback([
                {'question_id': foreign_question.id, 'rating': 5}])

    def test_small_team_warning(self):
        self.assertTrue(self.review_cycle.small_team_warning is not None)

    def _hr_admin(self):
        return self.env['res.users'].create({
            'name': 'Rev HR Admin', 'login': 'rev_hr_admin',
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('aic_hrm_base.group_hrm_admin').id])],
        })

    def _external_request(self):
        """A rater with no login: the 'external' role, and every employee
        the import wizard creates for a name it could not match."""
        outsider = self.env['hr.employee'].create({'name': 'Outside Rater'})
        self.assertFalse(outsider.user_id)
        return self.env['aic.hrm.feedback.request'].create({
            'review_id': self.review.id,
            'rater_employee_id': outsider.id,
            'rater_role': 'external',
        })

    def test_rater_without_login_cannot_be_spoken_for(self):
        """The guard used to read `if rater_user_id and ...`, so a rater
        with no account fell through it and anyone could submit in their
        name - untraceably, because responses are written by the system
        user on purpose."""
        request = self._external_request()
        with self.assertRaises(UserError):
            self._submit(request, self.peer1_user, 5)
        self.assertEqual(request.state, 'invited')
        self.assertFalse(request.sudo().response_ids)

    def test_hr_admin_may_transcribe_for_a_rater_without_login(self):
        """Someone has to be able to record a paper answer, or the
        external role is decorative. That someone is the administrator who
        issued the invitation."""
        request = self._external_request()
        self._submit(request, self._hr_admin(), 4)
        self.assertEqual(request.sudo().state, 'submitted')

    def test_invited_rater_still_submits_normally(self):
        self._submit(self.requests[0], self.peer1_user, 5)
        self.assertEqual(self.requests[0].sudo().state, 'submitted')
