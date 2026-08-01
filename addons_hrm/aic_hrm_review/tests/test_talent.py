# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from .common import ReviewCase


@tagged('post_install', '-at_install', 'aic_hrm_review')
class TestTalent(ReviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.review_cycle = cls._make_review_cycle()
        cls.review = cls.review_cycle.review_ids.filtered(
            lambda r: r.employee_id == cls.reviewee)

    def test_nine_box_placement(self):
        self.review.write({'manager_score': 0.9, 'potential_rating': '3'})
        box = self.review.nine_box_position
        self.assertEqual(box, 'star',
                         "high performance x high potential = star")
        self.review.write({'manager_score': 0.2, 'potential_rating': '1'})
        self.assertEqual(self.review.nine_box_position, 'underperformer')

    def test_pip_suggested_below_threshold(self):
        self.review.write({'manager_score': 0.3})
        self.review.action_finalize_review()
        self.assertTrue(
            self.review.pip_suggested,
            "a final score in the red band suggests a PIP")
        pip = self.env['aic.hrm.idp'].search([
            ('employee_id', '=', self.reviewee.id),
            ('plan_type', '=', 'pip')])
        self.assertTrue(pip, "the suggested PIP plan is created in draft")
        self.assertEqual(len(pip.action_ids), 3,
                         "PIP ships with 30/60/90-day checkpoints")

    def test_idp_lifecycle(self):
        idp = self.env['aic.hrm.idp'].create({
            'employee_id': self.reviewee.id,
            'review_id': self.review.id,
            'plan_type': 'development',
            'action_ids': [(0, 0, {
                'name': 'Lead the Q3 architecture review',
                'action_type': 'project',
            })],
        })
        self.assertEqual(idp.state, 'draft')
        idp.action_activate()
        self.assertEqual(idp.state, 'active')
        idp.action_ids.action_done()
        idp.action_close()
        self.assertEqual(idp.state, 'done')
