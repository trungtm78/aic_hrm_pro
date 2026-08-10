# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Sentinel for idempotent demo data installation."""
from odoo import fields, models


class AicHrmMatchDemoSentinel(models.Model):
    _name = 'aic.hrm.match.demo.sentinel'
    _description = 'Demo Installation Marker'

    name = fields.Char('Description', default='Demo Data')
    generated = fields.Boolean('Generated', default=False,
        help='Flag to track if demo data has already been generated. '
             'post_init_hook checks this to avoid re-running.')
