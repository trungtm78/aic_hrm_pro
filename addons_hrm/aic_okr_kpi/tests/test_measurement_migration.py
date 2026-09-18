# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The upgrade that re-reads stored scores after "not measured" stopped being red.

A changed compute does not touch rows already in the database. On the
customer's production three objectives with no figures at all kept the red
they were stored with, so the fix only reached new records. The migration
marks the fields for recomputation; this test keeps its list honest - a
renamed field, or one that stops being a stored compute, must not turn the
upgrade into a silent no-op.
"""
from odoo.tests import tagged

from odoo.addons.aic_okr_kpi import upgrade_utils

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestMeasurementMigration(KpiCase):

    def test_every_field_it_recomputes_is_a_stored_compute(self):
        for model_name, names in upgrade_utils.MEASUREMENT_FIELDS:
            model = self.env[model_name]
            for name in names:
                field = model._fields.get(name)
                self.assertIsNotNone(
                    field, f'{model_name}.{name} no longer exists: the upgrade '
                           f'would silently skip it')
                self.assertTrue(field.store and field.compute,
                                f'{model_name}.{name} is no longer a stored '
                                f'compute, so it needs no recomputation - drop '
                                f'it from the migration instead of leaving it')

    def test_it_repairs_a_row_left_red_with_nothing_measured(self):
        objective = self._make_objective(name='Chưa đo', weight=50.0)
        self._make_kr(objective, baseline=10, target=100, current=0, weight=100.0,
                      progress_reported_on=False)
        self.assertEqual(objective.rag, 'none')
        # An upgraded database: the row still carries the old verdict. Flush
        # first, or the pending write lands on top of the raw UPDATE.
        self.env.flush_all()
        self.env.cr.execute("UPDATE aic_hrm_objective SET rag = 'red' WHERE id = %s",
                            (objective.id,))
        objective.invalidate_recordset()
        self.assertEqual(objective.rag, 'red')

        upgrade_utils.recompute_measurement(self.env)

        objective.invalidate_recordset()
        self.assertEqual(objective.rag, 'none',
                         'the upgrade must re-read what was stored before it')
