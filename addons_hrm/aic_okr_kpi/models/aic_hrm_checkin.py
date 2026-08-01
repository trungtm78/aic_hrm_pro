# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AicHrmCheckin(models.Model):
    """One cadence heartbeat on a key result or a KPI target.

    Check-ins are the anti-set-and-forget backbone: value, confidence and
    blocker note per beat. A KR check-in writes the current value through;
    a KPI check-in materializes a DRAFT period result (a manager confirms it
    before it counts toward the score).
    """
    _name = 'aic.hrm.checkin'
    _description = 'Check-in'
    _order = 'date desc, id desc'

    kr_id = fields.Many2one(
        'aic.hrm.key.result', index=True, ondelete='cascade')
    kpi_target_id = fields.Many2one(
        'aic.hrm.kpi.target', index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', compute='_compute_company', store=True, index=True)
    date = fields.Date(
        default=fields.Date.context_today, required=True)
    value_current = fields.Float(required=True)
    progress_snapshot = fields.Float(
        readonly=True, help="Normalized progress right after this check-in.")
    rag_snapshot = fields.Selection([
        ('green', 'Green'), ('amber', 'Amber'), ('red', 'Red'),
        ('none', 'Not scored'),
    ], readonly=True)
    confidence = fields.Integer(
        required=True, default=5,
        help="1 = will miss badly, 10 = will certainly hit.")
    blocker = fields.Text()
    note = fields.Text()
    author_id = fields.Many2one(
        'hr.employee', default=lambda self: self.env.user.employee_id,
        readonly=True)

    @api.depends('kr_id.company_id', 'kpi_target_id.company_id')
    def _compute_company(self):
        for checkin in self:
            checkin.company_id = (checkin.kr_id.company_id
                                  or checkin.kpi_target_id.company_id)

    @api.constrains('kr_id', 'kpi_target_id')
    def _check_exactly_one_parent(self):
        for checkin in self:
            if bool(checkin.kr_id) == bool(checkin.kpi_target_id):
                raise ValidationError(_(
                    "A check-in belongs to exactly one key result or one "
                    "KPI target."))

    @api.constrains('confidence')
    def _check_confidence(self):
        for checkin in self:
            if not 1 <= checkin.confidence <= 10:
                raise ValidationError(_(
                    "Confidence is a 1..10 scale."))

    def _apply_to_kr(self):
        for checkin in self.filtered('kr_id'):
            kr = checkin.kr_id
            kr.write({'current': checkin.value_current})
            kr.write({
                'last_checkin_date': checkin.date,
                'confidence': checkin.confidence,
            })
            checkin.write({
                'progress_snapshot': kr.progress,
                'rag_snapshot': kr.rag,
            })

    def _apply_to_kpi(self):
        PeriodResult = self.env['aic.hrm.kpi.period.result']
        for checkin in self.filtered('kpi_target_id'):
            target = checkin.kpi_target_id
            month_start = checkin.date.replace(day=1)
            existing = PeriodResult.search([
                ('kpi_target_id', '=', target.id),
                ('date_from', '=', month_start),
            ], limit=1)
            if existing:
                if existing.state == 'draft':
                    existing.write({'actual': checkin.value_current,
                                    'source': 'checkin'})
            else:
                month_end = (month_start + relativedelta(months=1)
                             - relativedelta(days=1))
                PeriodResult.create({
                    'kpi_target_id': target.id,
                    'date_from': month_start,
                    'date_to': month_end,
                    'actual': checkin.value_current,
                    'source': 'checkin',
                    'state': 'draft',
                })
            checkin.write({
                'progress_snapshot': target.achievement,
                'rag_snapshot': target.rag,
            })

    @api.model_create_multi
    def create(self, vals_list):
        # Constraints only fire when their fields appear in vals; a payload
        # with NEITHER parent must still be rejected explicitly.
        for vals in vals_list:
            if bool(vals.get('kr_id')) == bool(vals.get('kpi_target_id')):
                raise ValidationError(_(
                    "A check-in belongs to exactly one key result or one "
                    "KPI target."))
        checkins = super().create(vals_list)
        checkins.kr_id.cycle_id.ensure_editable()
        checkins.kpi_target_id.cycle_id.ensure_editable()
        checkins._apply_to_kr()
        checkins._apply_to_kpi()
        return checkins
