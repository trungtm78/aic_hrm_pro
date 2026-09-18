# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Give the figures that were already confirmed a first audit event.

Without this, the trail would start in the middle: a manager opening the
history of a figure confirmed before the audit trail existed would see
nothing and could not tell an untouched figure from an unrecorded change.
The baseline event says plainly that the figure was already confirmed when
the trail was switched on, and carries the last writer and date the database
still knows about.
"""
import logging

from odoo import SUPERUSER_ID, _, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Audit = env['aic.hrm.kpi.result.audit']
    results = env['aic.hrm.kpi.period.result'].search([('state', '=', 'confirmed')])
    already = set(Audit.search([('result_id', 'in', results.ids)]).mapped('result_id').ids)
    values = []
    for result in results:
        if result.id in already:
            continue
        values.append({
            'result_id': result.id,
            'kpi_target_id': result.kpi_target_id.id,
            'date_from': result.date_from,
            'date_to': result.date_to,
            'action': 'confirm',
            'old_actual': 0.0,
            'new_actual': result.actual,
            'old_state': 'draft',
            'new_state': 'confirmed',
            'source': result.source,
            # Spelled out at the call site so the string is extracted for
            # translation: a reason the customer cannot read is no reason.
            'reason': _("Baseline: this figure was already confirmed before "
                        "the audit trail was switched on. Who and when are "
                        "taken from the last write the database still knows "
                        "about."),
            'user_id': result.write_uid.id or SUPERUSER_ID,
            'event_date': result.write_date,
        })
    if values:
        Audit.create(values)
        # The figures keep the same confirmer the baseline event names.
        for result in results:
            if not result.confirmed_by:
                result.write({'confirmed_by': result.write_uid.id,
                              'confirmed_on': result.write_date})
    _logger.info('Actual figure audit: %s baseline event(s) written', len(values))
