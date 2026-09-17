# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The reading of the Sales & Services actual revenue and cost workbooks.

Formatting cases run everywhere. The dataset cases need the customer's files,
which are never committed, and skip without them. Their expected figures were
summed by hand from the workbooks on 2026-09-17, not taken from the script.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('extract_kddv_actuals', _REPO / 'tools' / 'extract_kddv_actuals.py')
extract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(extract)

SOURCE = _REPO / 'Docs' / 'OKR'
HAVE_FILES = (SOURCE / extract.REVENUE_FILE).exists() and (SOURCE / extract.COST_FILE).exists()


class FormatCase(unittest.TestCase):

    def test_vietnamese_number_style(self):
        self.assertEqual(extract.fmt(1234.5), '1.234,50')
        self.assertEqual(extract.fmt(0.2), '0,20')
        self.assertEqual(extract.fmt(-0.177), '-0,18')

    def test_every_section_maps_to_a_known_stream(self):
        self.assertTrue(set(extract.SECTION_STREAM.values()) <= set(extract.STREAMS))

    def test_revenue_kpis_only_use_known_streams(self):
        for keys in extract.KPI_STREAMS.values():
            self.assertTrue(set(keys) <= set(extract.STREAMS))


@unittest.skipUnless(HAVE_FILES, 'customer workbooks not present')
class DatasetCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = extract.build(SOURCE)

    def stream(self, month, key):
        return self.data['revenue'][str(month)]['streams'][key]['total']

    def test_register_rows_agree_with_their_year_total(self):
        self.assertEqual(self.data['register_check'], [])

    def test_only_july_and_august_have_revenue(self):
        self.assertEqual(self.data['months_with_revenue'], [7, 8])
        self.assertFalse(self.data['revenue']['9']['has_data'])

    def test_july_streams(self):
        self.assertAlmostEqual(self.stream(7, 'telco'), 38.03, places=2)
        self.assertAlmostEqual(self.stream(7, 'vtvshop_mg'), 62.50, places=2)
        self.assertAlmostEqual(self.stream(7, 'tnnd'), 7.71, places=2)
        self.assertAlmostEqual(self.stream(7, 'fast'), 0.0, places=6)
        self.assertAlmostEqual(self.stream(7, 'digital'), 0.0, places=6)
        self.assertAlmostEqual(self.data['revenue']['7']['total'], 108.24, places=2)

    def test_august_counts_invoiced_and_not_yet_invoiced(self):
        telco = self.data['revenue']['8']['streams']['telco']
        self.assertAlmostEqual(telco['invoiced'], 14.29, places=2)
        self.assertAlmostEqual(telco['uninvoiced'], 29.70, places=2)
        self.assertAlmostEqual(self.stream(8, 'vtvshop_mg'), 41.67, places=2)
        self.assertAlmostEqual(self.stream(8, 'tnnd'), 13.37, places=2)
        self.assertAlmostEqual(self.stream(8, 'fast'), 2.50, places=2)
        self.assertAlmostEqual(self.data['revenue']['8']['total'], 101.53, places=2)

    def test_costs_exist_up_to_july(self):
        self.assertEqual(self.data['months_with_cost'], [1, 2, 3, 4, 5, 6, 7])
        self.assertAlmostEqual(self.data['cost']['7']['total'], 18.446, places=3)

    def test_kpi_actuals_cover_revenue_lines_for_months_with_data(self):
        actuals = {(a['month'], a['code']): a for a in self.data['kpi_actuals']}
        self.assertEqual(len(actuals), 2 * len(extract.KPI_STREAMS))
        self.assertAlmostEqual(actuals[(7, 'KDDV.TP-KD.B1.1')]['value'], 108.24, places=2)
        self.assertAlmostEqual(actuals[(8, 'KDDV.TP-KD.B1.4')]['value'], 15.87, places=2)
        self.assertNotIn((9, 'KDDV.TP-KD.B1.1'), actuals)
        self.assertIn('HĐ', actuals[(8, 'KDDV.CV-KD1.B1.1')]['note'])

    def test_revenue_key_result_is_the_quarter_to_date(self):
        [checkin] = self.data['kr_checkins']
        self.assertEqual(checkin['code'], 'O1.KR1')
        self.assertAlmostEqual(checkin['value'], 209.77, places=2)

    def test_tracking_only_where_both_numbers_exist(self):
        tracking = {(t['key'], t['month']): t['value'] for t in self.data['tracking']}
        self.assertAlmostEqual(tracking[('cost', 7)], 18.446, places=3)
        self.assertAlmostEqual(tracking[('gross_profit', 7)], 89.79, places=2)
        self.assertAlmostEqual(tracking[('margin', 7)], 82.96, places=2)
        self.assertIsNone(tracking[('cost', 8)])
        self.assertIsNone(tracking[('gross_profit', 8)])

    def test_irregularities_are_reported(self):
        texts = ' || '.join(issue['text'] for issue in self.data['irregularities'])
        kinds = {issue['kind'] for issue in self.data['irregularities']}
        self.assertEqual(kinds, {'negative', 'vat', 'both', 'lump'})
        self.assertIn('MobiFone', texts)
        self.assertIn('Tâm Anh', texts)
        self.assertIn('FPT', texts)


@unittest.skipUnless(HAVE_FILES, 'customer workbooks not present')
class AccountingCase(unittest.TestCase):
    """Documents that carry the two workbooks into Odoo accounting."""

    @classmethod
    def setUpClass(cls):
        cls.books = extract.build(SOURCE)['accounting']

    def test_one_posted_invoice_per_invoiced_cell(self):
        invoices = self.books['invoices']
        self.assertEqual(len(invoices), 96)
        self.assertEqual(len({invoice['ref'] for invoice in invoices}), 96)
        self.assertEqual(len(self.books['partners']), 21)
        july = sum(invoice['untaxed'] for invoice in invoices if invoice['month'] == 7)
        self.assertAlmostEqual(july / 1e9, 108.24, places=2)

    def test_invoices_whose_file_vat_is_not_8_percent_say_so(self):
        flagged = [invoice for invoice in self.books['invoices'] if 'khác 8%' in invoice['note']]
        self.assertTrue(flagged)
        self.assertTrue(all(abs(invoice['file_vat_rate'] - 8.0) > 0.5 for invoice in flagged))

    def test_not_invoiced_revenue_is_one_accrual_in_august(self):
        self.assertEqual(list(self.books['accruals']), ['8'])
        august = self.books['accruals']['8']
        self.assertEqual(len(august['lines']), 24)
        self.assertAlmostEqual(august['total'] / 1e9, 77.00, places=2)
        self.assertTrue(any(line['amount'] < 0 for line in august['lines']))

    def test_cost_entries_match_the_ledger_groups(self):
        self.assertEqual(self.books['ledger_check'], [])
        entries = self.books['cost_entries']
        self.assertEqual(list(entries), [str(m) for m in range(1, 8)])
        self.assertEqual(sum(len(entry['lines']) for entry in entries.values()), 167)
        self.assertEqual(entries['7']['total'], 18445937012)
        self.assertEqual(len(self.books['cost_accounts']), 36)

    def test_every_product_books_to_its_stream_account(self):
        accounts = {item['code'] for item in self.books['stream_accounts'].values()}
        self.assertEqual(len(self.books['products']), 7)
        self.assertTrue(all(product['account'] in accounts for product in self.books['products']))
