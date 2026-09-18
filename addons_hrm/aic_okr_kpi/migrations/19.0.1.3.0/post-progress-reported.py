# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Stamp when progress was reported, from the evidence already on record.

"Reported" used to be inferred from the value: a current value away from the
baseline counted as a report. A rolled-over key result sits at 0 under a
baseline of 10 and so read as reported, scored 0 and showed red although
nobody had entered anything. A report is now a recorded moment; this script
recovers it for key results written before the moment was kept, then
re-reads every score that depends on it.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.aic_okr_kpi import upgrade_utils


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    upgrade_utils.backfill_progress_reported(env)
    upgrade_utils.recompute_measurement(env)
