# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError


class AicHrmFeedbackRequest(models.Model):
    """360 feedback invitation.

    Anonymity by construction (CX#4): no chatter, the rater field is
    admin-only at field level, responses are written by the system user so
    ``create_uid`` never identifies the rater, and aggregates surface only
    once the stage's minimum rater count is reached. The app-level guarantee
    is documented honestly: a database administrator can always read raw
    rows.
    """
    _name = 'aic.hrm.feedback.request'
    _description = 'Feedback Request'

    review_id = fields.Many2one(
        'aic.hrm.review', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='review_id.company_id', store=True, index=True)
    rater_employee_id = fields.Many2one(
        'hr.employee', required=True,
        groups='aic_hrm_base.group_hrm_admin',
        help="Visible to HR administrators only.")
    rater_user_id = fields.Many2one(
        'res.users', compute='_compute_rater_user', store=True, index=True,
        groups='aic_hrm_base.group_hrm_admin')
    rater_role = fields.Selection([
        ('peer', 'Peer'),
        ('upward', 'Direct report'),
        ('manager', 'Manager'),
        ('external', 'External'),
    ], default='peer', required=True)
    deadline = fields.Date()
    state = fields.Selection([
        ('invited', 'Invited'),
        ('submitted', 'Submitted'),
        ('declined', 'Declined'),
    ], default='invited', required=True)
    response_ids = fields.One2many(
        'aic.hrm.feedback.response', 'request_id',
        groups='aic_hrm_base.group_hrm_admin')

    _review_rater_uniq = models.Constraint(
        'unique (review_id, rater_employee_id)',
        'This person was already invited to this review.',
    )

    @api.depends('rater_employee_id')
    def _compute_rater_user(self):
        for request in self:
            request.rater_user_id = request.rater_employee_id.user_id

    @api.constrains('review_id', 'rater_employee_id')
    def _check_not_self(self):
        for request in self.sudo():
            if request.rater_employee_id == request.review_id.employee_id:
                raise ValidationError(_(
                    "People do not rate themselves through 360 feedback; "
                    "self-assessment has its own stage."))

    def submit_feedback(self, answers):
        """Record answers and mark submitted.

        ``answers``: list of {'question_id':, 'rating':, 'text':}. Runs for
        the CALLING rater; responses are created through sudo so no
        create_uid trail points back at them.
        """
        self.ensure_one()
        request = self.sudo()
        # Authorise before the escalation is used for anything. The old
        # guard read `if request.rater_user_id and ...`, so a rater with no
        # login - every 'external' rater, and every employee the import
        # wizard creates - fell straight through it and any caller could
        # submit in their name. Anonymity then hid the forger as well as it
        # hides an honest rater.
        if not self.env.su:
            if request.rater_user_id:
                if request.rater_user_id != self.env.user:
                    raise UserError(_("Only the invited rater may submit "
                                      "this feedback."))
            elif not self.env.user.has_group(
                    'aic_hrm_base.group_hrm_admin'):
                # A rater without an account answers on paper or by mail;
                # the HR administrator who invited them transcribes it.
                # Nobody else gets to speak for them.
                raise UserError(_(
                    "This rater has no login of their own. Only an HR "
                    "administrator may record their answers."))
        if request.state != 'invited':
            raise UserError(_("This feedback was already submitted."))
        valid_questions = request.review_id.review_cycle_id.template_id \
            .form_id.section_ids.question_ids
        for answer in answers:
            question = valid_questions.filtered(
                lambda q: q.id == answer['question_id'])
            if not question:
                raise ValidationError(_(
                    "An answer references a question outside this "
                    "review's form."))
            rating = answer.get('rating', 0)
            if rating and not 1 <= rating <= question._rating_scale():
                raise ValidationError(_(
                    "Rating out of range for question %(name)s.",
                    name=question.name))
        # with_user(SUPERUSER_ID), not sudo(): sudo keeps the caller's uid
        # in create_uid/write_uid, which would identify the rater forever.
        system = self.with_user(SUPERUSER_ID)
        system.env['aic.hrm.feedback.response'].create([
            {
                'request_id': request.id,
                'question_id': answer['question_id'],
                'rating': answer.get('rating', 0),
                'text': answer.get('text', False),
            }
            for answer in answers
        ])
        system.write({'state': 'submitted'})
        return True


class AicHrmFeedbackResponse(models.Model):
    """Raw anonymous answers. Read path: HR admin only; everyone else sees
    aggregates through the review's computed fields."""
    _name = 'aic.hrm.feedback.response'
    _description = 'Feedback Response'

    request_id = fields.Many2one(
        'aic.hrm.feedback.request', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='request_id.company_id', store=True)
    question_id = fields.Many2one(
        'aic.hrm.review.question', required=True, ondelete='restrict')
    rating = fields.Integer()
    text = fields.Text()
