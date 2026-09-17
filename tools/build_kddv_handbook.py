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
import importlib.util
import os
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'build_kddv_evaluation', _REPO / 'tools' / 'build_kddv_evaluation.py')
_evaluation = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_evaluation)
Client, vn = _evaluation.Client, _evaluation.vn

DEFAULT_OUT = _REPO / 'Docs' / 'OKR' / 'Cam_nang_OKR_KPI_KDDV_Q3_2026.html'
DEFAULT_IMAGES = _REPO / 'Docs' / 'OKR' / 'img_kddv'
OLD_PAGE = _REPO / 'Docs' / 'OKR' / 'Mo_ta_du_lieu_OKR_KDDV.html'
DEPARTMENT = 'Kinh doanh và Dịch vụ'
MONTHS = {7: 'KDDV-2026-07', 8: 'KDDV-2026-08', 9: 'KDDV-2026-09'}
SCORED = (7, 8)
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
    '12-department-report': 'Báo cáo bảng điểm phòng ban: điểm trung bình của phòng theo từng chu kỳ.',
}

SECTIONS = [
    ('A', 'Số liệu của đơn vị đi vào hệ thống như thế nào'),
    ('B', 'Hệ thống đang có những gì (kèm số thật)'),
    ('C', 'Đọc kỹ ba phiếu giao KPI'),
    ('D', 'Việc phải làm hằng tháng với dữ liệu hiện tại'),
    ('E', 'Đánh giá hiệu suất được tính thế nào'),
    ('F', 'Việc cần đơn vị cung cấp thêm'),
    ('G', 'Phụ lục: toàn bộ dữ liệu đang có'),
]


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
            ['employee_id', 'job_note', 'score', 'score_covered', 'data_coverage', 'total_weight',
             'line_ids', 'group_ids', 'state'], order='employee_id', context=VI)
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


def render(data, images, generated):
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

<h2 id="B">B. Hệ thống đang có những gì (kèm số thật)</h2>
<h3>B1. Người và tổ chức</h3>
<p>{len(data['departments'])} phòng ban; nhân sự chi tiết của Phòng {esc(DEPARTMENT)}: <b>{len(data['staff'])} người</b>,
mỗi người một tài khoản đăng nhập ({data['users']} tài khoản nội bộ).</p>
{table(['Mã NV', 'Họ và tên', 'Chức danh', 'Tài khoản đăng nhập', 'Quản lý trực tiếp'],
       [[s['barcode'] or '', s['name'], s['job_title'] or '', s['work_email'] or '',
         s['parent_id'][1] if s['parent_id'] else ''] for s in data['staff']])}

<h3>B2. Chu kỳ đánh giá</h3>
{table(['Mã', 'Tên', 'Loại', 'Từ ngày', 'Đến ngày', 'Thuộc chu kỳ', 'Trạng thái'],
       [[c['code'], c['name'], data['labels']['cycle_type'].get(c['cycle_type'], c['cycle_type']),
         c['date_start'], c['date_end'], c['parent_id'][1] if c['parent_id'] else '—',
         data['labels']['state'].get(c['state'], c['state'])] for c in data['cycles']],
       'Phiếu giao KPI gắn với chu kỳ tháng; OKR của phòng gắn với chu kỳ quý.')}

<h3>B3. OKR quý III/2026 của phòng</h3>
<p>Đúng nguyên văn Phụ lục 5 của Quyết định giao nhiệm vụ trọng tâm. “Độ phủ dữ liệu” cho biết phần trọng số
đã có số thực hiện — phần còn lại chưa có số nên chưa chấm, <b>không bị tính 0 điểm</b>.</p>
{table(['Mã', 'Nội dung', 'Trọng số', 'Chỉ tiêu quý', 'Thực hiện', 'Điểm', 'Số liệu'], okr_rows(data))}
{picture('06-objective-form')}

<h3>B4. Phiếu giao KPI theo tháng</h3>
{table(['Tháng', 'Số phiếu', 'Số dòng KPI', 'Dòng đã có số thực hiện', 'Số phiếu có ít nhất một số thực hiện'],
       [[f'Tháng {month}/2026', len(cards),
         sum(len(data['lines'][c['id']]) for c in cards),
         sum(1 for c in cards for line in data['lines'][c['id']] if line['has_actual']),
         sum(1 for c in cards if c['data_coverage'])] for month, cards in sorted(data['cards'].items())],
       f'Tổng {lines_total} dòng KPI, trong đó {lines_measured} dòng đã có số thực hiện lấy từ sổ kế toán.')}
{picture('01-scorecard-list')}

