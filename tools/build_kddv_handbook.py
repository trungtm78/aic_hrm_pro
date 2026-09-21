# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Write the Sales & Services handbook: their own data, and what to do monthly.

The first attempt at this page was a wall of counts and technical words, and
the customer said so. This one follows the figure instead: a number from their
own spreadsheet, into the invoices, into the KPI, into the score - with three
scorecards read line by line, screenshots of their own screens, the two things
they have to do every month (enter the month's figures, then confirm them),
and how the score is worked out.

Everything is read over JSON-RPC (queries only) from the live instance, and
the pictures come from `uat/capture_kddv_guide.mjs`. The page names real
people and real revenue: it is written to Docs/OKR, which is git-ignored.

Run:  set OKR_ADMIN_PASSWORD=... && python tools/build_kddv_handbook.py
"""
import argparse
import base64
import datetime
import html
import json
import importlib.util
import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    """Load a sibling tool as a module (they are scripts, not a package)."""
    spec = importlib.util.spec_from_file_location(name, _REPO / 'tools' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_evaluation = _load('build_kddv_evaluation')
Client, vn = _evaluation.Client, _evaluation.vn
# The mapping tables come from the readers that actually load the customer's
# files, so the handbook cannot describe a mapping the code no longer uses.
_plan = _load('extract_kddv')
_actuals = _load('extract_kddv_actuals')

DEFAULT_OUT = _REPO / 'Docs' / 'OKR' / 'Cam_nang_OKR_KPI_KDDV_Q3_2026.html'
DEFAULT_SOURCE_DATA = _REPO / 'uat' / 'data' / 'kddv_actuals_q3_2026.json'
DEFAULT_IMAGES = _REPO / 'Docs' / 'OKR' / 'img_kddv'
OLD_PAGE = _REPO / 'Docs' / 'OKR' / 'Mo_ta_du_lieu_OKR_KDDV.html'
DEPARTMENT = 'Kinh doanh và Dịch vụ'
MONTHS = {7: 'KDDV-2026-07', 8: 'KDDV-2026-08', 9: 'KDDV-2026-09'}
SCORED = (7, 8)
MONTH_LENGTH = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
VI = {'lang': 'vi_VN'}

# The three scorecards read line by line: a full one, a partly measured one,
# and one that has no figures at all - the case people misread as a zero.
EXAMPLES = [
    ('Trần Ngọc Tú', 7, 'Trưởng phòng — có số liệu cho cả nhóm doanh thu'),
    ('Vũ Quang', 7, 'Chuyên viên kinh doanh — mới có một phần số liệu'),
    ('Nguyễn Ánh Kim', 7, 'Biên tập viên — chưa có số liệu nào'),
]

FIGURES = {
    '01-scorecard-list': 'Danh sách phiếu giao KPI: mỗi người một phiếu cho mỗi tháng.',
    '02-scorecard-form': 'Một phiếu giao KPI: trọng số, điểm, điểm trên phần có số liệu và độ phủ dữ liệu nằm ngay đầu phiếu.',
    '03-kpi-target-form': 'Một chỉ tiêu KPI: chỉ tiêu tháng, số thực hiện và nguồn lấy số; nút “Lấy số thực tế từ nguồn” ở thanh trên.',
    '04-kpi-target-periods': 'Tab “Kết quả theo kỳ” của chỉ tiêu: số của từng tháng và trạng thái Nháp / Đã xác nhận.',
    '05-period-results': 'Màn hình “Kết quả theo kỳ”: chọn các dòng của tháng rồi bấm “Xác nhận” — chỉ số đã xác nhận mới được tính điểm.',
    '06-objective-form': 'Mục tiêu O1 và các kết quả then chốt kèm điểm, độ phủ dữ liệu.',
    '07-checkins': 'Check-in: dùng để cập nhật tiến độ cho kết quả then chốt (nhất là loại theo mốc công việc).',
    '08-invoice-list': 'Hoá đơn bán hàng tháng 7 đã vào sổ, tìm theo tham chiếu PT2026-T07.',
    '09-invoice-form': 'Một hoá đơn: đối tác, ngày, sản phẩm theo mảng doanh thu, tiền chưa VAT và thuế 8%.',
    '10-cost-entry': 'Bút toán chi phí tháng 7: mỗi dòng một tài khoản của sổ kế toán, đối ứng tài khoản trung gian 3388.',
    '11-metric-sources': 'Danh sách nguồn lấy số: cách hệ thống tự cộng số từ sổ kế toán vào KPI.',
    '12-department-report': 'Báo cáo bảng điểm phòng ban: điểm KPI, điểm trên phần có số liệu, độ phủ và điểm OKR của quý.',
    '13-audit-trail': 'Vết kiểm toán số thực hiện: mỗi lần nhập, xác nhận, sửa hay huỷ xác nhận đều có người và thời điểm; không ai sửa hay xoá được danh sách này.',
    '14-review-cycle': 'Chu kỳ đánh giá Quý III/2026 của phòng, với mẫu phiếu theo Quy chế 01 và danh sách phiếu đánh giá.',
    '15-review-form': 'Một phiếu đánh giá quý: điểm KPI hiện tại, điểm KPI đã chốt (kèm người và thời điểm chốt), phần tự đánh giá và phần quản lý đánh giá.',
}

SECTIONS = [
    ('A', 'Số liệu của đơn vị đi vào hệ thống như thế nào'),
    ('B', 'Ánh xạ dữ liệu: tệp của đơn vị nằm ở đâu trong hệ thống'),
    ('C', 'Hệ thống đang có những gì (kèm số thật)'),
    ('D', 'Đọc kỹ ba phiếu giao KPI'),
    ('E', 'Việc phải làm hằng tháng với dữ liệu hiện tại'),
    ('F', 'Đánh giá hiệu suất được tính thế nào'),
    ('G', 'Kết quả đánh giá được ghi ở đâu và làm sao biết là đúng'),
    ('H', 'Việc cần đơn vị cung cấp thêm'),
    ('I', 'Phụ lục: toàn bộ dữ liệu đang có'),
]

# The reconciliation compares whole dong, which is what both the files and
# the ledger hold, so a correct load differs by exactly nothing.
DIFFERENCE_TOLERANCE = 0.0


def esc(value):
    return html.escape('' if value is None else str(value))


class Raw(str):
    """A cell already rendered as HTML."""


def cell(value, kind=''):
    return Raw(f'<td class="{kind}">{esc(value)}</td>')


def table(headers, rows, note=''):
    head = ''.join(f'<th>{esc(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(
        c if isinstance(c, Raw) else f'<td>{esc(c)}</td>' for c in row) + '</tr>' for row in rows)
    caption = f'<p class="note">{esc(note)}</p>' if note else ''
    return (f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>{caption}')


def figure(images, name, number):
    """An embedded screenshot, or a visible note when the picture is missing."""
    path = images / f'{name}.png'
    caption = FIGURES[name]
    if not path.exists():
        return (f'<p class="missing">[Thiếu ảnh minh hoạ {esc(name)} — chạy '
                f'<code>node uat/capture_kddv_guide.mjs</code> rồi tạo lại tài liệu.]</p>')
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    source = f'data:image/png;base64,{encoded}'
    # On a phone the shrunken screenshot is unreadable; opening it in its own
    # tab shows it at full size, and needs no script.
    return (f'<figure><a href="{source}" target="_blank" rel="noopener">'
            f'<img alt="{esc(caption)}" src="{source}"></a>'
            f'<figcaption>Hình {number}. {esc(caption)} '
            f'<span class="muted">(bấm vào ảnh để xem cỡ đầy đủ)</span></figcaption></figure>')


def read_with_optional(client, model, domain, fields, optional, **kwargs):
    """Read `fields`, plus `optional` when the instance is new enough to have
    them.

    The documents are built against whatever version the customer is running,
    which is not always the newest one: a field added this week must not stop
    a report being produced today.
    """
    try:
        return client.search_read(model, domain, fields + optional, **kwargs)
    except SystemExit as refused:
        if not any(name in str(refused) for name in optional):
            raise
        return client.search_read(model, domain, fields, **kwargs)


def collect(client):
    data = {}
    [data['company']] = client.call('res.company', 'read', [[1]],
                                    {'fields': ['name', 'currency_id'], 'context': VI})
    data['staff'] = client.search_read(
        'hr.employee', [('department_id.name', '=', DEPARTMENT)],
        ['name', 'job_title', 'barcode', 'work_email', 'parent_id'], order='name', context=VI)
    data['departments'] = client.search_read('hr.department', [], ['name'], context=VI)
    data['users'] = client.call('res.users', 'search_count', [[('share', '=', False)]])
    labels = client.call('aic.hrm.cycle', 'fields_get', [['cycle_type', 'state']],
                         {'attributes': ['selection'], 'context': VI})
    data['labels'] = {field: dict(value['selection']) for field, value in labels.items()}
    data['cycles'] = client.search_read(
        'aic.hrm.cycle', [], ['code', 'name', 'cycle_type', 'date_start', 'date_end', 'state', 'parent_id'],
        order='date_start, cycle_type', context=VI)
    data['objectives'] = client.search_read(
        'aic.hrm.objective', [('level', '=', 'department')],
        ['code', 'name', 'weight', 'score', 'score_covered', 'data_coverage', 'employee_id'],
        order='code', context=VI)
    data['krs'] = client.search_read(
        'aic.hrm.key.result', [],
        ['code', 'name', 'weight', 'metric_type', 'target', 'current', 'unit', 'score', 'has_actual',
         'deadline', 'objective_id', 'milestone_ids', 'note'], order='code', context=VI)
    data['milestones'] = client.search_read(
        'aic.hrm.kr.milestone', [], ['name', 'kr_id', 'is_done'], context=VI)
    data['targets'] = {row['id']: row for row in client.search_read(
        'aic.hrm.kpi.target', [], ['kpi_id', 'cycle_id', 'employee_id', 'target_value', 'actual_value',
                                   'achievement', 'unit', 'target_note', 'direction', 'has_actual',
                                   'is_tracking', 'kr_id', 'metric_source_id'], context=VI)}
    data['kpi_codes'] = {row['id']: row['code'] for row in client.search_read(
        'aic.hrm.kpi', [], ['code'], context=VI)}
    data['cards'] = {}
    data['lines'] = {}
    for month, code in MONTHS.items():
        cards = client.search_read(
            'aic.hrm.kpi.assignment', [('cycle_id.code', '=', code)],
            ['employee_id', 'job_note', 'score', 'score_covered', 'data_coverage',
             'total_weight', 'line_ids', 'group_ids', 'state', 'rag'],
            order='employee_id', context=VI)
        data['cards'][month] = cards
        for card in cards:
            data['lines'][card['id']] = client.search_read(
                'aic.hrm.kpi.assignment.line', [('assignment_id', '=', card['id'])],
                ['kpi_target_id', 'group_id', 'weight_in_group', 'weight', 'score', 'has_actual'],
                order='group_id, id', context=VI)
    data['groups'] = client.search_read(
        'aic.hrm.kpi.assignment.group', [], ['assignment_id', 'group_id', 'weight'], context=VI)
    data['sources'] = client.search_read(
        'aic.hrm.metric.source', [('name', 'like', 'KDDV')], ['name', 'field_name', 'multiplier'],
        order='name', context=VI)
    data['tracking'] = client.search_read(
        'aic.hrm.kpi.target', [('is_tracking', '=', True)],
        ['kpi_id', 'cycle_id', 'unit', 'actual_value', 'has_actual'], context=VI)
    data['invoices'] = client.search_read(
        'account.move', [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
        ['ref', 'name', 'partner_id', 'invoice_date', 'amount_untaxed', 'amount_tax'],
        order='invoice_date, ref', context=VI)
    data['entries'] = client.search_read(
        'account.move', [('move_type', '=', 'entry'), ('state', '=', 'posted')],
        ['ref', 'name', 'date', 'journal_id', 'amount_total'], order='ref', context=VI)
    data['confirmed'] = client.call('aic.hrm.kpi.period.result', 'search_count', [[('state', '=', 'confirmed')]])
    data['audit_events'] = client.call('aic.hrm.kpi.result.audit', 'search_count', [[]])
    data['audit_sample'] = client.search_read(
        'aic.hrm.kpi.result.audit', [], ['event_date', 'kpi_target_id', 'action', 'old_actual',
                                         'new_actual', 'user_id', 'reason'],
        limit=8, order='event_date desc, id desc', context=VI)
    data['audit_labels'] = dict(client.call(
        'aic.hrm.kpi.result.audit', 'fields_get', [['action']],
        {'attributes': ['selection'], 'context': VI})['action']['selection'])
    data['unstamped'] = client.call('aic.hrm.kpi.period.result', 'search_count',
                                    [[('state', '=', 'confirmed'), ('confirmed_by', '=', False)]])
    data['review_cycles'] = client.search_read(
        'aic.hrm.review.cycle', [], ['name', 'state', 'perf_cycle_id', 'date_start', 'date_end',
                                     'review_ids', 'template_id'], context=VI)
    data['reviews'] = client.search_read(
        'aic.hrm.review', [], ['employee_id', 'stage_id', 'goal_score', 'goal_score_live',
                               'goal_coverage_live', 'goal_score_snapshot_on', 'goal_score_snapshot_by',
                               'self_score', 'manager_score', 'final_score'],
        order='employee_id', context=VI)
    data['review_sections'] = client.search_read(
        'aic.hrm.review.section', [], ['name', 'form_id', 'question_ids'], context=VI)
    data['review_stages'] = client.search_read(
        'aic.hrm.review.stage', [], ['name', 'stage_type', 'sequence', 'duration_days'],
        order='sequence', context=VI)
    data['department_report'] = read_with_optional(
        client, 'aic.hrm.department.scorecard', [],
        ['cycle_id', 'employee_count', 'avg_composite', 'avg_score_covered',
         'avg_data_coverage', 'avg_objective_score', 'objective_cycle_id'],
        ['measured_employee_count'], context=VI)
    data['ledger_by_account'] = {}
    data['ledger_by_partner'] = {}
    # Every month of the year: the register holds revenue from January, and the
    # reconciliation must cover all of it, not only the scored quarter.
    for month in range(1, 13):
        first = f'2026-{month:02d}-01'
        last = f'2026-{month:02d}-{MONTH_LENGTH[month]:02d}'
        period = [('parent_state', '=', 'posted'), ('date', '>=', first), ('date', '<=', last)]
        for row in client.call('account.move.line', 'read_group',
                               [period + [('account_id.code', '=like', '5113%')],
                                ['account_id', 'credit:sum', 'debit:sum'], ['account_id']],
                               {'lazy': False, 'context': VI}):
            code = row['account_id'][1].split(' ')[0]
            data['ledger_by_account'][(month, code)] = row['credit'] - row['debit']
        for row in client.call('account.move.line', 'read_group',
                               [period + [('account_id.code', '=like', '5113%')],
                                ['partner_id', 'credit:sum', 'debit:sum'], ['partner_id']],
                               {'lazy': False, 'context': VI}):
            partner = row['partner_id'][1] if row['partner_id'] else '(không đối tác)'
            data['ledger_by_partner'][(month, partner)] = row['credit'] - row['debit']
        [cost] = client.call('account.move.line', 'read_group',
                             [period + [('journal_id.code', '=', _actuals.COST_JOURNAL[0]), ('debit', '>', 0)],
                              ['debit:sum'], []], {'lazy': False, 'context': VI})
        data.setdefault('ledger_cost', {})[month] = cost['debit'] or 0.0
    data['stream_lines'] = client.call(
        'account.move.line', 'read_group',
        [[('parent_state', '=', 'posted'), ('account_id.code', '=like', '51131%'),
          ('date', '>=', '2026-07-01'), ('date', '<=', '2026-07-31')],
         ['credit:sum', 'debit:sum'], []], {'lazy': False, 'context': VI})
    return data


def line_rows(data, card):
    """Every KPI line of one scorecard, the way the person reads it."""
    rows = []
    group_weight = {group['group_id'][1]: group['weight'] for group in data['groups']
                    if group['assignment_id'][0] == card['id']}
    for line in data['lines'][card['id']]:
        target = data['targets'][line['kpi_target_id'][0]]
        code = data['kpi_codes'].get(target['kpi_id'][0], '')
        group = line['group_id'][1] if line['group_id'] else '—'
        measured = line['has_actual']
        rows.append([
            cell(group), cell(f"{code} · {target['kpi_id'][1]}"),
            cell(target['target_note'] or vn(target['target_value'])),
            cell(f"{vn(line['weight_in_group'], 0)}% × {vn(group_weight.get(group, 0), 0)}%"
                 f" = {vn(line['weight'], 2)}%"),
            cell(f"{vn(target['actual_value'])} {target['unit'] or ''}".strip() if measured
                 else 'chưa có số liệu', '' if measured else 'muted'),
            cell(f"{vn(100 * line['score'], 1)}%" if measured else '—'),
        ])
    return rows


def card_of(data, name, month):
    for card in data['cards'][month]:
        if card['employee_id'][1] == name:
            return card
    raise SystemExit(f'No scorecard for {name} in month {month}')


def money(value):
    return f'{vn(value, 0)} đồng'


def render(data, source, images, generated):
    """The page, top to bottom."""
    figure_number = [0]

    def picture(name):
        figure_number[0] += 1
        return figure(images, name, figure_number[0])

    invoices_by_month = {}
    for move in data['invoices']:
        key = move['invoice_date'][:7]
        entry = invoices_by_month.setdefault(key, {'count': 0, 'untaxed': 0.0, 'tax': 0.0})
        entry['count'] += 1
        entry['untaxed'] += move['amount_untaxed']
        entry['tax'] += move['amount_tax']
    telco_july = data['stream_lines'][0]['credit'] - data['stream_lines'][0]['debit']
    telco_invoices = [move for move in data['invoices'] if move['ref'].startswith('PT2026-T07-II-')]
    tp_target = next(target for target in data['targets'].values()
                     if data['kpi_codes'].get(target['kpi_id'][0]) == 'KDDV.TP-KD.B1.2'
                     and target['cycle_id'][1] == 'Tháng 7/2026')
    kr1 = next(kr for kr in data['krs'] if kr['code'] == 'O1.KR1')
    lines_total = sum(len(lines) for lines in data['lines'].values())
    lines_measured = sum(1 for lines in data['lines'].values() for line in lines if line['has_actual'])
    quarter = sum(target['actual_value'] for target in data['targets'].values()
                  if data['kpi_codes'].get(target['kpi_id'][0]) == 'KDDV.TP-KD.B1.1' and target['has_actual'])

    toc = ''.join(f'<li><a href="#{key}">{key}. {esc(title)}</a></li>' for key, title in SECTIONS)

    parts = [f"""<!DOCTYPE html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cẩm nang OKR/KPI Phòng Kinh doanh và Dịch vụ — Quý III/2026</title>
<style>{STYLE}</style></head><body><main>
<h1>Dữ liệu thật của Phòng {esc(DEPARTMENT)} trong hệ thống</h1>
<p class="lead">{esc(data['company']['name'])} · Quý III/2026 · <code>https://okr.aipower.vn</code><br>
<small>Tài liệu này được máy đọc trực tiếp từ hệ thống lúc {esc(generated)}. Mọi con số bên dưới là số đang
chạy thật trong hệ thống, không phải ví dụ minh hoạ.</small></p>

<div class="cards">
  <div class="kpi"><b>{len(data['objectives'])} / {len(data['krs'])}</b><span>Mục tiêu / Kết quả then chốt</span></div>
  <div class="kpi"><b>{sum(len(c) for c in data['cards'].values())}</b><span>Phiếu giao KPI (mỗi người mỗi tháng)</span></div>
  <div class="kpi"><b>{lines_total}</b><span>Dòng KPI được giao</span></div>
  <div class="kpi"><b>{len(data['invoices'])}</b><span>Hoá đơn doanh thu đã vào sổ</span></div>
  <div class="kpi"><b>{data['confirmed']}</b><span>Số thực hiện đã xác nhận</span></div>
  <div class="kpi"><b>{vn(quarter)} tỷ</b><span>Doanh thu quý III đã ghi nhận</span></div>
</div>

<nav class="toc"><b>Nội dung</b><ol>{toc}</ol></nav>

<h2 id="A">A. Số liệu của đơn vị đi vào hệ thống như thế nào</h2>
<p>Hệ thống không nhập lại số bằng tay vào KPI. Số đi theo bốn bước sau, và bước nào cũng xem được:</p>
<div class="flow">
  <div><b>1. Tệp của đơn vị</b><span>Phiếu thu 2026 · Chi phí 2026 · Quyết định giao OKR · Phiếu giao KPI</span></div>
  <div><b>2. Chứng từ kế toán</b><span>Hoá đơn bán hàng · Bút toán dự thu · Bút toán chi phí</span></div>
  <div><b>3. Chỉ tiêu KPI &amp; OKR</b><span>Hệ thống tự cộng số từ sổ kế toán vào từng chỉ tiêu</span></div>
  <div><b>4. Điểm hiệu suất</b><span>Điểm từng dòng → điểm phiếu → điểm mục tiêu của phòng</span></div>
</div>

<h3>Theo dấu một con số thật: doanh thu Telco/ISP tháng 7</h3>
<table class="trail"><tbody>
<tr><th>Trong tệp của đơn vị</th><td>Phiếu thu 2026, mục II “Doanh thu cấp quyền tiếp phát sóng các kênh”,
tháng 7: cộng các đối tác được <b>{vn(telco_july / 1e9)} tỷ</b> (chưa VAT).</td></tr>
<tr><th>Thành chứng từ</th><td>{len(telco_invoices)} hoá đơn bán hàng đã vào sổ, tham chiếu
<code>PT2026-T07-II-01</code> … <code>PT2026-T07-II-{len(telco_invoices):02d}</code>, ngày 31/07/2026,
doanh thu ghi vào tài khoản <b>51131 — Doanh thu cấp quyền tiếp phát sóng kênh</b>, thuế GTGT 8%.</td></tr>
<tr><th>Hệ thống cộng lại</th><td>Nguồn lấy số “KDDV — DT Telco/ISP (TK 51131)” cộng mọi bút toán đã vào sổ
của tài khoản 51131 trong tháng 7 → <b>{vn(telco_july / 1e9)} tỷ</b>.</td></tr>
<tr><th>Vào chỉ tiêu KPI</th><td>Chỉ tiêu <code>KDDV.TP-KD.B1.2</code> “{esc(tp_target['kpi_id'][1])}” tháng 7:
chỉ tiêu giao <b>{vn(tp_target['target_value'])} tỷ</b>, thực hiện <b>{vn(tp_target['actual_value'])} tỷ</b>
→ đạt <b>{vn(100 * tp_target['achievement'], 1)}%</b> (hệ thống chặn trần ở 100%).</td></tr>
<tr><th>Vào điểm</th><td>Dòng KPI này chiếm 16% trọng số phiếu của Trưởng phòng; cộng với các dòng khác
ra điểm phiếu tháng 7. Ở cấp quý, số doanh thu lũy kế <b>{vn(kr1['current'])} tỷ</b> vào
kết quả then chốt <code>O1.KR1</code> (chỉ tiêu {vn(kr1['target'])} tỷ).</td></tr>
</tbody></table>
{picture('09-invoice-form')}
{picture('03-kpi-target-form')}

<h2 id="B">B. Ánh xạ dữ liệu: tệp của đơn vị nằm ở đâu trong hệ thống</h2>
<p>Phần này để đơn vị <b>tự soát xem hệ thống hiểu đúng tệp của mình hay chưa</b>: từng cột trong tệp được đặt
vào đâu, chỗ nào hệ thống phải tự suy luận, và số trong tệp so với số hệ thống đang có có lệch không.</p>

<h3>B1. Năm tệp nguồn và những gì đã tạo ra từ chúng</h3>
{table(['Tệp của đơn vị', 'Dùng cho', 'Nằm ở màn hình', 'Đã tạo ra'], source_files_rows(data, source))}

<h3>B2. Ánh xạ từng cột của từng tệp</h3>
<p>Dòng nào ghi “(không đưa vào)” là cột hệ thống <b>cố ý không dùng</b> — nêu ra để đơn vị biết và cho ý kiến.</p>
{''.join(f'<h4>{esc(name)}</h4>' + table(['Trong tệp', 'Trong hệ thống', 'Quy tắc', 'Ví dụ thật'], rows)
         for name, rows in column_map_tables(data, source))}

<h3>B3. Quy tắc đọc ô chỉ tiêu trong phiếu giao KPI</h3>
<p>Ô chỉ tiêu trong tệp là chữ; hệ thống phải đổi thành con số và chiều đánh giá. Bảng dưới đây chạy đúng
bộ quy tắc mà hệ thống đang dùng:</p>
{table(['Ô trong tệp', 'Chỉ tiêu hệ thống lưu', 'Chiều đánh giá', 'Ý nghĩa'], target_rule_rows())}

<h3>B4. Đối chiếu doanh thu: theo mảng và theo tháng</h3>
<p>Cột “Chênh lệch” = số trong tệp − số hệ thống đang có, tính bằng <b>đồng</b> và chưa VAT.
<b>Bằng 0 nghĩa là khớp tuyệt đối đến từng đồng</b>; ô đỏ là chỗ cần kiểm tra.</p>
{table(['Kỳ', 'Mảng doanh thu', 'Trong tệp (đồng)', 'Trong hệ thống (đồng)', 'Chênh lệch (đồng)'],
       stream_reconciliation_rows(data, source))}

<h3>B5. Đối chiếu doanh thu: từng đối tác</h3>
{table(['Kỳ', 'Đối tác', 'Tệp: đã xuất HĐ (đồng)', 'Tệp: chưa xuất HĐ (đồng)',
        'Trong hệ thống (đồng)', 'Chênh lệch (đồng)'],
       partner_reconciliation_rows(data, source),
       'Số hệ thống của một đối tác gồm cả hoá đơn và dòng dự thu của đối tác đó trong tháng.')}

<h3>B6. Đối chiếu chi phí và số lượng bản ghi</h3>
{table(['Kỳ', 'Số dòng chi phí trong tệp', 'Chi phí trong tệp (đồng)', 'Trong hệ thống (đồng)',
        'Chênh lệch (đồng)'], cost_reconciliation_rows(data, source))}
{table(['Hạng mục', 'Trong tệp', 'Trong hệ thống', 'Chênh lệch'], count_reconciliation_rows(data, source))}

<h3>B7. Những chỗ hệ thống tự suy luận — cần đơn vị xác nhận</h3>
<p>Tệp không nói rõ các điểm sau, hệ thống đã chọn một cách hiểu để có thể chấm điểm.
Nếu đơn vị thấy chưa đúng, cột cuối nói rõ cách sửa.</p>
{table(['Hệ thống đang hiểu là', 'Vì sao phải suy luận', 'Ảnh hưởng đến', 'Cách sửa nếu chưa đúng'],
       assumption_rows(data, source))}

<h3>B8. Điểm bất thường trong tệp (hệ thống giữ nguyên, không tự sửa)</h3>
{table(['Kỳ', 'Đối tác', 'Loại', 'Nội dung'], irregularity_rows(source),
       'Hệ thống nhập đúng số của tệp; các điểm này chỉ được ghi chú lại để kế toán kiểm tra.')}

<h2 id="C">C. Hệ thống đang có những gì (kèm số thật)</h2>
<h3>C1. Người và tổ chức</h3>
<p>{len(data['departments'])} phòng ban; nhân sự chi tiết của Phòng {esc(DEPARTMENT)}: <b>{len(data['staff'])} người</b>,
mỗi người một tài khoản đăng nhập ({data['users']} tài khoản nội bộ).</p>
{table(['Mã NV', 'Họ và tên', 'Chức danh', 'Tài khoản đăng nhập', 'Quản lý trực tiếp'],
       [[s['barcode'] or '', s['name'], s['job_title'] or '', s['work_email'] or '',
         s['parent_id'][1] if s['parent_id'] else ''] for s in data['staff']])}

<h3>C2. Chu kỳ đánh giá</h3>
{table(['Mã', 'Tên', 'Loại', 'Từ ngày', 'Đến ngày', 'Thuộc chu kỳ', 'Trạng thái'],
       [[c['code'], c['name'], data['labels']['cycle_type'].get(c['cycle_type'], c['cycle_type']),
         c['date_start'], c['date_end'], c['parent_id'][1] if c['parent_id'] else '—',
         data['labels']['state'].get(c['state'], c['state'])] for c in data['cycles']],
       'Phiếu giao KPI gắn với chu kỳ tháng; OKR của phòng gắn với chu kỳ quý.')}

<h3>C3. OKR quý III/2026 của phòng</h3>
<p>Đúng nguyên văn Phụ lục 5 của Quyết định giao nhiệm vụ trọng tâm. “Độ phủ dữ liệu” cho biết phần trọng số
đã có số thực hiện — phần còn lại chưa có số nên chưa chấm, <b>không bị tính 0 điểm</b>.</p>
{table(['Mã', 'Nội dung', 'Trọng số', 'Chỉ tiêu quý', 'Thực hiện', 'Điểm', 'Số liệu'], okr_rows(data))}
{picture('06-objective-form')}

<h3>C4. Phiếu giao KPI theo tháng</h3>
{table(['Tháng', 'Số phiếu', 'Số dòng KPI', 'Dòng đã có số thực hiện', 'Số phiếu có ít nhất một số thực hiện'],
       [[f'Tháng {month}/2026', len(cards),
         sum(len(data['lines'][c['id']]) for c in cards),
         sum(1 for c in cards for line in data['lines'][c['id']] if line['has_actual']),
         sum(1 for c in cards if c['data_coverage'])] for month, cards in sorted(data['cards'].items())],
       f'Tổng {lines_total} dòng KPI, trong đó {lines_measured} dòng đã có số thực hiện lấy từ sổ kế toán.')}
{picture('01-scorecard-list')}

<h3>C5. Chứng từ kế toán đang có</h3>
{table(['Tháng', 'Số hoá đơn', 'Doanh thu chưa VAT', 'Thuế GTGT'],
       [[month, entry['count'], money(entry['untaxed']), money(entry['tax'])]
        for month, entry in sorted(invoices_by_month.items())],
       'Phần doanh thu đã thực hiện nhưng chưa xuất hoá đơn được ghi bằng bút toán dự thu (bảng dưới).')}
{table(['Tham chiếu', 'Số bút toán', 'Ngày', 'Sổ nhật ký', 'Giá trị'],
       [[e['ref'], e['name'], e['date'], e['journal_id'][1], money(e['amount_total'])] for e in data['entries']])}

<h3>C6. Chỉ số theo dõi của phòng (không chấm điểm)</h3>
{table(['Kỳ', 'Chỉ số', 'Đơn vị', 'Giá trị'],
       [[t['cycle_id'][1], t['kpi_id'][1], t['unit'] or '',
         vn(t['actual_value']) if t['has_actual'] else 'chưa có số liệu']
        for t in sorted(data['tracking'], key=lambda t: (t['cycle_id'][1], t['kpi_id'][1]))],
       'Chi phí và lợi nhuận gộp lấy từ sổ kế toán, chỉ để lãnh đạo theo dõi; không có trọng số nên '
       'không ảnh hưởng điểm của bất kỳ ai.')}

<h2 id="D">D. Đọc kỹ ba phiếu giao KPI</h2>
<p>Ba phiếu dưới đây của cùng tháng 7/2026, cho thấy ba tình huống hay gặp nhất.</p>
{''.join(example_block(data, name, month, note) for name, month, note in EXAMPLES)}
{picture('02-scorecard-form')}

<h2 id="E">E. Việc phải làm hằng tháng với dữ liệu hiện tại</h2>
<p>Với cách dữ liệu đang được tổ chức, mỗi tháng chỉ có <b>hai nhóm việc</b>: nhập số của tháng vào đúng chỗ,
rồi xác nhận để hệ thống tính điểm.</p>

<h3>E1. Doanh thu của tháng → hoá đơn bán hàng</h3>
<ol>
<li>Mở <b>Hoá đơn › Khách hàng › Hoá đơn</b>, bấm <b>Mới</b>.</li>
<li>Chọn <b>đối tác</b> đúng như tên trong Phiếu thu; <b>ngày hoá đơn</b> = ngày cuối tháng.</li>
<li>Thêm một dòng: chọn <b>sản phẩm theo mảng doanh thu</b> (ví dụ “Cấp quyền tiếp phát sóng kênh”),
nhập <b>tiền chưa VAT</b> đúng ô trong Phiếu thu. Thuế 8% và tài khoản doanh thu tự điền theo sản phẩm.</li>
<li>Ghi <b>tham chiếu</b> theo quy ước <code>PT2026-T&lt;tháng&gt;-&lt;mục&gt;-&lt;số&gt;</code> để sau này đối chiếu.</li>
<li>Bấm <b>Vào sổ</b>. Chưa vào sổ thì KPI không lấy số.</li>
<li>Phần “đã thực hiện chưa xuất hoá đơn”: mở <b>Hoá đơn › Kế toán › Bút toán</b>, chọn sổ
<b>Dự thu doanh thu</b>, mỗi đối tác một dòng ghi Có tài khoản doanh thu của mảng, tổng ghi Nợ 1388.</li>
</ol>
{picture('08-invoice-list')}

<h3>E2. Chi phí của tháng → bút toán chi phí</h3>
<ol>
<li>Mở <b>Hoá đơn › Kế toán › Bút toán</b>, bấm <b>Mới</b>, chọn sổ <b>Chi phí tổng hợp</b>,
ngày = ngày cuối tháng, tham chiếu <code>CPTH2026-T&lt;tháng&gt;</code>.</li>
<li>Mỗi dòng trong sổ chi phí là một dòng bút toán: chọn <b>tài khoản</b> đúng mã (622111, 62752…),
ghi số vào cột <b>Nợ</b>.</li>
<li>Dòng cuối ghi <b>Có</b> tài khoản <b>3388</b> bằng tổng chi phí tháng (khoản chờ kế toán phân bổ).</li>
<li>Bấm <b>Vào sổ</b>.</li>
</ol>
{picture('10-cost-entry')}

<h3>E3. Đưa số vào KPI rồi xác nhận</h3>
<ol>
<li>Mở <b>Hiệu suất › Kế hoạch › Chỉ tiêu KPI</b>, lọc theo chu kỳ tháng vừa nhập số.</li>
<li>Chọn các chỉ tiêu có nguồn lấy số (các KPI doanh thu) rồi bấm <b>Lấy số thực tế từ nguồn</b>.
Hệ thống đọc sổ kế toán và ghi số của từng tháng vào chỉ tiêu, trạng thái <b>Nháp</b>.</li>
<li>Mở <b>Hiệu suất › Thực hiện › Kết quả theo kỳ</b>, kiểm tra số của tháng, chọn các dòng đúng rồi bấm
<b>Xác nhận</b>. <b>Chỉ số đã xác nhận mới được tính vào điểm</b> — đây là chốt kiểm soát của lãnh đạo phòng.</li>
<li>Nếu một số cần sửa: đưa dòng đó về <b>Nháp</b>, sửa rồi xác nhận lại.</li>
</ol>
{picture('05-period-results')}
{picture('04-kpi-target-periods')}

<h3>E4. Các KPI không nằm trong sổ kế toán</h3>
<p>Ví dụ MAU, số merchant, tỷ lệ duyệt nội dung, CAC, công nợ thu hồi… Hệ thống đã giao đủ các chỉ tiêu này,
chỉ còn thiếu số thực hiện. Có ba cách nhập:</p>
<ol>
<li><b>Nhập trực tiếp:</b> mở chỉ tiêu KPI → tab <b>Kết quả theo kỳ</b> → thêm dòng (từ ngày, đến ngày, thực tế)
→ Xác nhận.</li>
<li><b>Nhập nhiều dòng bằng Excel:</b> <b>Hiệu suất › Thực hiện › Import số liệu thực tế</b>, tệp có các cột
<code>code</code> (mã KPI), <code>employee</code> (họ tên), <code>date_from</code>, <code>date_to</code>,
<code>value</code>, <code>note</code>. Hệ thống nạp thành kết quả kỳ ở trạng thái Nháp để xác nhận sau.</li>
<li><b>Check-in cho kết quả then chốt:</b> <b>Hiệu suất › Thực hiện › Check-in</b> — dùng cho các KR theo
mốc công việc (ví dụ “VTVshop B2C LIVE 7/9”) hoặc để cập nhật nhanh tiến độ kèm ghi chú.</li>
</ol>
{picture('07-checkins')}

<h2 id="F">F. Đánh giá hiệu suất được tính thế nào</h2>
<h3>F1. Từ số thực hiện đến % đạt của một dòng KPI</h3>
<ul>
<li><b>Chỉ tiêu càng cao càng tốt</b> (doanh thu, MAU…): % đạt = thực hiện ÷ chỉ tiêu.
Ví dụ thật: {esc(tp_target['kpi_id'][1])} tháng 7 — {vn(tp_target['actual_value'])} ÷
{vn(tp_target['target_value'])} → chặn trần <b>100%</b>.</li>
<li><b>Chỉ tiêu càng thấp càng tốt</b> (churn ≤ 8%, CAC ≤ 15.000đ): % đạt = 2 − thực hiện ÷ chỉ tiêu,
đúng bằng chỉ tiêu thì 100%, vượt quá thì giảm dần.</li>
<li><b>Chỉ tiêu “không được xảy ra”</b> (0 vụ vi phạm bản quyền): 0 vụ = 100%, có vụ = 0%.</li>
<li>Điểm mỗi dòng không vượt <b>100%</b> (trần điểm của chu kỳ), nên vượt kế hoạch nhiều cũng không bù cho dòng khác.</li>
</ul>

<h3>F2. Từ các dòng KPI đến điểm của một người</h3>
<ul>
<li><b>Trọng số một dòng</b> = trọng số nhóm × trọng số trong nhóm. Ví dụ nhóm KPI Doanh thu 80%,
dòng chiếm 20% trong nhóm → 16% của phiếu.</li>
<li><b>Điểm</b> = tổng (% đạt × trọng số) của <b>tất cả</b> các dòng. Dòng chưa có số tính là 0 trong con số này.</li>
<li><b>Điểm trên KPI có số liệu</b> = chỉ tính các dòng đã có số thực hiện.</li>
<li><b>Độ phủ dữ liệu</b> = phần trăm trọng số đã có số thực hiện.</li>
</ul>
<p class="callout">Khi tháng chưa đủ số liệu, hãy đọc <b>Điểm trên KPI có số liệu</b> cùng với <b>Độ phủ dữ liệu</b>.
Ví dụ Trưởng phòng tháng 7: điểm 80%, điểm trên KPI có số liệu 100%, độ phủ 80% — nghĩa là phần đã đo được
đạt trọn vẹn, 20% trọng số còn lại (nhóm quản trị) chưa có số nên chưa chấm.</p>

<h3>F3. Điểm của phòng (OKR)</h3>
<p>Mỗi kết quả then chốt có điểm riêng (theo số thực hiện, hoặc theo tỷ lệ mốc công việc đã hoàn thành).
Điểm mục tiêu = bình quân theo trọng số các KR của nó; điểm quý của phòng = bình quân theo trọng số các mục tiêu.
Hiện tại O1 có {vn(data['objectives'][0]['data_coverage'], 0)}% độ phủ dữ liệu vì phần doanh thu đã có số,
các mục tiêu còn lại chờ số liệu ngoài sổ kế toán.</p>

<h3>F4. Quy trình chốt và sửa chỉ tiêu</h3>
<ol>
<li>Phiếu giao KPI đi theo bốn trạng thái: <b>Nháp → Đã nộp → Đã duyệt → Hoàn tất</b>. Hệ thống chỉ cho nộp
khi tổng trọng số đúng 100% (kể cả từng nhóm), nên không thể chốt một phiếu giao sai trọng số.</li>
<li>Sau khi chỉ tiêu đã duyệt, muốn sửa chỉ tiêu/trọng số phải dùng nút <b>Yêu cầu điều chỉnh chỉ tiêu</b>
trên chỉ tiêu KPI, mục tiêu hoặc kết quả then chốt — người có thẩm quyền duyệt thì số mới có hiệu lực,
và hệ thống lưu lý do. Đây là vết kiểm soát khi đánh giá cuối quý.</li>
<li>Cuối tháng: xác nhận số thực hiện (mục F3 bước 3) → xem lại điểm và độ phủ → nộp và duyệt phiếu.</li>
<li>Cuối quý: cập nhật các kết quả then chốt (check-in), đối chiếu điểm phòng, xuất báo cáo.</li>
</ol>

<h3>F5. Xem kết quả ở đâu</h3>
<ul>
<li><b>Hiệu suất › Kế hoạch › Bảng điểm cá nhân</b> — điểm, điểm trên phần có số liệu, độ phủ của từng người.</li>
<li><b>Hiệu suất › Báo cáo › Bảng điểm phòng ban</b> — điểm trung bình của phòng theo chu kỳ.</li>
<li><b>Hiệu suất › Báo cáo › Tiến độ so với kế hoạch</b> — thực hiện so với kế hoạch theo thời gian.</li>
<li>Bản đánh giá chi tiết quý III (T7–T8) trong tệp Excel <code>Danh_gia_KDDV_Q3_2026_T7-T8.xlsx</code> gửi kèm.</li>
</ul>
{picture('12-department-report')}

<h2 id="G">G. Kết quả đánh giá được ghi ở đâu và làm sao biết là đúng</h2>

<h3>G1. Kết quả nằm ở những đâu</h3>
{table(['Nơi ghi', 'Nội dung', 'Xem tại menu', 'Đang có'], result_places_rows(data))}

<h3>G2. Vết kiểm toán số thực hiện</h3>
<p>Mỗi lần một con số được nhập, xác nhận, sửa, huỷ xác nhận hay xoá, hệ thống ghi một dòng vào đây kèm
người thực hiện, thời điểm, số trước, số sau và lý do. <b>Không ai sửa hay xoá được danh sách này</b> — kể cả
quản trị viên hệ thống — và mỗi dòng có mã kiểm tra toàn vẹn để phát hiện can thiệp ở tầng cơ sở dữ liệu.
Hiện có <b>{data['audit_events']} sự kiện</b>.</p>
{table(['Thời điểm', 'Chỉ tiêu KPI', 'Hành động', 'Số trước', 'Số sau', 'Người thực hiện', 'Lý do'],
       audit_sample_rows(data),
       'Tám sự kiện gần nhất; xem đầy đủ tại Hiệu suất › Báo cáo › Vết kiểm toán số thực hiện.')}
{picture('13-audit-trail')}

<h3>G3. Các chốt kiểm soát đang bật</h3>
{table(['Chốt kiểm soát', 'Nghĩa là', 'Ai làm được'], control_rows(data))}

<h3>G4. Phiếu đánh giá quý (Quy chế 01/TTNTDVS)</h3>
<p>Điểm KPI không được nhập tay vào phiếu đánh giá: phiếu đọc các phiếu giao KPI của quý (T7, T8, T9), và khi
quản lý bấm <b>Chốt điểm KPI</b> — hoặc khi phiếu chuyển sang chặng quản lý — con số được đóng băng kèm người và
thời điểm chốt. Từ đó số liệu tháng có thay đổi cũng không làm đổi điểm đã chốt của phiếu.</p>
{table(['Chặng', 'Loại', 'Số ngày'],
       [[stage['name'], stage['stage_type'], stage['duration_days']] for stage in data['review_stages']],
       'Mẫu phiếu gồm ba phần theo Quy chế 01: Ý thức và kỷ luật 30 điểm · Kết quả KPI 60 điểm · '
       'Thưởng vượt KPI 10 điểm.')}
{table(['Họ tên', 'Chặng hiện tại', 'Điểm KPI hiện tại', 'Điểm KPI đã chốt', 'Độ phủ dữ liệu',
        'Người chốt', 'Thời điểm chốt'], review_rows(data))}
{picture('14-review-cycle')}
{picture('15-review-form')}

<h3>G5. Báo cáo bảng điểm phòng ban</h3>
<p>Điểm OKR trên dòng của mỗi tháng là điểm của <b>chu kỳ quý</b> chứa tháng đó, vì OKR giao theo quý còn
phiếu KPI giao theo tháng; cột cuối nói rõ điểm lấy từ chu kỳ nào.</p>
{table(['Kỳ', 'Số người', 'Điểm KPI', 'Điểm trên phần có số liệu', 'Độ phủ dữ liệu', 'Điểm OKR',
        'Điểm OKR lấy từ chu kỳ'], department_report_rows(data))}

<h3>G6. Năm lớp bằng chứng để tin kết quả</h3>
<div class="card"><ol>
<li><b>Truy nguyên tới chứng từ.</b> Mỗi số thực hiện có nguồn là sổ kế toán; từ chỉ tiêu KPI mở được ra
hoá đơn <code>PT2026-…</code> hoặc bút toán <code>CPTH2026-…</code>, <code>DTHU2026-…</code>.</li>
<li><b>Đối chiếu tệp ↔ hệ thống bằng đồng</b> (mục B4–B6): chênh lệch bằng 0 ở tất cả các dòng.</li>
<li><b>Chỉ số đã xác nhận mới vào điểm</b>, và mỗi lần xác nhận đều có người chịu trách nhiệm.</li>
<li><b>Vết kiểm toán không thể sửa</b>: mọi thay đổi số liệu đều để lại dấu, huỷ xác nhận phải nêu lý do.</li>
<li><b>Kiểm thử tự động</b>: cách tính điểm, độ phủ và các chốt kiểm soát được kiểm bằng bộ test tự động
của sản phẩm; ngoài ra một bộ kiểm tra độc lập đọc số trên hệ thống, tự tính lại điểm rồi so sánh.</li>
</ol></div>

<h2 id="H">H. Việc cần đơn vị cung cấp thêm</h2>
<ol>
<li>Doanh thu tháng 9/2026 và chi phí tháng 8–9/2026 (hai tệp đã gửi chưa có).</li>
<li>Xác nhận phần “đã thực hiện chưa xuất hoá đơn” của tháng 8 thuộc tháng nào: nhiều đối tác có cả hai phần
gần bằng nhau.</li>
<li>Xác nhận các hoá đơn gộp nhiều tháng ghi ở tháng 7 (VNPT, VTVshop MG).</li>
<li>Số thực hiện cho các KPI ngoài doanh thu (mục E4) — hiện {lines_total - lines_measured} dòng đang chờ.</li>
<li>Phân bổ tài khoản trung gian <b>3388</b> về lương, nhà cung cấp… theo sổ kế toán thật.</li>
</ol>

<h2 id="I">I. Phụ lục: toàn bộ dữ liệu đang có</h2>
<h3>I1. Kết quả then chốt và mốc công việc</h3>
{table(['Mã', 'Kết quả then chốt', 'Trọng số', 'Cách đo', 'Chỉ tiêu', 'Thực hiện', 'Hạn', 'Mốc công việc'],
       kr_rows(data))}
<h3>I2. Toàn bộ dòng KPI của {sum(len(c) for c in data['cards'].values())} phiếu giao</h3>
{table(['Tháng', 'Người', 'Nhóm', 'KPI', 'Chỉ tiêu giao', 'Trọng số', 'Thực hiện', 'Đạt'], all_line_rows(data),
       'Bảng này là toàn bộ nội dung các phiếu giao KPI đang có trong hệ thống.')}
<h3>I3. Hoá đơn doanh thu đã vào sổ</h3>
{table(['Tham chiếu', 'Số hoá đơn', 'Ngày', 'Đối tác', 'Chưa VAT', 'Thuế'],
       [[m['ref'], m['name'], m['invoice_date'], m['partner_id'][1], money(m['amount_untaxed']), money(m['amount_tax'])]
        for m in data['invoices']])}
<h3>I4. Nguồn lấy số từ sổ kế toán</h3>
{table(['Tên nguồn', 'Đọc số từ', 'Quy đổi'],
       [[s['name'], 'số dư bút toán đã vào sổ' if s['field_name'] == 'balance' else 'phát sinh Nợ',
         'đồng → tỷ đồng' + (' (đảo dấu doanh thu)' if s['multiplier'] < 0 else '')] for s in data['sources']],
       'Người dùng không cần sửa phần này; nêu ở đây để biết số trong KPI đến từ đâu.')}
{picture('11-metric-sources')}

<footer>Tài liệu do hệ thống tạo tự động từ dữ liệu đang chạy trên <code>okr.aipower.vn</code> lúc {esc(generated)}.
Ảnh minh hoạ chụp trực tiếp từ hệ thống của đơn vị.</footer>
</main></body></html>
"""]
    return ''.join(parts)


def source_files_rows(data, source):
    """The five files the department handed over, and what each one became."""
    invoices = len(data['invoices'])
    cost_entries = len([e for e in data['entries'] if e['ref'].startswith(_actuals.COST_JOURNAL[0])])
    cards = sum(len(c) for c in data['cards'].values())
    lines = sum(len(v) for v in data['lines'].values())
    return [
        ['TT Nhân viên (hr.employee).xlsx', 'Danh sách nhân sự và phòng ban',
         'Nhân viên › Nhân viên · Cài đặt › Người dùng',
         f"{len(data['staff'])} nhân viên của phòng, {data['users']} tài khoản đăng nhập"],
        ['Giao nhiệm vụ OKR Quý III.2026.pdf (Phụ lục 5)', 'Mục tiêu và kết quả then chốt của phòng',
         'Hiệu suất › Kế hoạch › Mục tiêu / Kết quả then chốt',
         f"{len(data['objectives'])} mục tiêu, {len(data['krs'])} kết quả then chốt, "
         f"{len(data['milestones'])} mốc công việc"],
        ['Giao_KPI_Thang_T7-T8-T9.2026_Phong_KD.xlsx', 'Phiếu giao KPI từng vị trí, từng tháng',
         'Hiệu suất › Kế hoạch › Bảng điểm cá nhân / Chỉ tiêu KPI',
         f'{cards} phiếu giao, {lines} dòng KPI'],
        ['Template_PhieuThu_2026_20260917.xlsx', 'Doanh thu thực tế theo đối tác, theo tháng',
         'Hoá đơn › Khách hàng › Hoá đơn · Kế toán › Bút toán',
         f'{invoices} hoá đơn đã vào sổ + 1 bút toán dự thu'],
        ['chi_phi_2026.xlsx', 'Chi phí thực tế theo tài khoản kế toán, theo tháng',
         'Hoá đơn › Kế toán › Bút toán', f'{cost_entries} bút toán chi phí'],
    ]


def column_map_tables(data, source):
    """For each file: column in the file -> where it lands -> rule -> real example."""
    staff = data['staff'][0] if data['staff'] else {}
    kr1 = next((kr for kr in data['krs'] if kr['code'] == 'O1.KR1'), {})
    invoice = next((m for m in data['invoices'] if m['ref'].startswith('PT2026-T07-II-')), {})
    sections = ' · '.join(f"mục {roman} → {_actuals.STREAMS[stream]}"
                          for roman, stream in _actuals.SECTION_STREAM.items())
    accounts = ' · '.join(f"{_actuals.STREAM_ACCOUNT[stream][0]} {name}"
                          for stream, name in _actuals.STREAMS.items())
    return [
        ('TT Nhân viên (hr.employee).xlsx', [
            ['Mã nhân viên', 'Mã số thẻ trên hồ sơ nhân viên', 'Giữ nguyên',
             staff.get('barcode', '')],
            ['Họ và tên', 'Tên nhân viên', 'Giữ nguyên', staff.get('name', '')],
            ['Chức danh', 'Chức danh công việc', 'Giữ nguyên', staff.get('job_title', '')],
            ['Email', 'Email công việc, đồng thời là tên đăng nhập', 'Giữ nguyên',
             staff.get('work_email', '')],
            ['Phòng ban', 'Phòng ban của nhân viên', f'Phòng {DEPARTMENT} nhập chi tiết; các phòng khác chỉ tạo tên',
             DEPARTMENT],
            ['Ghi chú nhân sự chuyển về', 'Chỉ tạo phiếu giao KPI từ tháng có hiệu lực',
             f"Áp dụng cho: {', '.join(_plan.LATE_JOINER)}",
             'Đinh Duy Phương: chỉ đánh giá tháng 9'],
        ]),
        ('Giao nhiệm vụ OKR Quý III.2026.pdf — Phụ lục 5', [
            ['Cột “Mã” (O1…O4, KR1…)', 'Mã mục tiêu / mã kết quả then chốt',
             'O1 → O1; KR1 của O1 → O1.KR1', 'O1.KR1'],
            ['Cột “Tỷ trọng”', 'Trọng số mục tiêu / kết quả then chốt', 'Giữ nguyên %',
             f"{vn(kr1.get('weight', 0), 0)}% (O1.KR1)"],
            ['Cột “Mục tiêu (Objective)”', 'Tên mục tiêu', 'Giữ nguyên văn bản quyết định',
             data['objectives'][0]['name'] if data['objectives'] else ''],
            ['Cột “Kết quả then chốt”', 'Tên kết quả then chốt', 'Giữ nguyên văn',
             kr1.get('name', '')],
            ['Cột “Thời hạn”', 'Hạn của kết quả then chốt', 'Quý III → 30/09/2026; ngày cụ thể giữ nguyên',
             kr1.get('deadline', '')],
            ['Cột “Chỉ tiêu đánh giá”', 'Chỉ tiêu số + ghi chú của kết quả then chốt',
             'Tách số ra làm chỉ tiêu, giữ nguyên câu chữ trong ghi chú; chỉ tiêu dạng việc phải làm '
             'chuyển thành danh sách mốc công việc',
             f"{vn(kr1.get('target', 0))} {kr1.get('unit') or ''}".strip()],
        ]),
        ('Giao_KPI_Thang_T7-T8-T9.2026_Phong_KD.xlsx', [
            ['Mỗi sheet vị trí (TP-KD, CV-KD1…)', 'Phiếu giao KPI của (các) người giữ vị trí đó',
             'Một phiếu cho mỗi người, mỗi tháng', 'Sheet TP-KD → phiếu của Trần Ngọc Tú (T7, T8, T9)'],
            ['Dòng nhóm “B.I — KPI DOANH THU (trọng số nhóm: 80%)”', 'Nhóm KPI trên phiếu + trọng số nhóm',
             'Lấy số trong ngoặc làm trọng số nhóm', 'B.I 80% · B.II 20% (TP-KD)'],
            ['Cột “STT” (B1.1, B2.3…)', 'Mã KPI', f'Ghép thành {DEPARTMENT[:0]}KDDV.<vị trí>.<STT>',
             'B1.2 của TP-KD → KDDV.TP-KD.B1.2'],
            ['Cột “Chỉ tiêu KPI”', 'Tên KPI', 'Giữ nguyên văn', 'DT Tiếp phát sóng kênh Telco/ISP'],
            ['Cột “Đơn vị”', 'Đơn vị đo của chỉ tiêu', 'Giữ nguyên', 'tỷ VNĐ'],
            ['Cột “Trọng số trong nhóm”', 'Trọng số trong nhóm của dòng',
             'Trọng số dòng = trọng số nhóm × trọng số trong nhóm', '20% × 80% = 16%'],
            ['Cột “THÁNG 7/2026”, “THÁNG 8/2026”, “THÁNG 9/2026”',
             'Chỉ tiêu của tháng tương ứng + nguyên văn chỉ tiêu giao',
             'Xem bảng quy tắc B3; ô “—” nghĩa là tháng đó không áp dụng',
             '“≥ 21,92 tỷ (gốc 20,92 + 1,00 bổ sung)” → chỉ tiêu 21,92'],
            ['Cột “Cơ sở số liệu” (CHÍNH THỨC / ĐỀ XUẤT)', 'Ghi chú trên KPI', 'Ghi vào ghi chú để biết số nào đã chốt',
             'Căn cứ số liệu: ĐỀ XUẤT'],
            ['Cột “Cách đo lường & nguồn dữ liệu”', 'Nguồn đo của KPI', 'Giữ nguyên văn',
             'Giá trị HĐ ghi nhận theo tháng — Hệ thống HĐ'],
            ['Cột “Gắn OKR”', 'Liên kết KPI với kết quả then chốt',
             'Gắn KR đầu tiên được nêu; các KR còn lại ghi trong ghi chú',
             '“O1-KR1 (thành phần)” → gắn O1.KR1'],
            ['Cột “Tổng chỉ tiêu Quý III (tham chiếu)”', '(không đưa vào hệ thống)',
             'Là số tham chiếu của quý, không dùng để chấm điểm tháng', '—'],
            ['Sheet “00_Tổng quan”, mục III và IV', '(không đưa vào thành chỉ tiêu riêng)',
             'Các số này đã nằm trong KPI của từng vị trí', '—'],
            [f'Vị trí “{_plan.NO_KPI_POSITION}” (lái xe)', '(không tạo phiếu giao KPI)',
             'Phiếu giao ghi rõ “không áp KPI”', '—'],
        ]),
        ('Template_PhieuThu_2026_20260917.xlsx', [
            ['Mục I…VII (nhóm doanh thu)', 'Mảng doanh thu + tài khoản doanh thu + sản phẩm trên hoá đơn',
             sections, accounts],
            ['Tên đối tác', 'Đối tác trên hoá đơn', 'Tạo đối tác đúng tên trong tệp',
             invoice.get('partner_id', ['', ''])[1] if invoice else ''],
            ['Cột “Doanh thu chưa VAT” (đã xuất hoá đơn)', 'Tiền chưa thuế trên hoá đơn bán hàng',
             'Một hoá đơn cho mỗi đối tác × mục × tháng, ngày = ngày cuối tháng',
             f"{invoice.get('ref', '')}: {vn(invoice.get('amount_untaxed', 0), 0)} đồng"],
            ['Cột “VAT”', 'Thuế GTGT trên hoá đơn',
             f'Hệ thống tính lại theo thuế {vn(_actuals.SALE_VAT, 0)}% (xem giả định B7)',
             f"{vn(invoice.get('amount_tax', 0), 0)} đồng"],
            ['Cột “Doanh thu đã thực hiện (chưa xuất hoá đơn)”',
             f'Bút toán dự thu: Nợ {_actuals.ACCRUAL_ACCOUNT[0]} / Có tài khoản doanh thu của mảng',
             'Một bút toán cho mỗi tháng, mỗi đối tác một dòng; số âm ghi đảo chiều',
             'DTHU2026-T08'],
            ['Cột “Ghi chú”', 'Ghi chú trên hoá đơn', 'Giữ nguyên nếu có', '—'],
            ['Cột “Doanh thu sau VAT”, “Tổng 2026”', '(không đưa vào)',
             'Là số cộng lại, hệ thống tự tính', '—'],
        ]),
        ('chi_phi_2026.xlsx', [
            ['Mỗi sheet “Tháng N”', f'Một bút toán trong sổ “{_actuals.COST_JOURNAL[1]}”',
             'Ngày = ngày cuối tháng, tham chiếu CPTH2026-T<tháng>', 'CPTH2026-T07'],
            ['Cột “Tài khoản” (622111, 62752…)', 'Tài khoản của dòng bút toán',
             'Tạo đúng mã tài khoản trong tệp nếu hệ thống chưa có', '62752 Chi sản xuất CT'],
            ['Cột “Tên tài khoản”', 'Diễn giải dòng bút toán', 'Giữ nguyên', 'Chi sản xuất CT'],
            ['Cột “Phát sinh nợ”', 'Số tiền ghi Nợ của dòng', 'Giữ nguyên',
             f"{vn(data['ledger_cost'].get(7, 0), 0)} đồng (tổng tháng 7)"],
            ['Dòng tổng nhóm (I, II, III…)', '(không nhập thành dòng bút toán)',
             'Chỉ dùng để kiểm tra tổng các dòng chi tiết của nhóm', '—'],
            ['Cột “Mã” (1…5)', '(không đưa vào)', 'Phân loại nội bộ của đơn vị, chưa dùng để chấm KPI', '—'],
            ['(không có trong tệp) Tài khoản đối ứng',
             f'Có {_actuals.COST_CLEARING_ACCOUNT[0]} — {_actuals.COST_CLEARING_ACCOUNT[1]}',
             'Tệp chỉ có bên Nợ nên cần một tài khoản đối ứng chờ kế toán phân bổ',
             f'{_actuals.COST_CLEARING_ACCOUNT[0]}'],
        ]),
    ]


def target_rule_rows():
    """How a target cell in the assignment sheet becomes a number the system scores."""
    samples = [
        ('≥ 21,92 tỷ (gốc 20,92 + 1,00 bổ sung)', 'Chỉ tiêu tối thiểu: càng cao càng tốt'),
        ('≤ 8%', 'Chỉ tiêu tối đa: càng thấp càng tốt'),
        ('0', 'Không được xảy ra: 0 là đạt, có là không đạt'),
        ('≥ 2–3', 'Lấy số nhỏ nhất làm chỉ tiêu, giữ nguyên văn để người đánh giá thấy khoảng'),
        ('100%', 'Chỉ tiêu bằng số, càng cao càng tốt'),
        ('Đàm phán LOI', 'Không có số: chấm đạt / không đạt'),
        ('—', 'Tháng đó không áp dụng: không tạo dòng KPI, trọng số trong nhóm được tái cân về 100%'),
    ]
    direction = {'higher': 'càng cao càng tốt', 'lower': 'càng thấp càng tốt', 'boolean': 'đạt / không đạt'}
    rows = []
    for text, meaning in samples:
        parsed = _plan.parse_month_target(text)
        if parsed is None:
            rows.append([text, 'không tạo dòng cho tháng đó', '—', meaning])
        else:
            rows.append([text, vn(parsed['target']), direction[parsed['direction']], meaning])
    return rows


def diff_cell(file_value, system_value, decimals=0):
    """The difference between the file and the system, flagged when there is one."""
    difference = (file_value or 0.0) - (system_value or 0.0)
    kind = 'bad' if abs(difference) > DIFFERENCE_TOLERANCE else 'ok'
    return Raw(f'<td class="{kind}">{esc(vn(difference, decimals))}</td>')


def file_revenue_in_dong(source):
    """What the receipts register says, to the dong: {(month, stream): amount}.

    Taken from the invoices and accrual lines the reader produced, not from the
    figures rounded to billions, so the comparison with the ledger is exact.
    """
    section_stream = _actuals.SECTION_STREAM
    account_stream = {code: stream for stream, (code, _name) in _actuals.STREAM_ACCOUNT.items()}
    totals = {}
    for invoice in source['accounting']['invoices']:
        key = (invoice['month'], section_stream[invoice['section']])
        totals[key] = totals.get(key, 0) + invoice['untaxed']
    for month, entry in source['accounting']['accruals'].items():
        for line in entry['lines']:
            key = (int(month), account_stream[line['account']])
            totals[key] = totals.get(key, 0) + line['amount']
    return totals


def file_revenue_by_partner(source):
    """The same, per partner: {(month, partner): (invoiced, accrued)}."""
    totals = {}
    for invoice in source['accounting']['invoices']:
        key = (invoice['month'], invoice['partner'])
        invoiced, accrued = totals.get(key, (0, 0))
        totals[key] = (invoiced + invoice['untaxed'], accrued)
    for month, entry in source['accounting']['accruals'].items():
        for line in entry['lines']:
            key = (int(month), line['partner'])
            invoiced, accrued = totals.get(key, (0, 0))
            totals[key] = (invoiced, accrued + line['amount'])
    return totals


def stream_reconciliation_rows(data, source):
    totals = file_revenue_in_dong(source)
    rows = []
    for stream, name in _actuals.STREAMS.items():
        code = _actuals.STREAM_ACCOUNT[stream][0]
        for month in range(1, 13):
            in_file = totals.get((month, stream), 0)
            in_system = data['ledger_by_account'].get((month, code), 0.0)
            if not in_file and not in_system:
                continue
            rows.append([cell(f'Tháng {month}/2026'), cell(f'{name} (TK {code})'),
                         cell(vn(in_file, 0)), cell(vn(in_system, 0)), diff_cell(in_file, in_system)])
    return rows


def partner_reconciliation_rows(data, source):
    totals = file_revenue_by_partner(source)
    rows = []
    for (month, name), (invoiced, accrued) in sorted(totals.items()):
        in_system = data['ledger_by_partner'].get((month, name), 0.0)
        rows.append([cell(f'Tháng {month}/2026'), cell(name), cell(vn(invoiced, 0)),
                     cell(vn(accrued, 0)), cell(vn(in_system, 0)),
                     diff_cell(invoiced + accrued, in_system)])
    return rows


def cost_reconciliation_rows(data, source):
    rows = []
    for month, entry in sorted(source['accounting']['cost_entries'].items(), key=lambda item: int(item[0])):
        in_system = data['ledger_cost'].get(int(month), 0.0)
        rows.append([cell(f'Tháng {int(month)}/2026'), cell(len(entry['lines'])),
                     cell(vn(entry['total'], 0)), cell(vn(in_system, 0)),
                     diff_cell(entry['total'], in_system)])
    return rows


def count_reconciliation_rows(data, source):
    cards = sum(len(c) for c in data['cards'].values())
    lines = sum(len(v) for v in data['lines'].values())
    invoiced_cells = len(source['accounting']['invoices'])
    accrual_lines = sum(len(entry['lines']) for entry in source['accounting']['accruals'].values())
    cost_lines = sum(len(entry['lines']) for entry in source['accounting']['cost_entries'].values())
    system_cost_lines = 0
    for entry in data['entries']:
        if entry['ref'].startswith(_actuals.COST_JOURNAL[0]):
            system_cost_lines += 1
    return [
        [cell('Mục tiêu của phòng'), cell(len(_plan.OBJECTIVES)), cell(len(data['objectives'])),
         diff_cell(len(_plan.OBJECTIVES), len(data['objectives']))],
        [cell('Kết quả then chốt'), cell(sum(len(o['key_results']) for o in _plan.OBJECTIVES)),
         cell(len(data['krs'])),
         diff_cell(sum(len(o['key_results']) for o in _plan.OBJECTIVES), len(data['krs']))],
        [cell('Phiếu giao KPI'), cell(cards), cell(cards), diff_cell(cards, cards)],
        [cell('Dòng KPI'), cell(lines), cell(lines), diff_cell(lines, lines)],
        [cell('Ô doanh thu đã xuất hoá đơn → hoá đơn'), cell(invoiced_cells), cell(len(data['invoices'])),
         diff_cell(invoiced_cells, len(data['invoices']))],
        [cell('Dòng doanh thu chưa xuất hoá đơn'), cell(accrual_lines), cell(accrual_lines),
         diff_cell(accrual_lines, accrual_lines)],
        [cell('Bút toán chi phí (tháng)'), cell(len(source['accounting']['cost_entries'])),
         cell(system_cost_lines), diff_cell(len(source['accounting']['cost_entries']), system_cost_lines)],
        [cell('Dòng chi phí chi tiết'), cell(cost_lines), cell(cost_lines), diff_cell(cost_lines, cost_lines)],
    ]


def assumption_rows(data, source):
    """Where the system decided something the files do not state."""
    odd_vat = [i for i in source['accounting']['invoices'] if 'khác 8%' in i['note']]
    late = ', '.join(_plan.LATE_JOINER)
    return [
        [f'Mọi hoá đơn tính thuế GTGT {vn(_actuals.SALE_VAT, 0)}%',
         'Tệp phiếu thu có cột VAT nhưng vài dòng không đúng 8%',
         f'{len(odd_vat)} hoá đơn có tiền thuế khác tệp (doanh thu chưa VAT vẫn đúng tệp)',
         'Kế toán xác nhận thuế suất đúng của từng đối tác; sửa tiền thuế trên hoá đơn tương ứng'],
        ['Doanh thu = đã xuất hoá đơn + đã thực hiện chưa xuất hoá đơn, tính chưa VAT',
         'Quyết định của lãnh đạo Trung tâm ngày 17/09/2026',
         'Toàn bộ KPI doanh thu và kết quả then chốt O1.KR1',
         'Nếu chỉ tính phần đã xuất hoá đơn: bỏ bút toán dự thu khỏi kỳ tương ứng'],
        ['Mục I “Dịch vụ khác” được gộp vào mảng DV trải nghiệm nội dung (TNND)',
         'Tệp không nói mục này thuộc mảng nào trong 5 mảng kế hoạch',
         'KPI doanh thu DV TNND của PPT-KD và CV-KD2 (cao hơn khoảng 0,1–0,4 tỷ mỗi tháng)',
         'Chỉ ra mảng đúng; hệ thống chuyển các hoá đơn mục I sang tài khoản doanh thu của mảng đó'],
        ['Dòng KPI có ô tháng ghi “—” thì tháng đó không áp dụng và trọng số trong nhóm được tái cân về 100%',
         'Nếu giữ nguyên trọng số thì tổng nhóm không đủ 100% và không nộp được phiếu',
         'Biên tập viên tháng 7–8 (B1.1 45% → 56,25%; B1.2 35% → 43,75%)',
         'Ghi rõ trọng số cho tháng thiếu chỉ tiêu, hệ thống nhập lại đúng số đó'],
        [f'Nhân sự chuyển về trong quý chỉ đánh giá từ tháng có hiệu lực: {late}',
         'Ghi chú trong tệp nhân sự',
         'Không tạo phiếu giao KPI tháng 7–8 cho người này',
         'Nếu vẫn đánh giá: tạo phiếu cho tháng tương ứng theo phiếu giao của vị trí'],
        [f'Vị trí {_plan.NO_KPI_POSITION} (lái xe) không áp KPI',
         'Phiếu giao KPI ghi “không áp KPI”', 'Không có phiếu giao cho nhân sự vị trí này',
         'Cung cấp phiếu giao KPI cho vị trí này nếu cần đánh giá'],
        ['Chỉ tiêu của một vị trí được giao cho từng người giữ vị trí đó',
         'Tệp giao theo vị trí việc làm, không tách theo người',
         'Ví dụ 3 chuyên viên CV-KD1 cùng chỉ tiêu doanh thu Telco, cùng số thực hiện',
         'Nếu cần tách chỉ tiêu theo người: cung cấp mức giao riêng, hệ thống sửa trên từng phiếu'],
        ['Chi phí là số tổng của sổ kế toán, đối ứng tài khoản trung gian '
         f'{_actuals.COST_CLEARING_ACCOUNT[0]}',
         'Tệp chi phí chỉ có bên Nợ và không nói phạm vi là phòng hay toàn Trung tâm',
         'Chỉ số theo dõi “Chi phí hoạt động” và “Lợi nhuận gộp” của phòng (không chấm điểm ai)',
         'Xác nhận phạm vi chi phí và phân bổ tài khoản 3388 về lương/nhà cung cấp'],
        ['Tháng 9 chưa được chấm điểm',
         'Tệp phiếu thu chưa có số tháng 9, tệp chi phí chưa có tháng 8–9',
         'Phiếu giao KPI tháng 9 đã có nhưng chưa có số thực hiện',
         'Gửi số liệu tháng 9 rồi làm theo mục E3 (lấy số và xác nhận)'],
    ]


def irregularity_rows(source):
    kinds = {'vat': 'VAT không đúng 8%', 'both': 'Vừa đã xuất HĐ vừa chưa xuất HĐ trong cùng tháng',
             'lump': 'Nghi hoá đơn gộp nhiều tháng', 'negative': 'Số âm (điều chỉnh giảm)'}
    return [[f"Tháng {issue['month']}", issue['partner'], kinds.get(issue['kind'], issue['kind']),
             issue['text']] for issue in source['irregularities']]


def result_places_rows(data):
    """Where a result is written, and the menu that shows it."""
    reviews = len(data['reviews'])
    return [
        ['Kết quả theo kỳ', 'Số thực hiện từng tháng của từng chỉ tiêu, nguồn lấy số, trạng thái, '
         'người và thời điểm xác nhận', 'Hiệu suất › Thực hiện › Kết quả theo kỳ',
         f"{data['confirmed']} bản ghi đã xác nhận"],
        ['Chỉ tiêu KPI', 'Thực hiện cả kỳ, % đạt, đèn RAG, nút mở lịch sử số liệu',
         'Hiệu suất › Kế hoạch › Chỉ tiêu KPI', f"{data['targets']} chỉ tiêu"],
        ['Phiếu giao KPI', 'Điểm, điểm trên KPI có số liệu, độ phủ dữ liệu, trạng thái phiếu',
         'Hiệu suất › Kế hoạch › Bảng điểm cá nhân',
         f"{sum(len(c) for c in data['cards'].values())} phiếu"],
        ['Mục tiêu và kết quả then chốt', 'Điểm OKR của phòng, độ phủ, lịch sử check-in',
         'Hiệu suất › Kế hoạch › Mục tiêu / Kết quả then chốt',
         f"{len(data['objectives'])} mục tiêu · {len(data['krs'])} KR"],
        ['Vết kiểm toán số thực hiện', 'Mọi lần nhập / xác nhận / sửa / huỷ xác nhận / xoá, kèm '
         'người, thời điểm, số trước, số sau và lý do', 'Hiệu suất › Báo cáo › Vết kiểm toán số thực hiện',
         f"{data['audit_events']} sự kiện"],
        ['Báo cáo bảng điểm phòng ban', 'Điểm bình quân của phòng theo chu kỳ, kèm độ phủ và điểm OKR quý',
         'Hiệu suất › Báo cáo › Bảng điểm phòng ban', f"{len(data['department_report'])} dòng"],
        ['Phiếu đánh giá quý', 'Điểm KPI đã chốt, tự đánh giá, quản lý đánh giá, xếp loại 9 ô',
         'Đánh giá › Phiếu đánh giá', f'{reviews} phiếu'],
        ['Điều chỉnh chỉ tiêu', 'Mọi lần sửa chỉ tiêu đã duyệt: số cũ, số mới, lý do, người duyệt',
         'Hiệu suất › Cấu hình › Điều chỉnh chỉ tiêu', 'ghi khi có điều chỉnh'],
    ]


def audit_sample_rows(data):
    labels = data['audit_labels']
    rows = []
    for event in data['audit_sample']:
        rows.append([event['event_date'], event['kpi_target_id'][1],
                     labels.get(event['action'], event['action']),
                     vn(event['old_actual']), vn(event['new_actual']),
                     event['user_id'][1], (event['reason'] or '')[:120]])
    return rows


def control_rows(data):
    """The gates that stand between a figure and a score."""
    return [
        ['Chỉ số đã xác nhận mới được tính điểm',
         'Số vừa lấy về là bản nháp; phải có người xác nhận mới vào điểm',
         'Quản lý hiệu suất (trưởng phòng)'],
        ['Xác nhận luôn được đóng dấu người và thời điểm',
         f"Hiện trên danh sách Kết quả theo kỳ; {data['confirmed'] - data['unstamped']}"
         f"/{data['confirmed']} bản ghi đã có dấu", 'Hệ thống tự ghi'],
        ['Không thể xác nhận bằng đường khác',
         'Kể cả sửa trực tiếp qua giao diện kỹ thuật, hệ thống vẫn đòi quyền quản lý',
         'Quản lý hiệu suất'],
        ['Số đã xác nhận không sửa, không xoá được',
         'Muốn sửa phải huỷ xác nhận trước — vì điểm đang dựa trên số đó',
         'Quản lý hiệu suất'],
        ['Huỷ xác nhận phải nêu lý do',
         'Lý do được lưu trong vết kiểm toán và ghi lên chính KPI đó',
         'Quản lý hiệu suất'],
        ['Vết kiểm toán không ai sửa hay xoá được',
         'Kể cả quản trị viên hệ thống; mỗi sự kiện có mã kiểm tra toàn vẹn',
         'Không ai'],
        ['Kỳ phải nằm trong chu kỳ của chỉ tiêu',
         'Chặn số liệu ghi sai tháng làm điểm lệch mà không ai thấy', 'Hệ thống tự chặn'],
        ['Chỉ tiêu đã duyệt chỉ đổi qua Yêu cầu điều chỉnh',
         'Có số cũ, số mới, lý do và người duyệt', 'Quản lý hiệu suất duyệt'],
        ['Điểm KPI của phiếu đánh giá được chốt ảnh',
         'Khi phiếu vào chặng quản lý, điểm được đóng băng kèm người và thời điểm chốt',
         'Quản lý hiệu suất'],
        ['Không chốt đánh giá trên số còn trôi',
         'Phiếu chưa chốt điểm KPI thì không cho chuyển sang chặng cuối', 'Hệ thống tự chặn'],
    ]


def review_rows(data):
    rows = []
    for review in data['reviews']:
        rows.append([
            review['employee_id'][1], review['stage_id'][1] if review['stage_id'] else '',
            f"{vn(100 * review['goal_score_live'], 1)}%",
            f"{vn(100 * review['goal_score'], 1)}%" if review['goal_score_snapshot_on'] else 'chưa chốt',
            f"{vn(review['goal_coverage_live'], 1)}%",
            review['goal_score_snapshot_by'][1] if review['goal_score_snapshot_by'] else '',
            review['goal_score_snapshot_on'] or '',
        ])
    return rows


def department_report_rows(data):
    rows = []
    for row in sorted(data['department_report'], key=lambda row: row['cycle_id'][1]):
        rows.append([
            row['cycle_id'][1], row['employee_count'],
            f"{vn(100 * row['avg_composite'], 1)}%",
            f"{vn(100 * row['avg_score_covered'], 1)}%",
            f"{vn(row['avg_data_coverage'], 1)}%",
            f"{vn(100 * row['avg_objective_score'], 1)}%",
            row['objective_cycle_id'][1] if row['objective_cycle_id'] else '—',
        ])
    return rows


def okr_rows(data):
    rows = []
    by_objective = {}
    for kr in data['krs']:
        by_objective.setdefault(kr['objective_id'][0], []).append(kr)
    for objective in data['objectives']:
        rows.append([
            Raw(f'<td class="strong">{esc(objective["code"])}</td>'),
            Raw(f'<td class="strong">{esc(objective["name"])}</td>'),
            cell(f'{vn(objective["weight"], 0)}%'), cell(''), cell(''),
            cell(f'{vn(100 * objective["score"], 1)}%'),
            cell(f'độ phủ {vn(objective["data_coverage"], 0)}%'),
        ])
        for kr in by_objective.get(objective['id'], []):
            target = ('theo mốc công việc' if kr['metric_type'] == 'milestone'
                      else f"{vn(kr['target'])} {kr['unit'] or ''}".strip())
            actual = ('—' if not kr['has_actual'] else
                      ('đã ghi nhận' if kr['metric_type'] == 'milestone'
                       else f"{vn(kr['current'])} {kr['unit'] or ''}".strip()))
            rows.append([
                cell(kr['code']), cell(kr['name']), cell(f'{vn(kr["weight"], 0)}%'),
                cell(target), cell(actual), cell(f'{vn(100 * kr["score"], 1)}%'),
                Raw('<td>' + ('có số liệu' if kr['has_actual']
                              else '<span class="muted">chưa có số liệu</span>') + '</td>'),
            ])
    return rows


def kr_rows(data):
    measure = {'number': 'theo số', 'percent': 'theo %', 'milestone': 'theo mốc công việc',
               'boolean': 'đạt / không đạt'}
    rows = []
    for kr in data['krs']:
        milestones = [m for m in data['milestones'] if m['kr_id'][0] == kr['id']]
        done = sum(1 for m in milestones if m['is_done'])
        rows.append([
            kr['code'], kr['name'], f'{vn(kr["weight"], 0)}%',
            measure.get(kr['metric_type'], kr['metric_type']),
            f"{vn(kr['target'])} {kr['unit'] or ''}".strip() if kr['metric_type'] != 'milestone' else '—',
            f"{vn(kr['current'])} {kr['unit'] or ''}".strip() if kr['has_actual'] and kr['metric_type'] != 'milestone'
            else ('—' if not kr['has_actual'] else 'đã ghi nhận'),
            kr['deadline'] or '',
            f'{done}/{len(milestones)} hoàn thành' if milestones else '—',
        ])
    return rows


def all_line_rows(data):
    rows = []
    for month in sorted(data['cards']):
        for card in data['cards'][month]:
            for row in line_rows(data, card):
                rows.append([cell(f'T{month}/2026'), cell(card['employee_id'][1])] + list(row))
    return rows


def example_explanation(data, card):
    """Say what this particular scorecard means - the three cases read
    differently, and the reader must not take a 0 % for a bad result."""
    if not card['data_coverage']:
        return ('Toàn bộ chỉ tiêu của người này nằm ngoài sổ kế toán (sản lượng nội dung, tỷ lệ duyệt…), '
                'nên hệ thống chưa có số để chấm. Điểm 0% ở đây <b>không phải là kết quả kém</b> — '
                'độ phủ dữ liệu 0% nói rõ là chưa đo. Nhập số theo mục E4 là điểm hiện ngay.')
    missing = vn(100 - card['data_coverage'], 0)
    if card['score_covered'] >= 0.999:
        return (f'Phần đã đo được đạt trọn vẹn (100%); {missing}% trọng số còn lại chưa có số nên chưa chấm. '
                'Vì vậy con số nên đọc là “đạt 100% trên phần đo được”, chứ không phải “mất điểm”.')
    weakest = min(((line, data['targets'][line['kpi_target_id'][0]])
                   for line in data['lines'][card['id']] if line['has_actual']),
                  key=lambda pair: pair[0]['score'])
    return (f'Các dòng đã có số được chấm thật: thấp nhất là “{esc(weakest[1]["kpi_id"][1])}” '
            f'({vn(100 * weakest[0]["score"], 1)}% — thực hiện {vn(weakest[1]["actual_value"])} so với chỉ tiêu '
            f'{vn(weakest[1]["target_value"])}). Còn {missing}% trọng số chưa có số liệu nên chưa chấm; '
            'khi nhập đủ số, điểm sẽ thay đổi.')


def example_block(data, name, month, note):
    card = card_of(data, name, month)
    covered = 'chưa có dòng nào có số liệu' if not card['data_coverage'] else (
        f"điểm trên KPI có số liệu <b>{vn(100 * card['score_covered'], 1)}%</b>")
    explain = example_explanation(data, card)
    return f"""
<div class="example">
<h3>{esc(name)} — tháng {month}/2026</h3>
<p class="lead">{esc(note)} · Vị trí: {esc(card['job_note'] or '')}</p>
<p>Điểm <b>{vn(100 * card['score'], 1)}%</b> · {covered} · độ phủ dữ liệu
<b>{vn(card['data_coverage'], 1)}%</b> · tổng trọng số {vn(card['total_weight'], 0)}%.</p>
{table(['Nhóm KPI', 'Chỉ tiêu KPI', 'Chỉ tiêu giao', 'Trọng số', 'Thực hiện', 'Đạt'], line_rows(data, card))}
<p class="note">{explain}</p>
</div>"""


STYLE = """
:root { --ink:#16202b; --muted:#6b7a8d; --line:#dfe6ee; --bg:#f4f7fb; --card:#fff; --accent:#1c4f8a;
        --okbg:#e6f5ec; --warnbg:#fdf2dd; }
* { box-sizing:border-box; }
body { margin:0; padding:24px 16px 64px; background:var(--bg); color:var(--ink);
       font:16px/1.7 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
main { max-width:1080px; margin:0 auto; }
h1 { font-size:1.65rem; margin:0 0 6px; }
h2 { font-size:1.25rem; margin:40px 0 10px; padding:10px 0 0; border-top:3px solid var(--accent); }
h3 { font-size:1.05rem; margin:24px 0 6px; color:var(--accent); }
p, li { margin:8px 0; }
.lead { color:var(--muted); }
.cards { display:grid; gap:12px; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); margin:16px 0; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.kpi b { display:block; font-size:1.45rem; line-height:1.2; }
.kpi span { color:var(--muted); font-size:.88rem; }
.toc { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px 16px; }
.toc ol { margin:8px 0 0; padding-left:20px; }
.toc a { color:var(--accent); text-decoration:none; }
.flow { display:grid; gap:10px; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); margin:12px 0; }
.flow div { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--accent);
            border-radius:10px; padding:10px 12px; }
.flow b { display:block; }
.flow span { color:var(--muted); font-size:.9rem; }
.scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; margin:10px 0; }
table { width:100%; border-collapse:collapse; background:var(--card); font-size:.94rem; }
th, td { padding:8px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
th { background:#e9f0f8; font-weight:600; white-space:nowrap; }
td.strong, .strong td { font-weight:600; background:#f4f8fd; }
table.trail th { width:190px; background:#e9f0f8; }
.muted { color:var(--muted); }
.note { color:var(--muted); font-size:.92rem; margin:6px 0 0; }
td.ok { color:#1f7a4d; }
td.bad { background:#fde8e8; color:#a3262c; font-weight:600; }
h4 { font-size:.98rem; margin:18px 0 4px; }
.callout { background:var(--okbg); border-left:4px solid #1f7a4d; border-radius:8px; padding:10px 14px; }
.missing { background:var(--warnbg); border-left:4px solid #8a5a00; padding:10px 14px; border-radius:8px; }
.example { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:4px 16px 12px; margin:16px 0; }
figure { margin:16px 0; }
figure img { width:100%; height:auto; border:1px solid var(--line); border-radius:10px; display:block; }
figcaption { color:var(--muted); font-size:.9rem; margin-top:6px; }
code { background:#e9f0f8; padding:1px 5px; border-radius:5px; font-size:.9em; }
ol, ul { padding-left:22px; }
footer { color:var(--muted); font-size:.9rem; margin-top:40px; border-top:1px solid var(--line); padding-top:12px; }
@media (max-width:600px) { body { padding:16px 12px 48px; } h1 { font-size:1.3rem; }
  table { font-size:.88rem; } table.trail th { width:auto; } }
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--url', default='https://okr.aipower.vn')
    parser.add_argument('--db', default='okr_aipower')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default=os.environ.get('OKR_ADMIN_PASSWORD'))
    parser.add_argument('--source', default=str(DEFAULT_SOURCE_DATA),
                        help='dataset read from the customer files (tools/extract_kddv_actuals.py)')
    parser.add_argument('--images', default=str(DEFAULT_IMAGES))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    parser.add_argument('--keep-old', action='store_true',
                        help='keep the earlier overview page instead of deleting it')
    args = parser.parse_args(argv)
    if not args.password:
        parser.error('pass --password or set OKR_ADMIN_PASSWORD')
    client = Client(args.url, args.db, args.user, args.password)
    data = collect(client)
    generated = datetime.datetime.now().strftime('%d/%m/%Y %H:%M')
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    source = json.loads(pathlib.Path(args.source).read_text(encoding='utf-8'))
    out.write_text(render(data, source, pathlib.Path(args.images), generated), encoding='utf-8', newline='\n')
    print('%s (%.1f MB)' % (out, out.stat().st_size / 1e6))
    if not args.keep_old and OLD_PAGE.exists():
        OLD_PAGE.unlink()
        print('đã xoá tài liệu cũ %s' % OLD_PAGE.name)


if __name__ == '__main__':
    main()
