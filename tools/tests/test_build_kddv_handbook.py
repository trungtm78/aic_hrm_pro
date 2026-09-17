# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Rendering of the Sales & Services handbook.

The handbook reads production over RPC and embeds screenshots; here only the
rendering is exercised, with a hand-made dataset and a temporary picture, so
the tests need neither network nor the customer's files.

Run:  python -m unittest discover -s tools/tests -t .
"""
import importlib.util
import pathlib
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_handbook', _REPO / 'tools' / 'build_kddv_handbook.py')
handbook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(handbook)

# Smallest valid PNG, so a figure can be embedded without a real screenshot.
PNG = bytes.fromhex('89504e470d0a1a0a0000000d494844520000000100000001080600000'
                    '01f15c4890000000a49444154789c6300010000050001'
                    '0d0a2db40000000049454e44ae426082')


def target(id_, kpi, cycle, **kw):
    row = {'id': id_, 'kpi_id': [id_, kpi], 'cycle_id': [70 + int(cycle[-2:]), f'Tháng {int(cycle[-2:])}/2026'],
           'employee_id': [5, 'Trần Ngọc Tú'], 'target_value': 21.92, 'actual_value': 38.03,
           'achievement': 1.0, 'unit': 'tỷ VNĐ', 'target_note': '≥ 21,92 tỷ', 'direction': 'higher',
           'has_actual': True, 'is_tracking': False, 'kr_id': False, 'metric_source_id': [1, 'KDDV — DT']}
    row.update(kw)
    return row


def dataset():
    targets = {
        1: target(1, 'DT Tiếp phát sóng kênh Telco/ISP', 'KDDV-2026-07'),
        2: target(2, 'Churn rate VTVgo Plus', 'KDDV-2026-07', target_value=8.0, actual_value=0.0,
                  achievement=0.0, unit='%', direction='lower', has_actual=False, target_note='≤ 8%'),
        3: target(3, 'DT FAST Channel', 'KDDV-2026-07', target_value=0.9, actual_value=0.0, achievement=0.0),
        4: target(4, 'Sản lượng nội dung', 'KDDV-2026-07', target_value=90.0, actual_value=0.0,
                  achievement=0.0, unit='%', has_actual=False),
    }
    kpi_codes = {1: 'KDDV.TP-KD.B1.2', 2: 'KDDV.CV-KD2.B2.1', 3: 'KDDV.CV-KD2.B2.3', 4: 'KDDV.BTV.B1.1',
                 5: 'KDDV.TP-KD.B1.1'}
    cards = {
        7: [
            {'id': 100, 'employee_id': [5, 'Trần Ngọc Tú'], 'job_note': 'Trưởng phòng', 'score': 0.8,
             'score_covered': 1.0, 'data_coverage': 80.0, 'total_weight': 100.0, 'line_ids': [1, 2],
             'group_ids': [1, 2], 'state': 'draft'},
            {'id': 200, 'employee_id': [6, 'Vũ Quang'], 'job_note': 'Chuyên viên KD', 'score': 0.32,
             'score_covered': 0.604, 'data_coverage': 53.0, 'total_weight': 100.0, 'line_ids': [3, 4],
             'group_ids': [3], 'state': 'draft'},
            {'id': 300, 'employee_id': [7, 'Nguyễn Ánh Kim'], 'job_note': 'Biên tập viên', 'score': 0.0,
             'score_covered': 0.0, 'data_coverage': 0.0, 'total_weight': 100.0, 'line_ids': [5],
             'group_ids': [4], 'state': 'draft'},
        ],
        8: [], 9: [],
    }
    lines = {
        100: [{'kpi_target_id': [1, 'x'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight_in_group': 20.0,
               'weight': 16.0, 'score': 1.0, 'has_actual': True},
              {'kpi_target_id': [2, 'x'], 'group_id': [7, 'B.II — KPI QUẢN TRỊ'], 'weight_in_group': 30.0,
               'weight': 6.0, 'score': 0.0, 'has_actual': False}],
        200: [{'kpi_target_id': [3, 'x'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight_in_group': 25.0,
               'weight': 20.0, 'score': 0.0, 'has_actual': True},
              {'kpi_target_id': [2, 'x'], 'group_id': [7, 'B.II — KPI QUẢN TRỊ'], 'weight_in_group': 30.0,
               'weight': 6.0, 'score': 0.0, 'has_actual': False}],
        300: [{'kpi_target_id': [4, 'x'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight_in_group': 45.0,
               'weight': 22.5, 'score': 0.0, 'has_actual': False}],
    }
    return {
        'company': {'name': 'Trung tâm', 'currency_id': [1, 'VND']},
        'staff': [{'name': 'Trần Ngọc Tú', 'job_title': 'Trưởng phòng', 'barcode': 'KDDV01',
                   'work_email': 'tu@example.com', 'parent_id': False}],
        'departments': [{'name': 'Kinh doanh và Dịch vụ'}], 'users': 22,
        'labels': {'cycle_type': {'month': 'Tháng'}, 'state': {'open': 'Đang mở'}},
        'cycles': [{'code': 'KDDV-2026-07', 'name': 'Tháng 7/2026', 'cycle_type': 'month',
                    'date_start': '2026-07-01', 'date_end': '2026-07-31', 'state': 'open',
                    'parent_id': [2, 'Quý III/2026']}],
        'objectives': [{'id': 1, 'code': 'O1', 'name': 'Doanh thu', 'weight': 50.0, 'score': 0.7,
                        'score_covered': 1.0, 'data_coverage': 70.0, 'employee_id': [5, 'TP']}],
        'krs': [{'id': 11, 'code': 'O1.KR1', 'name': 'Doanh thu quý', 'weight': 35.0, 'metric_type': 'number',
                 'target': 150.56, 'current': 209.77, 'unit': 'tỷ VNĐ', 'score': 1.0, 'has_actual': True,
                 'deadline': '2026-09-30', 'objective_id': [1, 'Doanh thu'], 'milestone_ids': [], 'note': ''},
                {'id': 12, 'code': 'O1.KR2', 'name': 'Ra mắt B2C', 'weight': 10.0, 'metric_type': 'milestone',
                 'target': 0.0, 'current': 0.0, 'unit': False, 'score': 0.0, 'has_actual': False,
                 'deadline': '2026-09-07', 'objective_id': [1, 'Doanh thu'], 'milestone_ids': [1], 'note': ''}],
        'milestones': [{'name': 'LIVE 7/9', 'kr_id': [12, 'Ra mắt B2C'], 'is_done': False}],
        'targets': targets, 'kpi_codes': kpi_codes, 'cards': cards, 'lines': lines,
        'groups': [{'assignment_id': [100, 'a'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight': 80.0},
                   {'assignment_id': [100, 'a'], 'group_id': [7, 'B.II — KPI QUẢN TRỊ'], 'weight': 20.0},
                   {'assignment_id': [200, 'b'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight': 80.0},
                   {'assignment_id': [300, 'c'], 'group_id': [6, 'B.I — KPI DOANH THU'], 'weight': 50.0}],
        'sources': [{'name': 'KDDV — DT Telco/ISP (TK 51131)', 'field_name': 'balance', 'multiplier': -1e-9},
                    {'name': 'KDDV — Chi phí', 'field_name': 'debit', 'multiplier': 1e-9}],
        'tracking': [{'kpi_id': [9, 'Chi phí hoạt động'], 'cycle_id': [77, 'Tháng 7/2026'], 'unit': 'tỷ VNĐ',
                      'actual_value': 18.446, 'has_actual': True},
                     {'kpi_id': [9, 'Chi phí hoạt động'], 'cycle_id': [78, 'Tháng 8/2026'], 'unit': 'tỷ VNĐ',
                      'actual_value': 0.0, 'has_actual': False}],
        # Two invoices, matching the two the file reader produces in source().
        'invoices': [{'ref': 'PT2026-T07-II-01', 'name': 'INV/2026/00001', 'partner_id': [1, 'FPT'],
                      'invoice_date': '2026-07-31', 'amount_untaxed': 38030000000.0, 'amount_tax': 3042400000.0},
                     {'ref': 'PT2026-T08-II-01', 'name': 'INV/2026/00002', 'partner_id': [1, 'FPT'],
                      'invoice_date': '2026-08-31', 'amount_untaxed': 21990000000.0, 'amount_tax': 1759200000.0}],
        'entries': [{'ref': 'CPTH2026-T07', 'name': 'CPTH/2026/07/0001', 'date': '2026-07-31',
                     'journal_id': [1, 'Chi phí tổng hợp'], 'amount_total': 18445937012.0}],
        'confirmed': 38,
        'stream_lines': [{'credit': 38030000000.0, 'debit': 0.0}],
        # What the ledger holds, to the dong, per month.
        'ledger_by_account': {(7, '51131'): 38030000000.0, (8, '51131'): 43990000000.0},
        'ledger_by_partner': {(7, 'FPT'): 38030000000.0, (8, 'FPT'): 43990000000.0},
        'ledger_cost': {7: 18445937012.0},
    }


def source():
    """The dataset the file reader produces (tools/extract_kddv_actuals.py)."""
    return {
        'streams': {'telco': 'Telco', 'vtvshop_mg': 'MG', 'tnnd': 'TNND', 'fast': 'FAST', 'digital': 'DV so'},
        'irregularities': [{'month': 8, 'partner': 'Apple', 'kind': 'vat', 'stream': 'tnnd',
                            'text': 'T8 Apple: VAT 9,4%'}],
        'accounting': {
            'invoices': [
                {'ref': 'PT2026-T07-II-01', 'partner': 'FPT', 'section': 'II', 'month': 7,
                 'date': '2026-07-31', 'product': 'Cap quyen tiep phat song kenh', 'untaxed': 38030000000,
                 'file_vat': 3042400000, 'file_vat_rate': 8.0, 'note': 'Phieu thu 2026, thang 7'},
                {'ref': 'PT2026-T08-II-01', 'partner': 'FPT', 'section': 'II', 'month': 8,
                 'date': '2026-08-31', 'product': 'Cap quyen tiep phat song kenh', 'untaxed': 21990000000,
                 'file_vat': 1759200000, 'file_vat_rate': 10.0, 'note': 'VAT trong file la 10,00%, khác 8%'},
            ],
            'accruals': {'8': {'ref': 'DTHU2026-T08', 'date': '2026-08-31', 'total': 22000000000,
                               'lines': [{'partner': 'FPT', 'section': 'II', 'account': '51131',
                                          'label': 'T8 chua xuat HD', 'amount': 22000000000}]}},
            'cost_entries': {'7': {'ref': 'CPTH2026-T07', 'date': '2026-07-31', 'total': 18445937012,
                                   'lines': [{'account': '62752', 'label': 'Chi san xuat CT',
                                              'amount': 18445937012}]}},
            'cost_accounts': [{'code': '62752', 'name': 'Chi san xuat CT'}],
        },
    }


class FigureCase(unittest.TestCase):

    def test_missing_picture_is_flagged_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as folder:
            rendered = handbook.figure(pathlib.Path(folder), '01-scorecard-list', 1)
        self.assertIn('Thiếu ảnh minh hoạ', rendered)
        self.assertNotIn('<img', rendered)

    def test_picture_is_embedded_in_the_page(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder)
            (path / '01-scorecard-list.png').write_bytes(PNG)
            rendered = handbook.figure(path, '01-scorecard-list', 3)
        self.assertIn('data:image/png;base64,', rendered)
        self.assertIn('Hình 3.', rendered)


class ScorecardCase(unittest.TestCase):

    def setUp(self):
        self.data = dataset()

    def test_a_line_shows_how_its_weight_is_made(self):
        rows = handbook.line_rows(self.data, self.data['cards'][7][0])
        self.assertIn('20% × 80% = 16,00%', rows[0][3])

    def test_a_line_without_figures_says_so_instead_of_showing_zero(self):
        rows = handbook.line_rows(self.data, self.data['cards'][7][0])
        self.assertIn('chưa có số liệu', rows[1][4])
        self.assertIn('>—<', rows[1][5])

    def test_full_coverage_is_explained_as_measured_part_complete(self):
        note = handbook.example_explanation(self.data, self.data['cards'][7][0])
        self.assertIn('đạt trọn vẹn', note)
        self.assertIn('20% trọng số còn lại', note)

    def test_partial_score_names_the_weakest_measured_line(self):
        note = handbook.example_explanation(self.data, self.data['cards'][7][1])
        self.assertIn('DT FAST Channel', note)
        self.assertIn('47% trọng số chưa có số liệu', note)

    def test_no_figures_at_all_is_not_a_bad_result(self):
        note = handbook.example_explanation(self.data, self.data['cards'][7][2])
        self.assertIn('không phải là kết quả kém', note)


class MappingCase(unittest.TestCase):
    """The section the customer uses to audit the mapping."""

    def setUp(self):
        self.data, self.source = dataset(), source()

    def test_all_five_source_files_are_listed(self):
        rows = handbook.source_files_rows(self.data, self.source)
        names = ' '.join(row[0] for row in rows)
        for file_name in ['TT Nhân viên', 'Giao nhiệm vụ OKR', 'Giao_KPI_Thang',
                          'Template_PhieuThu', 'chi_phi_2026']:
            self.assertIn(file_name, names, file_name)

    def test_each_file_has_a_column_map_including_what_is_left_out(self):
        tables = handbook.column_map_tables(self.data, self.source)
        self.assertEqual(len(tables), 5)
        for name, rows in tables:
            self.assertTrue(rows, name)
            self.assertTrue(all(len(row) == 4 for row in rows), name)
        left_out = [row for _name, rows in tables for row in rows
                    if row[1].startswith('(không')]
        self.assertTrue(left_out, 'the page must say which columns are deliberately unused')

    def test_target_rules_match_what_the_reader_really_does(self):
        rows = handbook.target_rule_rows()
        self.assertEqual(len(rows), 7)
        by_text = {row[0]: row for row in rows}
        self.assertEqual(by_text['≤ 8%'][1:3], ['8,00', 'càng thấp càng tốt'])
        self.assertEqual(by_text['0'][2], 'càng thấp càng tốt')
        self.assertEqual(by_text['Đàm phán LOI'][2], 'đạt / không đạt')
        self.assertIn('không tạo dòng', by_text['—'][1])

    def test_a_match_is_green_and_a_mismatch_is_flagged(self):
        self.assertIn('class="ok"', handbook.diff_cell(100.0, 100.0))
        flagged = handbook.diff_cell(100.0, 90.0)
        self.assertIn('class="bad"', flagged)
        self.assertIn('10', flagged)

    def test_revenue_is_reconciled_to_the_dong_per_stream(self):
        rows = handbook.stream_reconciliation_rows(self.data, self.source)
        self.assertTrue(rows)
        self.assertTrue(all('class="ok"' in row[-1] for row in rows),
                        'the fixture ledger equals the fixture files')
        broken = dict(self.data, ledger_by_account={(7, '51131'): 1.0})
        self.assertTrue(any('class="bad"' in row[-1]
                            for row in handbook.stream_reconciliation_rows(broken, self.source)))

    def test_revenue_is_reconciled_per_partner_and_month(self):
        rows = handbook.partner_reconciliation_rows(self.data, self.source)
        august = [row for row in rows if 'Tháng 8/2026' in row[0]][0]
        self.assertIn('21.990.000.000', august[2], 'invoiced part of August')
        self.assertIn('22.000.000.000', august[3], 'accrued part of August')
        self.assertTrue(all('class="ok"' in row[-1] for row in rows))

    def test_cost_is_reconciled_per_month(self):
        rows = handbook.cost_reconciliation_rows(self.data, self.source)
        self.assertEqual(len(rows), 1)
        self.assertIn('18.445.937.012', rows[0][2])
        self.assertIn('class="ok"', rows[0][-1])

    def test_counts_are_reconciled_and_a_gap_is_flagged(self):
        rows = handbook.count_reconciliation_rows(self.data, self.source)
        self.assertTrue(all(len(row) == 4 for row in rows))
        self.assertTrue(any('hoá đơn' in row[0] for row in rows))
        # The fixture holds one objective while the decision has four, so the
        # row must show the gap instead of hiding it.
        objectives = [row for row in rows if 'Mục tiêu' in row[0]][0]
        self.assertIn('class="bad"', objectives[-1])

    def test_assumptions_say_why_what_it_affects_and_how_to_fix(self):
        rows = handbook.assumption_rows(self.data, self.source)
        self.assertGreaterEqual(len(rows), 8)
        self.assertTrue(all(len(row) == 4 and all(row) for row in rows))
        self.assertTrue(any('8%' in row[0] for row in rows))

    def test_irregularities_are_listed_with_their_kind_in_words(self):
        rows = handbook.irregularity_rows(self.source)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 'VAT không đúng 8%')


class PageCase(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        images = pathlib.Path(self.folder.name)
        for name in handbook.FIGURES:
            (images / f'{name}.png').write_bytes(PNG)
        self.page = handbook.render(dataset(), source(), images, '18/09/2026 01:30')

    def tearDown(self):
        self.folder.cleanup()

    def test_self_contained_vietnamese_page(self):
        self.assertTrue(self.page.startswith('<!DOCTYPE html>'))
        self.assertIn('<html lang="vi">', self.page)
        self.assertIn('width=device-width', self.page)
        self.assertNotIn('<script', self.page)
        # Each figure embeds its picture twice: once shown, once as the link
        # that opens it full size.
        self.assertEqual(self.page.count('<figure>'), len(handbook.FIGURES))
        self.assertEqual(self.page.count('data:image/png;base64,'), 2 * len(handbook.FIGURES))
        self.assertIn('bấm vào ảnh để xem cỡ đầy đủ', self.page)

    def test_every_section_has_a_heading_the_contents_can_reach(self):
        for key, title in handbook.SECTIONS:
            self.assertIn(f'href="#{key}"', self.page)
            self.assertIn(f'id="{key}"', self.page)
            self.assertIn(title, self.page)

    def test_the_trail_carries_the_figure_from_file_to_score(self):
        for expected in ['38,03 tỷ', 'PT2026-T07-II-01', '51131', 'KDDV.TP-KD.B1.2', '209,77']:
            self.assertIn(expected, self.page, expected)

    def test_no_technical_names_leak_into_the_page(self):
        for forbidden in ['aic.hrm', 'account.move', 'miền lọc', 'search_read']:
            self.assertNotIn(forbidden, self.page, forbidden)

    def test_the_mapping_section_lets_the_reader_audit_the_load(self):
        self.assertIn('Ánh xạ dữ liệu', self.page)
        self.assertIn('Chênh lệch (đồng)', self.page)
        self.assertIn('cần đơn vị xác nhận', self.page)
        self.assertIn('không tự sửa', self.page)

    def test_money_reconciliations_are_exact_for_a_correct_load(self):
        for builder in (handbook.stream_reconciliation_rows, handbook.partner_reconciliation_rows,
                        handbook.cost_reconciliation_rows):
            rows = builder(dataset(), source())
            self.assertTrue(rows, builder.__name__)
            self.assertTrue(all('class="ok"' in row[-1] for row in rows), builder.__name__)

    def test_monthly_duties_and_scoring_are_both_explained(self):
        self.assertIn('Lấy số thực tế từ nguồn', self.page)
        self.assertIn('Xác nhận', self.page)
        self.assertIn('Yêu cầu điều chỉnh chỉ tiêu', self.page)
        self.assertIn('Độ phủ dữ liệu', self.page)