<h3>B5. Chứng từ kế toán đang có</h3>
{table(['Tháng', 'Số hoá đơn', 'Doanh thu chưa VAT', 'Thuế GTGT'],
       [[month, entry['count'], money(entry['untaxed']), money(entry['tax'])]
        for month, entry in sorted(invoices_by_month.items())],
       'Phần doanh thu đã thực hiện nhưng chưa xuất hoá đơn được ghi bằng bút toán dự thu (bảng dưới).')}
{table(['Tham chiếu', 'Số bút toán', 'Ngày', 'Sổ nhật ký', 'Giá trị'],
       [[e['ref'], e['name'], e['date'], e['journal_id'][1], money(e['amount_total'])] for e in data['entries']])}

<h3>B6. Chỉ số theo dõi của phòng (không chấm điểm)</h3>
{table(['Kỳ', 'Chỉ số', 'Đơn vị', 'Giá trị'],
       [[t['cycle_id'][1], t['kpi_id'][1], t['unit'] or '',
         vn(t['actual_value']) if t['has_actual'] else 'chưa có số liệu']
        for t in sorted(data['tracking'], key=lambda t: (t['cycle_id'][1], t['kpi_id'][1]))],
       'Chi phí và lợi nhuận gộp lấy từ sổ kế toán, chỉ để lãnh đạo theo dõi; không có trọng số nên '
       'không ảnh hưởng điểm của bất kỳ ai.')}

<h2 id="C">C. Đọc kỹ ba phiếu giao KPI</h2>
<p>Ba phiếu dưới đây của cùng tháng 7/2026, cho thấy ba tình huống hay gặp nhất.</p>
{''.join(example_block(data, name, month, note) for name, month, note in EXAMPLES)}
{picture('02-scorecard-form')}

<h2 id="D">D. Việc phải làm hằng tháng với dữ liệu hiện tại</h2>
<p>Với cách dữ liệu đang được tổ chức, mỗi tháng chỉ có <b>hai nhóm việc</b>: nhập số của tháng vào đúng chỗ,
rồi xác nhận để hệ thống tính điểm.</p>

<h3>D1. Doanh thu của tháng → hoá đơn bán hàng</h3>
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

<h3>D2. Chi phí của tháng → bút toán chi phí</h3>
<ol>
<li>Mở <b>Hoá đơn › Kế toán › Bút toán</b>, bấm <b>Mới</b>, chọn sổ <b>Chi phí tổng hợp</b>,
ngày = ngày cuối tháng, tham chiếu <code>CPTH2026-T&lt;tháng&gt;</code>.</li>
<li>Mỗi dòng trong sổ chi phí là một dòng bút toán: chọn <b>tài khoản</b> đúng mã (622111, 62752…),
ghi số vào cột <b>Nợ</b>.</li>
<li>Dòng cuối ghi <b>Có</b> tài khoản <b>3388</b> bằng tổng chi phí tháng (khoản chờ kế toán phân bổ).</li>
<li>Bấm <b>Vào sổ</b>.</li>
</ol>
{picture('10-cost-entry')}

<h3>D3. Đưa số vào KPI rồi xác nhận</h3>
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

<h3>D4. Các KPI không nằm trong sổ kế toán</h3>
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

<h2 id="E">E. Đánh giá hiệu suất được tính thế nào</h2>
<h3>E1. Từ số thực hiện đến % đạt của một dòng KPI</h3>
<ul>
<li><b>Chỉ tiêu càng cao càng tốt</b> (doanh thu, MAU…): % đạt = thực hiện ÷ chỉ tiêu.
Ví dụ thật: {esc(tp_target['kpi_id'][1])} tháng 7 — {vn(tp_target['actual_value'])} ÷
{vn(tp_target['target_value'])} → chặn trần <b>100%</b>.</li>
<li><b>Chỉ tiêu càng thấp càng tốt</b> (churn ≤ 8%, CAC ≤ 15.000đ): % đạt = 2 − thực hiện ÷ chỉ tiêu,
đúng bằng chỉ tiêu thì 100%, vượt quá thì giảm dần.</li>
<li><b>Chỉ tiêu “không được xảy ra”</b> (0 vụ vi phạm bản quyền): 0 vụ = 100%, có vụ = 0%.</li>
<li>Điểm mỗi dòng không vượt <b>100%</b> (trần điểm của chu kỳ), nên vượt kế hoạch nhiều cũng không bù cho dòng khác.</li>
</ul>

<h3>E2. Từ các dòng KPI đến điểm của một người</h3>
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

<h3>E3. Điểm của phòng (OKR)</h3>
<p>Mỗi kết quả then chốt có điểm riêng (theo số thực hiện, hoặc theo tỷ lệ mốc công việc đã hoàn thành).
Điểm mục tiêu = bình quân theo trọng số các KR của nó; điểm quý của phòng = bình quân theo trọng số các mục tiêu.
Hiện tại O1 có {vn(data['objectives'][0]['data_coverage'], 0)}% độ phủ dữ liệu vì phần doanh thu đã có số,
các mục tiêu còn lại chờ số liệu ngoài sổ kế toán.</p>

