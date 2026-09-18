# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Re-read the stored scores now that "not measured" is no longer "off track".

`rag`, `has_actual`, `data_coverage` and `score_covered` are stored computed
fields. Their formulas changed - an objective nobody has measured must read
"not scored" instead of red - but a changed formula does not touch rows that
are already in the database. Without this pass an upgraded customer keeps
looking at the old verdict: on the customer's own production objectives with
no figures at all still showed red, which reads as a department in trouble
when it means nobody has reported yet.
"""
from odoo import SUPERUSER_ID, api

from odoo.addons.aic_okr_kpi import upgrade_utils


def migrate(cr, version):
    upgrade_utils.recompute_measurement(api.Environment(cr, SUPERUSER_ID, {}))
