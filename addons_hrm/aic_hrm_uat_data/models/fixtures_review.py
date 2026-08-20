# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Review, 360 feedback and calibration fixtures.

The two anonymity cases are the reason this file exists. Below the minimum
rater count the aggregate must not appear at all - not rounded, not greyed
out, absent - because with two raters an average is a name. At the threshold
it appears. Having both states sitting in the database side by side is the
only way a person can check the difference by looking.
"""
from odoo import api, models


class AicHrmUatFixtureReview(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def _catalog(self):
        catalog = super()._catalog()
        catalog.update({
            'review_template.active.D0': {
                'doc': "A four-stage review template (self, peers with a "
                       "minimum of three raters, manager, final) and the "
                       "form behind it.",
                'entity': 'review_template', 'state': 'active',
                'lifecycle': 'D0', 'shape': 'normal',
                'depends': [],
                'setup': '_setup_review_template',
                'outputs': ['template_id', 'form_id', 'question_rating_id',
                            'question_text_id', 'peer_stage_id'],
            },
            'review.below_threshold.D0': {
                'doc': "Three peers invited, two have answered. The peer "
                       "aggregate must stay hidden - two raters is a name, "
                       "not a statistic.",
                'entity': 'review', 'state': 'below_threshold',
                'lifecycle': 'D0', 'shape': 'sparse',
                'depends': ['org.base.D0', 'cycle.open.D-45',
                            'review_template.active.D0'],
                'setup': '_setup_review_below_threshold',
                'outputs': ['review_cycle_id', 'review_id', 'request_ids',
                            'submitted_count'],
            },
            'review.ready.D0': {
                'doc': "The same review one answer later: three of three, so "
                       "the aggregate is allowed to appear.",
                'entity': 'review', 'state': 'ready',
                'lifecycle': 'D0', 'shape': 'normal',
                'depends': ['review.below_threshold.D0'],
                'setup': '_setup_review_ready',
                'outputs': ['review_id', 'submitted_count'],
            },
            'review.external_rater.D0': {
                'doc': "An invitation to a rater with no login at all. Only "
                       "an HR administrator may record their answer; anyone "
                       "else submitting in their name is forgery that "
                       "anonymity would hide.",
                'entity': 'review', 'state': 'external_rater',
                'lifecycle': 'D0', 'shape': 'normal',
                'depends': ['review.below_threshold.D0'],
                'setup': '_setup_review_external_rater',
                'outputs': ['request_id', 'rater_employee_id'],
            },
            'calibration.applied.D0': {
                'doc': "A calibration line that has been applied: an audit "
                       "record, immutable for everyone including the "
                       "superuser, and undeletable through the UI.",
                'entity': 'calibration', 'state': 'applied', 'lifecycle': 'D0',
                'shape': 'normal',
                'depends': ['review.ready.D0'],
                'setup': '_setup_calibration_applied',
                'outputs': ['session_id', 'line_id', 'score_before',
                            'score_after'],
            },
        })
        return catalog

    # ------------------------------------------------------------------
    def _setup_review_template(self, ctx):
        form = self.env['aic.hrm.review.form'].create({
            'name': 'UAT Standard form',
            'section_ids': [(0, 0, {
                'name': 'UAT Competencies',
                'question_ids': [
                    (0, 0, {'name': 'UAT Delivers on commitments',
                            'question_type': 'rating_10'}),
                    (0, 0, {'name': 'UAT What should they keep doing?',
                            'question_type': 'text'}),
                ],
            })],
        })
        self._track([form])
        template = self.env['aic.hrm.review.template'].create({
            'name': 'UAT Annual template',
            'form_id': form.id,
            'stage_ids': [
                (0, 0, {'sequence': 1, 'name': 'UAT Self',
                        'stage_type': 'self'}),
                (0, 0, {'sequence': 2, 'name': 'UAT Peers',
                        'stage_type': 'peer_feedback', 'min_raters': 3}),
                (0, 0, {'sequence': 3, 'name': 'UAT Manager',
                        'stage_type': 'manager'}),
                (0, 0, {'sequence': 4, 'name': 'UAT Final',
                        'stage_type': 'final'}),
            ],
        })
        self._track([template])
        questions = form.section_ids.question_ids
        peer_stage = template.stage_ids.filtered(
            lambda s: s.stage_type == 'peer_feedback')
        return {
            'template_id': template.id, 'form_id': form.id,
            'question_rating_id': questions[0].id,
            'question_text_id': questions[1].id,
            'peer_stage_id': peer_stage.id,
        }

    def _answers(self, ctx, rating, text):
        template = ctx['review_template.active.D0']
        return [
            {'question_id': template['question_rating_id'], 'rating': rating},
            {'question_id': template['question_text_id'], 'text': text},
        ]

    def _setup_review_below_threshold(self, ctx):
        org = ctx['org.base.D0']
        template = ctx['review_template.active.D0']
        review_cycle = self.env['aic.hrm.review.cycle'].create({
            'name': 'UAT Annual review',
            'perf_cycle_id': ctx['cycle.open.D-45']['cycle_id'],
            'template_id': template['template_id'],
            'date_start': self._day(-14),
            'date_end': self._day(16),
            'department_ids': [(4, org['dept_product_id'])],
        })
        # Reviews are generated, not created one by one, and they cascade
        # from the cycle - so the cycle is the only thing worth tracking.
        self._track([review_cycle])
        review_cycle.action_generate_reviews()

        review = review_cycle.review_ids.filtered(
            lambda r: r.employee_id.id == org['member_employee_id'])
        Request = self.env['aic.hrm.feedback.request']
        requests = Request.create([
            {'review_id': review.id, 'rater_employee_id': peer_id,
             'rater_role': 'peer', 'deadline': self._day(10)}
            for peer_id in org['peer_employee_ids']
        ])
        # Two of three answer. The third is deliberately left open.
        peer_users = self.env['hr.employee'].browse(
            org['peer_employee_ids']).mapped('user_id')
        for request, user, rating in zip(requests[:2], peer_users[:2], (8, 6)):
            request.with_user(user).submit_feedback(
                self._answers(ctx, rating, 'UAT keep shipping'))
        return {
            'review_cycle_id': review_cycle.id,
            'review_id': review.id,
            'request_ids': requests.ids,
            'submitted_count': 2,
        }

    def _setup_review_ready(self, ctx):
        parent = ctx['review.below_threshold.D0']
        requests = self.env['aic.hrm.feedback.request'].browse(
            parent['request_ids'])
        pending = requests.filtered(lambda r: r.state == 'invited')
        for request in pending:
            request.with_user(request.rater_user_id).submit_feedback(
                self._answers(ctx, 7, 'UAT clear communication'))
        review = self.env['aic.hrm.review'].browse(parent['review_id'])
        return {'review_id': review.id,
                'submitted_count': len(requests.filtered(
                    lambda r: r.state == 'submitted'))}

    def _setup_review_external_rater(self, ctx):
        org = ctx['org.base.D0']
        parent = ctx['review.below_threshold.D0']
        request = self.env['aic.hrm.feedback.request'].create({
            'review_id': parent['review_id'],
            'rater_employee_id': org['external_rater_id'],
            'rater_role': 'external',
            'deadline': self._day(10),
        })
        self._track([request])
        return {'request_id': request.id,
                'rater_employee_id': org['external_rater_id']}

    def _setup_calibration_applied(self, ctx):
        parent = ctx['review.below_threshold.D0']
        review = self.env['aic.hrm.review'].browse(parent['review_id'])
        session = self.env['aic.hrm.calibration.session'].create({
            'name': 'UAT Calibration round',
            'review_cycle_id': parent['review_cycle_id'],
            'date': self._day(-1),
        })
        # Track the session, never the line: an applied line refuses to be
        # unlinked by anyone, but it cascades from its session in SQL.
        self._track([session])
        session.write({'state': 'in_progress'})
        line = self.env['aic.hrm.calibration.line'].create({
            'session_id': session.id,
            'review_id': review.id,
            'score_after': (review.final_score or 0.0) + 0.1,
            'justification': 'UAT: consistent delivery across two quarters.',
        })
        score_before = line.score_before
        line.action_apply()
        return {'session_id': session.id, 'line_id': line.id,
                'score_before': score_before, 'score_after': line.score_after}