<h3>E4. Quy trình chốt và sửa chỉ tiêu</h3>
<ol>
<li>Phiếu giao KPI đi theo bốn trạng thái: <b>Nháp → Đã nộp → Đã duyệt → Hoàn tất</b>. Hệ thống chỉ cho nộp
khi tổng trọng số đúng 100% (kể cả từng nhóm), nên không thể chốt một phiếu giao sai trọng số.</li>
<li>Sau khi chỉ tiêu đã duyệt, muốn sửa chỉ tiêu/trọng số phải dùng nút <b>Yêu cầu điều chỉnh chỉ tiêu</b>
trên chỉ tiêu KPI, mục tiêu hoặc kết quả then chốt — người có thẩm quyền duyệt thì số mới có hiệu lực,
và hệ thống lưu lý do. Đây là vết kiểm soát khi đánh giá cuối quý.</li>
<li>Cuối tháng: xác nhận số thực hiện (mục D3) → xem lại điểm và độ phủ → nộp và duyệt phiếu.</li>
<li>Cuối quý: cập nhật các kết quả then chốt (check-in), đối chiếu điểm phòng, xuất báo cáo.</li>
</ol>

<h3>E5. Xem kết quả ở đâu</h3>
<ul>
<li><b>Hiệu suất › Kế hoạch › Bảng điểm cá nhân</b> — điểm, điểm trên phần có số liệu, độ phủ của từng người.</li>
<li><b>Hiệu suất › Báo cáo › Bảng điểm phòng ban</b> — điểm trung bình của phòng theo chu kỳ.</li>
<li><b>Hiệu suất › Báo cáo › Tiến độ so với kế hoạch</b> — thực hiện so với kế hoạch theo thời gian.</li>
<li>Bản đánh giá chi tiết quý III (T7–T8) trong tệp Excel <code>Danh_gia_KDDV_Q3_2026_T7-T8.xlsx</code> gửi kèm.</li>
</ul>
{picture('12-department-report')}

<h2 id="F">F. Việc cần đơn vị cung cấp thêm</h2>
<ol>
<li>Doanh thu tháng 9/2026 và chi phí tháng 8–9/2026 (hai tệp đã gửi chưa có).</li>
<li>Xác nhận phần “đã thực hiện chưa xuất hoá đơn” của tháng 8 thuộc tháng nào: nhiều đối tác có cả hai phần
gần bằng nhau.</li>
<li>Xác nhận các hoá đơn gộp nhiều tháng ghi ở tháng 7 (VNPT, VTVshop MG).</li>
<li>Số thực hiện cho các KPI ngoài doanh thu (mục D4) — hiện {lines_total - lines_measured} dòng đang chờ.</li>
<li>Phân bổ tài khoản trung gian <b>3388</b> về lương, nhà cung cấp… theo sổ kế toán thật.</li>
</ol>

<h2 id="G">G. Phụ lục: toàn bộ dữ liệu đang có</h2>
<h3>G1. Kết quả then chốt và mốc công việc</h3>
{table(['Mã', 'Kết quả then chốt', 'Trọng số', 'Cách đo', 'Chỉ tiêu', 'Thực hiện', 'Hạn', 'Mốc công việc'],
       kr_rows(data))}
<h3>G2. Toàn bộ dòng KPI của {sum(len(c) for c in data['cards'].values())} phiếu giao</h3>
{table(['Tháng', 'Người', 'Nhóm', 'KPI', 'Chỉ tiêu giao', 'Trọng số', 'Thực hiện', 'Đạt'], all_line_rows(data),
       'Bảng này là toàn bộ nội dung các phiếu giao KPI đang có trong hệ thống.')}
<h3>G3. Hoá đơn doanh thu đã vào sổ</h3>
{table(['Tham chiếu', 'Số hoá đơn', 'Ngày', 'Đối tác', 'Chưa VAT', 'Thuế'],
       [[m['ref'], m['name'], m['invoice_date'], m['partner_id'][1], money(m['amount_untaxed']), money(m['amount_tax'])]
        for m in data['invoices']])}
<h3>G4. Nguồn lấy số từ sổ kế toán</h3>
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
                'độ phủ dữ liệu 0% nói rõ là chưa đo. Nhập số theo mục D4 là điểm hiện ngay.')
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
    out.write_text(render(data, pathlib.Path(args.images), generated), encoding='utf-8', newline='\n')
    print('%s (%.1f MB)' % (out, out.stat().st_size / 1e6))
    if not args.keep_old and OLD_PAGE.exists():
        OLD_PAGE.unlink()
        print('đã xoá tài liệu cũ %s' % OLD_PAGE.name)


if __name__ == '__main__':
    main()
