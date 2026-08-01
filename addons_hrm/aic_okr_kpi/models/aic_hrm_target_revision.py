# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class AicHrmTargetRevision(models.Model):
    _inherit = 'aic.hrm.target.revision'

    @api.model
    def _get_revisable_fields(self):
        revisable = super()._get_revisable_fields()
        revisable.update({
            'aic.hrm.objective': {'weight'},
            'aic.hrm.key.result': {'target', 'baseline', 'weight'},
            'aic.hrm.kpi.target': {'target_value', 'baseline_value',
                                   'weight'},
        })
        return revisable
