# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import ReviewCase


@tagged('post_install', '-at_install', 'aic_hrm_review')
class TestCalibration(ReviewCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.review_cycle = cls._make_review_cycle()
        cls.review = cls.review_cycle.review_ids.filtered(
            lambda r: r.employee_id == cls.reviewee)
        cls.review.write({'manager_score': 0.7})
        cls.session = cls.env['aic.hrm.calibration.session'].create({
            'name': 'Year-end calibration',
            'review_cycle_id': cls.review_cycle.id,
            'line_ids': [(0, 0, {'review_id': cls.review.id,
                                 'score_after': 0.7})],
        })

    def test_score_before_snapshot(self):
        line = self.session.line_ids
        self.assertAlmostEqual(line.score_before, 0.7)

    def test_change_requires_justification(self):
        line = self.session.line_ids
        with self.assertRaises(ValidationError):
            line.write({'score_after': 0.9})
        line.write({'score_after': 0.9,
                    'justification': 'Delivered the platform launch under '
                                     'a frozen headcount.'})
        self.assertAlmostEqual(line.score_after, 0.9)

    def test_apply_writes_calibrated_score(self):
        line = self.session.line_ids
        line.write({'score_after': 0.85,
                    'justification': 'Consistent overdelivery all year.'})
        line.action_apply()
        self.assertAlmostEqual(self.review.calibrated_score, 0.85)
        self.assertAlmostEqual(self.review.final_score, 0.85)
        self.assertEqual(line.state, 'applied')

    def test_applied_line_immutable(self):
        line = self.session.line_ids
        line.action_apply()
        with self.assertRaises(ValidationError):
            line.write({'justification': 'history rewrite attempt'})

    def test_applied_line_cannot_be_deleted(self):
        """write() alone left the record deletable, and the manager ACL
        granted unlink - so the evidence of a score change could be removed
        by the role that makes score changes."""
        line = self.session.line_ids
        line.action_apply()
        with self.assertRaises(ValidationError):
            line.unlink()
        self.assertTrue(line.exists())

    def test_unapplied_line_can_still_be_removed(self):
        """A proposal that was never applied is not an audit record; the
        guard must not freeze the working state of a live session."""
        line = self.session.line_ids
        self.assertEqual(line.state, 'proposed')
        line.unlink()
        self.assertFalse(line.exists())

    def test_closed_session_blocks_apply(self):
        line = self.session.line_ids
        self.session.write({'state': 'done'})
        with self.assertRaises(ValidationError):
            line.action_apply()

    def test_unchanged_score_needs_no_justification(self):
        line = self.session.line_ids
        line.action_apply()
        self.assertAlmostEqual(self.review.calibrated_score, 0.7)
