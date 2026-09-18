# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Re-band every scorecard on its score over the KPIs that have figures.

The band used to follow the full score, where a KPI still waiting for its
figure counts as 0: on the customer's July a card at 100% on everything
reported showed amber and one at 57% showed red. The stored band does not
change by itself when its formula does.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.aic_okr_kpi import upgrade_utils


def migrate(cr, version):
    upgrade_utils.recompute_measurement(api.Environment(cr, SUPERUSER_ID, {}))
