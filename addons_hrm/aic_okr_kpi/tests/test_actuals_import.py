# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
import base64

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import OkrCase


@tagged('post_install', '-at_install', 'aic_okr_kpi')
class TestActualsImport(OkrCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kpi = cls.env['aic.hrm.kpi'].create({
            'name': 'Units processed', 'code': 'ACT-UNITS',
            'unit': 'count', 'direction': 'higher', 'aggregation': 'sum',
            'default_target': 1000.0,
        })
        cls.target = cls.env['aic.hrm.kpi.target'].create({
            'kpi_id': cls.kpi.id,
            'cycle_id': cls.year.id,
            'employee_id': cls.member_employee.id,
            'target_value': 1000.0,
        })
        objective = cls._make_objective()
        cls.kr = cls._make_kr(objective, code='ACT-KR-1')

    def _wizard(self, csv_text, filename='actuals.csv'):
        return self.env['aic.hrm.actuals.import.wizard'].create({
            'cycle_id': self.year.id,
            'file': base64.b64encode(csv_text.encode('utf-8')),
            'filename': filename,
        })

    def test_import_creates_period_result_with_import_source(self):
        wizard = self._wizard(
            'type,code,employee,date_from,date_to,value,note\n'
            'kpi,ACT-UNITS,Nam Member,2026-01-01,2026-01-31,120,'
            'from warehouse system\n')
        wizard.action_preview()
        self.assertIn('1 KPI period value', wizard.preview)
        wizard.action_import()
        self.assertEqual(wizard.imported_period_count, 1)
        period = self.target.period_result_ids
        self.assertEqual(len(period), 1)
        self.assertEqual(period.actual, 120.0)
        self.assertEqual(period.source, 'import')
        self.assertEqual(period.state, 'draft',
                         'imported values wait for manager confirmation')

    def test_import_never_overwrites_manual_entry(self):
        manual = self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': self.target.id,
            'date_from': '2026-01-01', 'date_to': '2026-01-31',
            'actual': 555.0, 'source': 'manual',
        })
        wizard = self._wizard(
            'code,employee,date_from,value\n'
            'ACT-UNITS,Nam Member,2026-01-01,120\n')
        wizard.action_import()
        self.assertEqual(manual.actual, 555.0, 'manual always wins')
        self.assertEqual(wizard.imported_period_count, 0)
        self.assertIn('manual wins', wizard.warning_log)

    def test_import_never_touches_confirmed_period(self):
        confirmed = self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': self.target.id,
            'date_from': '2026-02-01', 'date_to': '2026-02-28',
            'actual': 200.0, 'source': 'auto', 'state': 'confirmed',
        })
        wizard = self._wizard(
            'code,employee,date_from,value\n'
            'ACT-UNITS,Nam Member,2026-02-01,999\n')
        wizard.action_import()
        self.assertEqual(confirmed.actual, 200.0)
        self.assertIn('confirmed', wizard.warning_log)

    def test_import_updates_auto_draft_row(self):
        auto = self.env['aic.hrm.kpi.period.result'].create({
            'kpi_target_id': self.target.id,
            'date_from': '2026-03-01', 'date_to': '2026-03-31',
            'actual': 10.0, 'source': 'auto',
        })
        wizard = self._wizard(
            'code,employee,date_from,value\n'
            'ACT-UNITS,Nam Member,2026-03-01,42\n')
        wizard.action_import()
        self.assertEqual(auto.actual, 42.0)
        self.assertEqual(auto.source, 'import')

    def test_kr_row_lands_as_checkin(self):
        wizard = self._wizard(
            'type,code,date_from,value\n'
            'kr,ACT-KR-1,2026-05-10,37\n')
        wizard.action_import()
        self.assertEqual(wizard.imported_checkin_count, 1)
        self.assertEqual(self.kr.current, 37.0,
                         'check-in write-through moved the KR current')

    def test_semicolon_csv_and_decimal_comma(self):
        wizard = self._wizard(
            'code;employee;date_from;value\n'
            'ACT-UNITS;Nam Member;2026-04-01;12,5\n')
        wizard.action_import()
        self.assertEqual(self.target.period_result_ids.filtered(
            lambda period: str(period.date_from) == '2026-04-01').actual,
            12.5)

    def test_unknown_code_warns_not_crashes(self):
        wizard = self._wizard(
            'code,date_from,value\n'
            'NO-SUCH-KPI,2026-01-01,1\n')
        wizard.action_import()
        self.assertEqual(wizard.imported_period_count, 0)
        self.assertIn('NO-SUCH-KPI', wizard.warning_log)

    def test_missing_required_columns_is_a_user_error(self):
        wizard = self._wizard('foo,bar\n1,2\n')
        with self.assertRaises(UserError):
            wizard.action_preview()
