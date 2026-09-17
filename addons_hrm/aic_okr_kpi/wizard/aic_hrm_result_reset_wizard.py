# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Ask for the reason before a confirmed figure leaves someone's score."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_MIN_REASON = 15


class AicHrmKpiResultResetWizard(models.TransientModel):
    _name = 'aic.hrm.kpi.result.reset.wizard'
    _description = 'Withdraw Confirmation of Actual Figures'

    result_ids = fields.Many2many(
        'aic.hrm.kpi.period.result', string='Figures', required=True)
    affected_summary = fields.Text(
        compute='_compute_affected_summary',
        help="Whose score changes when these confirmations are withdrawn.")
    reason = fields.Text(
        required=True,
        help="Why a figure that is already part of a score has to be taken "
             "back. Kept in the audit trail and posted on the KPI.")

    @api.depends('result_ids')
    def _compute_affected_summary(self):
        for wizard in self:
            lines = []
            for result in wizard.result_ids:
                target = result.kpi_target_id
                lines.append(_(
                    "%(kpi)s · %(owner)s · %(start)s - %(end)s · figure %(actual)s",
                    kpi=target.kpi_id.name or '',
                    owner=target.employee_id.name or _('department'),
                    start=result.date_from, end=result.date_to,
                    actual=result.actual))
            wizard.affected_summary = '\n'.join(lines)

    @api.constrains('reason')
    def _check_reason(self):
        for wizard in self:
            if len((wizard.reason or '').strip()) < _MIN_REASON:
                raise ValidationError(_(
                    "State the reason in a sentence someone can read next "
                    "quarter (at least %(count)s characters).",
                    count=_MIN_REASON))

    def action_reset(self):
        self.ensure_one()
        self._check_reason()
        self.result_ids.action_reset_to_draft(reason=self.reason.strip())
        return {'type': 'ir.actions.act_window_close'}
