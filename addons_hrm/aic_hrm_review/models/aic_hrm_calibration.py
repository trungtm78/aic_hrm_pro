# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class AicHrmCalibrationSession(models.Model):
    _name = 'aic.hrm.calibration.session'
    _description = 'Calibration Session'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    review_cycle_id = fields.Many2one(
        'aic.hrm.review.cycle', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        related='review_cycle_id.company_id', store=True, index=True)
    facilitator_id = fields.Many2one(
        'res.users', default=lambda self: self.env.user)
    date = fields.Date(default=fields.Date.context_today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], default='draft', required=True, tracking=True, copy=False)
    line_ids = fields.One2many('aic.hrm.calibration.line', 'session_id')


class AicHrmCalibrationLine(models.Model):
    """One review inside a calibration session. Every score move carries a
    mandatory written justification — the audit answer to 'why did this
    rating change in a closed-door meeting?'."""
    _name = 'aic.hrm.calibration.line'
    _description = 'Calibration Line'

    session_id = fields.Many2one(
        'aic.hrm.calibration.session', required=True, index=True,
        ondelete='cascade')
    company_id = fields.Many2one(
        related='session_id.company_id', store=True)
    review_id = fields.Many2one(
        'aic.hrm.review', required=True, ondelete='cascade')
    score_before = fields.Float(readonly=True)
    score_after = fields.Float()
    justification = fields.Text()
    state = fields.Selection([
        ('proposed', 'Proposed'),
        ('applied', 'Applied'),
    ], default='proposed', required=True)

    _session_review_uniq = models.Constraint(
        'unique (session_id, review_id)',
        'This review is already on the session.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        # Snapshot BEFORE super(): the justification constraint compares
        # against score_before at flush time.
        Review = self.env['aic.hrm.review']
        for vals in vals_list:
            if vals.get('review_id') and 'score_before' not in vals:
                review = Review.browse(vals['review_id'])
                vals['score_before'] = review.final_score
                if 'score_after' not in vals:
                    vals['score_after'] = review.final_score
        return super().create(vals_list)

    @api.constrains('score_after', 'justification')
    def _check_justification(self):
        for line in self:
            changed = float_compare(
                line.score_after, line.score_before,
                precision_digits=4) != 0
            if changed and not (line.justification
                                and line.justification.strip()):
                raise ValidationError(_(
                    "Changing a score in calibration requires a written "
                    "justification."))

    def action_apply(self):
        for line in self:
            line.review_id.write({'calibrated_score': line.score_after})
            if line.justification:
                line.review_id.message_post(body=_(
                    "Calibration adjusted the final score from %(before)s "
                    "to %(after)s: %(why)s",
                    before=line.score_before, after=line.score_after,
                    why=line.justification))
            line.write({'state': 'applied'})
