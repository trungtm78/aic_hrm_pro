# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Append-only trail of every change to an actual figure.

A performance score is an argument about a person's year, and the figures it
rests on must be defensible months later: who entered this number, who
confirmed it, who took the confirmation back and why. Chatter cannot carry
that at enterprise volume (one message per row per change), so the events go
into their own table that nobody - not a manager, not an administrator, not
the superuser - can rewrite or delete.

Each event also stores a checksum over its own payload, so tampering at the
database level, below the ORM, does not go unnoticed.
"""
import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

_CHECKSUM_FIELDS = ('result_id', 'kpi_target_id', 'action', 'old_actual',
                    'new_actual', 'old_state', 'new_state', 'reason',
                    'user_id', 'event_date')


class AicHrmKpiResultAudit(models.Model):
    _name = 'aic.hrm.kpi.result.audit'
    _description = 'Actual Figure Audit Event'
    _order = 'event_date desc, id desc'
    _rec_name = 'display_label'

    result_id = fields.Many2one(
        'aic.hrm.kpi.period.result', string='Period Result', index=True,
        ondelete='set null', readonly=True,
        help="The period result this event happened to. Kept as a reference "
             "only: deleting the result never deletes its history.")
    kpi_target_id = fields.Many2one(
        'aic.hrm.kpi.target', required=True, index=True, ondelete='restrict',
        readonly=True)
    employee_id = fields.Many2one(
        related='kpi_target_id.employee_id', store=True, index=True, readonly=True)
    cycle_id = fields.Many2one(
        related='kpi_target_id.cycle_id', store=True, index=True, readonly=True)
    company_id = fields.Many2one(
        related='kpi_target_id.company_id', store=True, index=True, readonly=True)
    display_label = fields.Char(compute='_compute_display_label')
    date_from = fields.Date(readonly=True)
    date_to = fields.Date(readonly=True)
    action = fields.Selection([
        ('create', 'Figure entered'),
        ('edit', 'Figure changed'),
        ('confirm', 'Confirmed'),
        ('reset', 'Confirmation withdrawn'),
        ('delete', 'Figure deleted'),
    ], required=True, readonly=True)
    old_actual = fields.Float(readonly=True)
    new_actual = fields.Float(readonly=True)
    old_state = fields.Char(readonly=True)
    new_state = fields.Char(readonly=True)
    source = fields.Char(
        readonly=True, help="Where the figure came from: manual entry, import, "
                            "metric source or check-in.")
    reason = fields.Text(
        readonly=True,
        help="Required when a confirmed figure is withdrawn - the score changes "
             "with it.")
    user_id = fields.Many2one(
        'res.users', string='Done by', required=True, index=True, readonly=True,
        default=lambda self: self.env.user)
    event_date = fields.Datetime(
        required=True, readonly=True, index=True, default=fields.Datetime.now)
    same_user = fields.Boolean(
        readonly=True,
        help="The confirmation was withdrawn by the very person who confirmed "
             "it. Allowed, but recorded: four eyes are better than two.")
    evidence_checksum = fields.Char(readonly=True, size=64)

    @api.depends('kpi_target_id', 'action', 'event_date')
    def _compute_display_label(self):
        labels = dict(self._fields['action'].selection)
        for event in self:
            event.display_label = '%s · %s' % (
                labels.get(event.action, event.action or ''),
                event.kpi_target_id.display_label or '')

    def _checksum(self, values):
        payload = '|'.join(str(values.get(name, '')) for name in _CHECKSUM_FIELDS)
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('user_id', self.env.uid)
            vals.setdefault('event_date', fields.Datetime.now())
            vals['evidence_checksum'] = self._checksum(vals)
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_(
            "The audit trail of actual figures cannot be changed. It is what "
            "makes a score defensible."))

    def unlink(self):
        raise AccessError(_(
            "The audit trail of actual figures cannot be deleted."))

    @api.model
    def record_event(self, result, action, reason=False, old=None, same_user=None):
        """Write one event for `result`; `old` holds the values before a change.

        Called by the period result itself, with elevated rights: a user who
        may enter a figure must not need write access to its history, and a
        user who may not must still leave a trace.
        """
        old = old or {}
        target = result.kpi_target_id
        values = {
            'result_id': result.id,
            'kpi_target_id': target.id,
            'date_from': result.date_from,
            'date_to': result.date_to,
            'action': action,
            'old_actual': old.get('actual', result.actual if action == 'delete' else 0.0),
            'new_actual': 0.0 if action == 'delete' else result.actual,
            'old_state': old.get('state', result.state if action == 'delete' else False),
            'new_state': False if action == 'delete' else result.state,
            'source': result.source,
            'reason': reason,
            'same_user': bool(same_user if same_user is not None else (
                action == 'reset' and result.confirmed_by
                and result.confirmed_by.id == self.env.uid)),
        }
        return self.sudo().create(values)
