# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""When a key result counts as reported - recorded, never guessed.

The cockpit once inferred "reported" from the value itself: a current value
away from the baseline meant somebody had reported. A rolled-over key result
starts with current 0 under a baseline of 10, so it read as reported, scored
0 and turned red - on the customer's production the MAU objective showed as
off track while nobody had entered a single figure for it.

A report is an event: a check-in, a completed milestone, or a person writing
the current value. The moment is stamped on the key result, and an upgraded
database recovers it from the value's tracked history.
"""
from odoo.tests import tagged

from odoo.addons.aic_okr_kpi import upgrade_utils

from .test_kpi_engine import KpiCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestProgressReporting(KpiCase):

    def setUp(self):
        super().setUp()
        self.objective = self._make_objective(name='MAU', weight=20.0)

    def _untouched(self):
        # The customer's shape: a baseline of 10, nothing entered yet.
        return self._make_kr(self.objective, baseline=10.0, target=15.0,
                             current=0.0, progress_reported_on=False)

    def test_an_untouched_value_below_its_baseline_is_not_a_report(self):
        kr = self._untouched()
        self.assertFalse(kr.progress_reported_on)
        self.assertFalse(kr.has_actual)
        self.assertEqual(kr.rag, 'none', 'nothing entered means not scored, not red')
        self.assertEqual(self.objective.rag, 'none')
        self.assertAlmostEqual(self.objective.data_coverage, 0.0)

    def test_writing_the_current_value_is_a_report(self):
        kr = self._untouched()
        kr.write({'current': 12.0})
        self.assertTrue(kr.progress_reported_on)
        self.assertTrue(kr.has_actual)
        self.assertNotEqual(kr.rag, 'none')

    def test_writing_zero_on_purpose_is_a_report_too(self):
        """A real zero is a figure; only the untouched default is not."""
        kr = self._make_kr(self.objective, baseline=10.0, target=15.0,
                           current=3.0, progress_reported_on=False)
        kr.write({'current': 0.0})
        self.assertTrue(kr.has_actual)
        self.assertEqual(kr.rag, 'red', 'a reported 0 against 10 -> 15 is off track')

    def test_saving_the_same_value_again_is_not_a_report(self):
        kr = self._untouched()
        kr.write({'current': 0.0})
        self.assertFalse(kr.progress_reported_on)
        self.assertFalse(kr.has_actual)

    def test_creating_with_progress_is_a_report(self):
        kr = self._make_kr(self.objective, baseline=0.0, target=100.0, current=40.0)
        self.assertTrue(kr.progress_reported_on)
        self.assertTrue(kr.has_actual)

    def test_creating_at_the_baseline_is_not_a_report(self):
        kr = self._make_kr(self.objective, baseline=10.0, target=15.0, current=10.0)
        self.assertFalse(kr.progress_reported_on)
        self.assertFalse(kr.has_actual)

    def test_a_check_in_is_a_report(self):
        kr = self._untouched()
        self.env['aic.hrm.checkin'].create({'kr_id': kr.id, 'value_current': 11.0})
        self.assertTrue(kr.progress_reported_on)
        self.assertTrue(kr.has_actual)

    def test_a_rolled_over_copy_starts_unreported(self):
        kr = self._make_kr(self.objective, baseline=10.0, target=15.0, current=14.0)
        self.assertTrue(kr.has_actual)
        copy = kr.copy({'current': 0.0, 'last_checkin_date': False})
        self.assertFalse(copy.progress_reported_on,
                         'a copy starts a new period: nothing reported in it yet')
        self.assertFalse(copy.has_actual)

    def test_the_upgrade_recovers_reports_from_the_tracked_history(self):
        reported = self._untouched()
        untouched = self._untouched()
        # Odoo does not track changes on a record created in the same
        # transaction; in real use the value is entered on a later save.
        self.env.flush_all()
        self.env.cr.precommit.run()
        reported.with_context(tracking_disable=False, mail_notrack=False).write(
            {'current': 12.0})
        self.env.flush_all()
        self.env.cr.precommit.run()  # tracking values are written at commit
        # An upgraded database: the stamp did not exist when the value was written.
        self.env.cr.execute(
            "UPDATE aic_hrm_key_result SET progress_reported_on = NULL, "
            "has_actual = FALSE, rag = 'red' WHERE id IN %s",
            (tuple((reported | untouched).ids),))
        self.env.invalidate_all()

        upgrade_utils.backfill_progress_reported(self.env)
        upgrade_utils.recompute_measurement(self.env)

        self.env.invalidate_all()
        self.assertTrue(reported.progress_reported_on)
        self.assertTrue(reported.has_actual)
        self.assertFalse(untouched.progress_reported_on)
        self.assertFalse(untouched.has_actual)
        self.assertEqual(untouched.rag, 'none')
