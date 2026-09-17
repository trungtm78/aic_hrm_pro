# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Figures and formatting of the Sales & Services evaluation report.

The report reads production over RPC; only the parts that shape numbers into
rows are tested here, with a hand-made dataset, so the tests need no network.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_evaluation', _REPO / 'tools' / 'build_kddv_evaluation.py')
report = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(report)

STREAMS = {'telco': 'Telco', 'vtvshop_mg': 'MG', 'tnnd': 'TNND', 'fast': 'FAST', 'digital': 'DV số'}


def month(values, has_data=True):
    return {'has_data': has_data, 'total': round(sum(values.values()), 6),
            'streams': {key: {'total': value, 'invoiced': value, 'uninvoiced': 0.0, 'partners': []}
                        for key, value in values.items()}}


ACTUALS = {
    'streams': STREAMS,
    'revenue': {
        '7': month({'telco': 38.03, 'vtvshop_mg': 62.50, 'tnnd': 7.71, 'fast': 0.0, 'digital': 0.0}),
        '8': month({'telco': 43.99, 'vtvshop_mg': 41.67, 'tnnd': 13.37, 'fast': 2.50, 'digital': 0.0}),
        '9': month({'telco': 0.0, 'vtvshop_mg': 0.0, 'tnnd': 0.0, 'fast': 0.0, 'digital': 0.0}, has_data=False),
    },
}


class FormatCase(unittest.TestCase):

    def test_vietnamese_numbers(self):
        self.assertEqual(report.vn(1234.5), '1.234,50')
        self.assertEqual(report.vn(82.9567, 1), '83,0')
        self.assertEqual(report.vn(None), '')


class RevenueRowsCase(unittest.TestCase):

    def setUp(self):
        self.rows = {row[0]: row for row in report.revenue_rows(ACTUALS)}

    def test_one_row_per_stream_plus_a_total(self):
        self.assertEqual(set(self.rows), set(STREAMS.values()) | {'TỔNG'})

    def test_plan_and_actual_side_by_side(self):
        telco = self.rows['Telco']
        self.assertEqual(telco[1:5], ['21,92', '38,03', '22,64', '43,99'])

    def test_september_actual_stays_empty_until_the_month_has_figures(self):
        self.assertEqual(self.rows['Telco'][6], '')
        self.assertEqual(self.rows['TỔNG'][6], '')

    def test_quarter_to_date_and_share_of_plan(self):
        total = self.rows['TỔNG']
        self.assertEqual(total[7:10], ['150,51', '209,77', '139,4'])
        self.assertEqual(self.rows['FAST'][8:10], ['2,50', '91,6'])

    def test_a_stream_without_a_quarter_plan_shows_no_share(self):
        rows = report.revenue_rows(ACTUALS)
        digital = [row for row in rows if row[0] == 'DV số'][0]
        self.assertEqual(digital[9], vn_share := report.vn(100.0 * 0.0 / 0.20, 1))
        self.assertEqual(vn_share, '0,0')


class SheetLayoutCase(unittest.TestCase):

    def test_every_sheet_has_a_header(self):
        for title, header, _builder in report.SHEETS:
            self.assertTrue(title and header, title)
            self.assertTrue(all(header), title)
