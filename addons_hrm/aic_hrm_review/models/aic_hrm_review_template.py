# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AicHrmReviewTemplate(models.Model):
    """Configurable review route map (the SuccessFactors-style template)."""
    _name = 'aic.hrm.review.template'
    _description = 'Review Template'

    name = fields.Char(required=True)
    form_id = fields.Many2one('aic.hrm.review.form', required=True)
    stage_ids = fields.One2many('aic.hrm.review.stage', 'template_id')
    company_id = fields.Many2one('res.company')
    active = fields.Boolean(default=True)

    @api.constrains('stage_ids')
    def _check_stages(self):
        for template in self:
            if template.stage_ids and not any(
                    stage.stage_type == 'final'
                    for stage in template.stage_ids):
                raise ValidationError(_(
                    "A review template needs a final stage."))


class AicHrmReviewStage(models.Model):
    _name = 'aic.hrm.review.stage'
    _description = 'Review Stage'
    _order = 'template_id, sequence, id'

    template_id = fields.Many2one(
        'aic.hrm.review.template', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    stage_type = fields.Selection([
        ('self', 'Self-assessment'),
        ('peer_feedback', 'Peer feedback'),
        ('upward_feedback', 'Upward feedback'),
        ('manager', 'Manager assessment'),
        ('calibration', 'Calibration'),
        ('final', 'Final'),
    ], required=True)
    duration_days = fields.Integer(default=7)
    min_raters = fields.Integer(
        default=3,
        help="Anonymous aggregates only appear once this many raters have "
             "submitted.")


class AicHrmReviewForm(models.Model):
    _name = 'aic.hrm.review.form'
    _description = 'Review Form'

    name = fields.Char(required=True)
    section_ids = fields.One2many('aic.hrm.review.section', 'form_id')
    company_id = fields.Many2one('res.company')
    active = fields.Boolean(default=True)


class AicHrmReviewSection(models.Model):
    _name = 'aic.hrm.review.section'
    _description = 'Review Form Section'
    _order = 'form_id, sequence, id'

    form_id = fields.Many2one(
        'aic.hrm.review.form', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    question_ids = fields.One2many('aic.hrm.review.question', 'section_id')


class AicHrmReviewQuestion(models.Model):
    _name = 'aic.hrm.review.question'
    _description = 'Review Question'
    _order = 'section_id, sequence, id'

    section_id = fields.Many2one(
        'aic.hrm.review.section', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    question_type = fields.Selection([
        ('rating_5', 'Rating 1-5'),
        ('rating_10', 'Rating 1-10'),
        ('text', 'Free text'),
        ('boolean', 'Yes / No'),
    ], default='rating_10', required=True)
    is_required = fields.Boolean(default=True)
    competency = fields.Char(
        help="Optional competency label this question maps to.")

    def _rating_scale(self):
        self.ensure_one()
        return 5.0 if self.question_type == 'rating_5' else 10.0
