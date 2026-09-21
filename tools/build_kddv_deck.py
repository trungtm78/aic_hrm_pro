# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Write the progress report the customer presents in their review meeting.

Three files out of one description: a PowerPoint deck, the same deck as a PDF
for people who only open mail attachments, and every chart again as a PNG so
they can drop one into a report of their own. Nothing is converted from
anything - neither PowerPoint nor LibreOffice is installed on the build
machine - so the three renderers read the same slide list instead.

The load-bearing rule, and the reason the three outputs can never disagree:

    a number a human reads as text is a Vietnamese-formatted string produced
    in `facts()`; a number a chart draws is a raw float (or None for "no
    figures yet") carried in a Series. A renderer never formats and never
    parses.

Everything comes from the live instance over read-only JSON-RPC at build
time, the way the handbook does, so no figure in the deck can be stale or
typed by hand. The pictures come from `uat/capture_kddv_guide.mjs`; a missing
one stops the build rather than leaving a hole in a customer deck.

Run:  set OKR_ADMIN_PASSWORD=... && python tools/build_kddv_deck.py
      (needs python-pptx, matplotlib and reportlab: the Python 3.11 here has
      them. The slide content itself needs none of the three, so its tests
      run on any interpreter.)
"""
import argparse
import dataclasses
import datetime
import importlib.util
import json
import os
import pathlib
import re

_REPO = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    """Load a sibling tool as a module (they are scripts, not a package)."""
    spec = importlib.util.spec_from_file_location(name, _REPO / 'tools' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_handbook = _load('build_kddv_handbook')
_evaluation = _load('build_kddv_evaluation')
Client, vn = _evaluation.Client, _evaluation.vn
collect = _handbook.collect
DEPARTMENT = _handbook.DEPARTMENT
MONTHS = _handbook.MONTHS
MONTH_PLAN, QUARTER_PLAN = _evaluation.MONTH_PLAN, _evaluation.QUARTER_PLAN
VI = _handbook.VI

DEFAULT_OUT = _REPO / 'Docs' / 'OKR' / 'Reports' / 'Bao_cao_tien_do_KDDV_Q3_2026.pptx'
DEFAULT_CHARTS = _REPO / 'Docs' / 'OKR' / 'Reports' / 'charts'
DEFAULT_IMAGES = _handbook.DEFAULT_IMAGES
DEFAULT_SOURCE_DATA = _handbook.DEFAULT_SOURCE_DATA
DEFAULT_ENGAGEMENT = _REPO / 'uat' / 'data' / 'kddv_engagement.json'

# ---------------------------------------------------------------- palette --
# The design tokens are authored in OKLCH (tokens.css); PowerPoint, matplotlib
# and reportlab all want sRGB. Converted here rather than copied, so the deck
# cannot drift away from the colours on screen.
TOKENS = {
    'accent': (0.45, 0.14, 235.0),
    'accent_hi': (0.48, 0.20, 235.0),
    'green': (0.60, 0.13, 150.0),
    'amber': (0.72, 0.14, 75.0),
    'red': (0.55, 0.18, 25.0),
    'ink': (0.20, 0.010, 235.0),
    'ink2': (0.40, 0.010, 235.0),
    'muted': (0.50, 0.010, 235.0),
    'rule': (0.88, 0.008, 235.0),
    'paper': (0.98, 0.005, 235.0),
    'paper2': (0.95, 0.006, 235.0),
    'paper3': (0.92, 0.008, 235.0),
}


def oklch_to_rgb(lightness, chroma, hue):
    """OKLCH -> sRGB hex, the conversion Björn Ottosson published with Oklab.

    Written out rather than pulled from a library: the deck must build with
    nothing but the standard library plus the three rendering packages.
    """
    import math
    hue_rad = math.radians(hue)
    a = chroma * math.cos(hue_rad)
    b = chroma * math.sin(hue_rad)
    l_ = lightness + 0.3963377774 * a + 0.2158037573 * b
    m_ = lightness - 0.1055613458 * a - 0.0638541728 * b
    s_ = lightness - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    linear = (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    channels = []
    for value in linear:
        # sRGB transfer function, then clip: a token slightly outside the
        # monitor gamut must still give a usable colour, not an exception.
        srgb = (1.055 * (value ** (1 / 2.4)) - 0.055) if value > 0.0031308 else 12.92 * value
        channels.append(max(0, min(255, round(srgb * 255))))
    return '%02X%02X%02X' % tuple(channels)


RGB = {name: oklch_to_rgb(*value) for name, value in TOKENS.items()}
HEX = {name: '#' + value for name, value in RGB.items()}
RAG_TONE = {'green': 'green', 'amber': 'amber', 'red': 'red', 'none': 'muted', False: 'muted'}

# --------------------------------------------------------------- geometry --
# Inches, converted per backend. PowerPoint's canonical 16:9 is 12192000 x
# 6858000 EMU; Inches(13.333) lands 240 EMU short and makes PowerPoint ask
# the customer about a "different slide size" when they paste into their own
# template.
SLIDE_W, SLIDE_H = 13.333333, 7.5
SLIDE_EMU = (12192000, 6858000)
MARGIN = 0.62
BODY_TOP, BODY_BOTTOM = 1.62, 6.9
MAX_TABLE_ROWS = 11
CHART_SIZE = (9.6, 4.9)          # inches; every PNG is rendered at this aspect

KINDS = ('cover', 'section', 'bullets', 'kpis', 'table', 'chart', 'chart_table',
         'picture', 'picture_bullets', 'close')


# ------------------------------------------------------------ slide model --
@dataclasses.dataclass(frozen=True)
class Series:
    """One line or one set of bars. `None` is a gap - never a zero."""
    name: str
    values: tuple = ()
    colour: str = 'accent'
    kind: str = 'column'
    labels: bool = True
    point_colours: tuple = ()


@dataclasses.dataclass(frozen=True)
class Chart:
    key: str                      # ascii slug, also the PNG file name
    kind: str                     # column | stacked | bar | line | combo | doughnut
    title: str
    categories: tuple = ()
    series: tuple = ()
    unit: str = ''
    decimals: int = 1
    note: str = ''
    native: bool = True           # False: even the .pptx gets the picture


@dataclasses.dataclass(frozen=True)
class Table:
    headers: tuple = ()
    rows: tuple = ()
    align: str = ''
    widths: tuple = ()
    note: str = ''


@dataclasses.dataclass(frozen=True)
class Picture:
    name: str
    caption: str


@dataclasses.dataclass(frozen=True)
class Kpi:
    value: str
    label: str
    tone: str = 'accent'
    note: str = ''


@dataclasses.dataclass(frozen=True)
class Slide:
    kind: str
    title: str = ''
    lead: str = ''
    bullets: tuple = ()
    kpis: tuple = ()
    table: Table = None
    chart: Chart = None
    picture: Picture = None
    footnote: str = ''


def visible_strings(slides):
    """Every piece of text the customer can read, wherever it sits.

    Walks the dataclass fields instead of naming them, so a field added later
    is checked by the same tests without anybody remembering to list it.
    """
    seen = []

    def walk(value):
        if isinstance(value, str):
            seen.append(value)
        elif dataclasses.is_dataclass(value):
            for field in dataclasses.fields(value):
                walk(getattr(value, field.name))
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(list(slides))
    return seen


def charts_of(slides):
    return [slide.chart for slide in slides if slide.chart]


def pictures_of(slides):
    return [slide.picture for slide in slides if slide.picture]


def percent(value, decimals=1):
    """A 0..1 score as Vietnamese percent text."""
    return vn(100.0 * (value or 0.0), decimals) + '%'


def share(value, decimals=1):
    """A 0..100 share (coverage) as Vietnamese percent text."""
    return vn(value or 0.0, decimals) + '%'


def billions(value, decimals=2):
    """Đồng -> tỷ đồng, the unit the customer talks in."""
    return vn((value or 0.0) / 1e9, decimals)


MONTH_LABEL = {month: f'Tháng {month}' for month in range(1, 13)}
AUTOMATIC = 'Tự động từ sổ kế toán'
BY_HAND = 'Người phụ trách nhập'


def _revenue_by_month(data):
    """Revenue recognised per month, in tỷ: every 5113 account, invoices and
    the accrual alike - that is what the score reads."""
    totals = {}
    for (month, _code), amount in data['ledger_by_account'].items():
        totals[month] = totals.get(month, 0.0) + amount
    return {month: value / 1e9 for month, value in sorted(totals.items()) if abs(value) > 1.0}


def _invoiced_by_month(data):
    totals = {}
    for invoice in data['invoices']:
        month = int(invoice['invoice_date'][5:7])
        totals[month] = totals.get(month, 0.0) + invoice['amount_untaxed']
    return {month: value / 1e9 for month, value in sorted(totals.items())}


def _cost_by_month(data):
    return {month: value / 1e9 for month, value in sorted(data['ledger_cost'].items())
            if abs(value) > 1.0}


PREFIXES = (('Công ty Cổ phần', 'CTCP'), ('Công ty cổ phần', 'CTCP'),
            ('Công ty TNHH', 'Công ty TNHH'), ('Tổng Công ty', 'TCT'),
            ('Tổng công ty', 'TCT'), ('CÔNG TY CỔ PHẦN', 'CTCP'))


def short_name(name, limit=34):
    """A partner name that fits on a chart and is still recognisable.

    Full legal names run past the edge of the picture and lose their first
    words, which is where the company's actual name usually is not - the
    prefix is. Shorten the prefix, then cut the tail if it is still too long.
    """
    text = name.strip()
    for prefix, short in PREFIXES:
        if text.startswith(prefix):
            text = short + text[len(prefix):]
            break
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def _revenue_by_partner(data, top=10):
    totals = {}
    for (_month, partner), amount in data['ledger_by_partner'].items():
        totals[partner] = totals.get(partner, 0.0) + amount
    ranked = sorted(totals.items(), key=lambda item: -item[1])
    return [(short_name(name), value / 1e9) for name, value in ranked[:top]], len(ranked)


def _scorecard_month(data, month):
    """What one month's scorecards say, read the way the leadership desk
    reads them: the score over the people who have figures, with the coverage
    beside it. Averaged over everybody, a month where most figures are still
    missing reads as a collapse instead of as a gap."""
    cards = data['cards'][month]
    measured = [card for card in cards if card['data_coverage'] > 0]
    bands = {'green': 0, 'amber': 0, 'red': 0, 'none': 0}
    for card in cards:
        bands[card.get('rag') or 'none'] += 1
    return {
        'month': month,
        'label': MONTH_LABEL[month],
        'cards': len(cards),
        'measured': len(measured),
        'waiting': len(cards) - len(measured),
        'score_covered': (sum(card['score_covered'] for card in measured) / len(measured)
                          if measured else None),
        'coverage': (sum(card['data_coverage'] for card in cards) / len(cards)) if cards else 0.0,
        'bands': bands,
    }


def _automation(data):
    """How much of the scorecard weight the system scores by itself, straight
    from the ledger, and how much still waits for somebody to report."""
    total = automatic = 0.0
    for lines in data['lines'].values():
        for line in lines:
            target = data['targets'].get(line['kpi_target_id'][0])
            if not target:
                continue
            total += line['weight']
            if target['metric_source_id']:
                automatic += line['weight']
    return {'total': total, 'automatic': automatic,
            'share': (100.0 * automatic / total) if total else 0.0}


def _example_card(data, month, card):
    """One person's scorecard, line by line, with where each figure comes
    from - the slide that answers "how is my score worked out?"."""
    rows = []
    for line in data['lines'][card['id']]:
        target = data['targets'].get(line['kpi_target_id'][0], {})
        rows.append({
            'kpi': (target.get('kpi_id') or [0, ''])[1],
            'weight': line['weight'],
            'target': target.get('target_value'),
            'unit': target.get('unit') or '',
            'actual': target.get('actual_value') if target.get('has_actual') else None,
            'achievement': target.get('achievement') if target.get('has_actual') else None,
            'score': line['score'],
            'has_actual': bool(line['has_actual']),
            'source': AUTOMATIC if target.get('metric_source_id') else BY_HAND,
        })
    rows.sort(key=lambda row: -row['weight'])
    return {
        'name': card['employee_id'][1],
        'job': card.get('job_note') or '',
        'month': month,
        'label': MONTH_LABEL[month],
        'coverage': card['data_coverage'],
        'score_covered': card['score_covered'],
        'score': card['score'],
        'weight': card['total_weight'],
        'lines': rows,
        'measured_weight': sum(row['weight'] for row in rows if row['has_actual']),
    }


def _examples(data, month=7):
    """Two real scorecards: the one with the most figures behind it and the
    one with the fewest - the same rules, two very different pictures."""
    measured = [card for card in data['cards'][month] if card['data_coverage'] > 0]
    if not measured:
        return []
    ranked = sorted(measured, key=lambda card: (-card['data_coverage'], card['employee_id'][1]))
    chosen = [ranked[0]] if len(ranked) == 1 else [ranked[0], ranked[-1]]
    return [_example_card(data, month, card) for card in chosen]


def facts(data, source, engagement=None):
    """Every number the deck states, worked out once.

    Text that a person reads is formatted here; series a chart draws stay raw.
    """
    engagement = engagement or {}
    revenue = _revenue_by_month(data)
    invoiced = _invoiced_by_month(data)
    cost = _cost_by_month(data)
    partners, partner_count = _revenue_by_partner(data)
    months = [_scorecard_month(data, month) for month in sorted(MONTHS)]
    objectives = data['objectives']
    weight = sum(objective['weight'] for objective in objectives) or 1.0
    okr_score = sum(o['score'] * o['weight'] for o in objectives) / weight
    okr_coverage = sum(o['data_coverage'] * o['weight'] for o in objectives) / weight
    file_revenue = {int(month): row['total'] for month, row in source.get('revenue', {}).items()
                    if row.get('has_data')}
    # The reader writes the month's cost as a block with its account groups;
    # older snapshots carry the total alone.
    file_cost = {int(month): (value['total'] if isinstance(value, dict) else value)
                 for month, value in source.get('cost', {}).items()}
    stages = {}
    for review in data['reviews']:
        stage = (review['stage_id'] or [0, 'Chưa vào chặng'])[1]
        stages[stage] = stages.get(stage, 0) + 1
    reviewed = data['reviews'] or []
    return {
        'built_at': datetime.datetime.now().strftime('%d/%m/%Y %H:%M'),
        'company': data['company']['name'],
        'department': DEPARTMENT,
        'engagement': engagement,
        # ---- what is in the system ----
        'staff': len(data['staff']),
        'users': data['users'],
        'cycles': len(data['cycles']),
        'library': len(data['kpi_codes']),
        'targets': len(data['targets']),
        'cards': sum(month['cards'] for month in months),
        'sources': len(data['sources']),
        'invoices': len(data['invoices']),
        'entries': len(data['entries']),
        # The cost journal and the accrual journal are both "entries"; a
        # headline that counts them together next to the cost total says the
        # cost came from one more document than it did.
        'cost_entries': sum(1 for entry in data['entries']
                            if 'chi phí' in (entry['journal_id'][1] or '').lower()),
        'accrual_entries': sum(1 for entry in data['entries']
                               if 'chi phí' not in (entry['journal_id'][1] or '').lower()),
        'confirmed': data['confirmed'],
        'audit_events': data['audit_events'],
        'unstamped': data['unstamped'],
        # ---- money ----
        'revenue_by_month': revenue,
        'invoiced_by_month': invoiced,
        'cost_by_month': cost,
        'revenue_total': sum(revenue.values()),
        'invoiced_total': sum(invoiced.values()),
        'cost_total': sum(cost.values()),
        'partners': partners,
        'partner_count': partner_count,
        'quarter_plan': sum(QUARTER_PLAN.values()),
        'quarter_actual': sum(revenue.get(month, 0.0) for month in MONTHS),
        'month_plan': {month: sum(MONTH_PLAN[month].values()) for month in sorted(MONTHS)},
        'file_revenue': file_revenue,
        'file_cost': file_cost,
        # ---- OKR ----
        'objectives': objectives,
        'okr_score': okr_score,
        'okr_coverage': okr_coverage,
        'okr_measured': sum(1 for o in objectives if o['data_coverage'] > 0),
        'krs': len(data['krs']),
        'krs_reported': sum(1 for kr in data['krs'] if kr['has_actual']),
        # ---- KPI ----
        'months': months,
        'automation': _automation(data),
        'examples': _examples(data),
        'department_report': sorted(data['department_report'],
                                    key=lambda row: row['cycle_id'][1]),
        # ---- appraisal ----
        'reviews': len(reviewed),
        'review_stages': stages,
        'review_score_live': (sum(r['goal_score_live'] for r in reviewed) / len(reviewed)
                              if reviewed else 0.0),
        'review_coverage_live': (sum(r['goal_coverage_live'] for r in reviewed) / len(reviewed)
                                 if reviewed else 0.0),
        'review_stage_count': len(data['review_stages']),
        'review_sections': len(data['review_sections']),
    }


# ------------------------------------------------------------- the slides --
CAPTIONS = dict(_handbook.FIGURES)
CAPTIONS.update({
    '16-cockpit-quarter': 'Bàn điều hành lãnh đạo, chu kỳ Quý III/2026',
    '17-cockpit-month': 'Bàn điều hành lãnh đạo, chu kỳ Tháng 7/2026 kèm khối phiếu giao KPI',
    '18-executive-overview': 'Màn hình Tổng quan lãnh đạo',
    '19-progress-vs-plan': 'Báo cáo Tiến độ so với kế hoạch',
})

# Screens in use, named exactly as the menu names them on the live system.
# `check_menus()` refuses to build if any of these is not on the customer's
# menu, so the deck can never claim a screen that is not there.
FUNCTIONS = [
    ('Kế hoạch', [
        ('Chu kỳ', 'Khai báo năm, quý, tháng và quan hệ cha con giữa chúng; điểm của tháng cuộn lên quý, quý cuộn lên năm.'),
        ('Mục tiêu', 'Mục tiêu (Objective) của phòng trong quý, có trọng số và người chịu trách nhiệm.'),
        ('Kết quả then chốt', 'Các kết quả then chốt (Key Result) của từng mục tiêu, có mốc bắt đầu và đích đến.'),
        ('Cây liên kết mục tiêu', 'Xem mục tiêu cấp trên nối xuống mục tiêu cấp dưới trên một màn hình.'),
        ('Chỉ tiêu KPI', 'Chỉ tiêu giao cho từng người trong từng tháng, kèm cách chấm điểm.'),
        ('Bảng điểm cá nhân', 'Phiếu giao KPI của một người trong một kỳ: các dòng chỉ tiêu và trọng số cộng lại thành 100.'),
        ('Thư viện KPI', 'Kho chỉ tiêu dùng lại cho các kỳ sau và cho phòng ban khác.'),
        ('Nhập từ Excel', 'Nạp mục tiêu và phiếu giao KPI từ tệp Excel theo mẫu.'),
        ('Nhân bản sang kỳ mới', 'Sao chép toàn bộ phiếu giao của kỳ này sang kỳ sau để chỉ chỉnh phần thay đổi.'),
    ]),
    ('Thực hiện', [
        ('Kết quả theo kỳ', 'Số thực hiện của từng chỉ tiêu trong từng tháng, có trạng thái nháp hoặc đã xác nhận.'),
        ('Import số liệu thực tế', 'Nạp số thực hiện hàng loạt từ tệp Excel thay vì gõ từng dòng.'),
        ('Check-in', 'Báo cáo tiến độ của kết quả then chốt, ghi lại ai báo và báo lúc nào.'),
        ('Nguồn số liệu', 'Khai báo lấy số tự động từ sổ kế toán, ví dụ doanh thu tài khoản 51131 của tháng.'),
    ]),
    ('Giám sát', [
        ('Bàn điều hành', 'Màn hình một trang cho lãnh đạo: điểm chung, độ phủ dữ liệu, bản đồ nhiệt theo phòng và khối phiếu KPI.'),
        ('Luật cảnh báo', 'Tự động cảnh báo khi chỉ tiêu tụt hạng hoặc quá lâu không có ai báo cáo.'),
        ('Họp rà soát', 'Ghi biên bản các buổi rà soát hiệu suất và việc cần làm sau buổi họp.'),
    ]),
    ('Đánh giá', [
        ('Chu kỳ đánh giá', 'Mở đợt đánh giá cho một chu kỳ hiệu suất và sinh phiếu cho toàn bộ nhân sự.'),
        ('Phiếu đánh giá', 'Phiếu của từng người theo Quy chế: ý thức kỷ luật, kết quả KPI, thưởng vượt KPI.'),
        ('Hiệu chỉnh', 'Cuộc họp hiệu chỉnh để so điểm giữa các nhóm trước khi chốt.'),
        ('Kế hoạch phát triển', 'Kế hoạch phát triển cá nhân đi kèm kết quả đánh giá.'),
    ]),
    ('Báo cáo', [
        ('Tổng quan lãnh đạo', 'Bức tranh chung của kỳ: kế hoạch so với thực hiện theo tháng.'),
        ('Bảng điểm phòng ban', 'Điểm KPI và điểm OKR bình quân của từng phòng trong từng kỳ.'),
        ('Tiến độ so với kế hoạch', 'Bảng và biểu đồ tiến độ của từng chỉ tiêu so với kế hoạch.'),
        ('Vết kiểm toán số thực hiện', 'Nhật ký mọi lần nhập, xác nhận, sửa hay huỷ xác nhận số liệu; không ai xoá được.'),
    ]),
]

CONTROLS = [
    ('Chỉ số đã xác nhận mới vào điểm',
     'Số mới nhập ở trạng thái nháp, chưa ảnh hưởng điểm; phải có người xác nhận.',
     'Quản lý hiệu suất'),
    ('Xác nhận có người chịu trách nhiệm',
     'Hệ thống lưu ai xác nhận và xác nhận lúc nào cho từng con số.',
     'Ghi tự động'),
    ('Số đã xác nhận không sửa trực tiếp',
     'Muốn sửa phải huỷ xác nhận, và huỷ thì bắt buộc nêu lý do.',
     'Quản lý hiệu suất'),
    ('Vết kiểm toán không xoá được',
     'Mọi thay đổi số liệu đều để lại dấu kèm số trước, số sau, người và lý do.',
     'Không ai, kể cả quản trị viên'),
    ('Điểm KPI trong phiếu đánh giá được chốt',
     'Khi phiếu vào chặng quản lý, điểm KPI được đóng băng kèm người và thời điểm chốt.',
     'Quản lý trực tiếp'),
    ('Mỗi người chỉ thấy phần của mình',
     'Nhân viên xem phiếu của mình; số liệu bình quân toàn phòng chỉ quản lý xem được.',
     'Phân quyền hệ thống'),
]

BEFORE_AFTER = [
    ('Nơi lưu số liệu',
     'Nhiều tệp Excel gửi qua lại, mỗi người một bản.',
     'Một nơi duy nhất trên hệ thống, ai cũng nhìn cùng một con số.'),
    ('Tổng hợp doanh thu theo mảng',
     'Lọc và cộng tay từ tệp phiếu thu mỗi lần cần báo cáo.',
     'Đã vào sổ kế toán, hệ thống tự cộng theo tài khoản và theo tháng.'),
    ('Chấm điểm KPI',
     'Người làm báo cáo tự tính phần trăm hoàn thành rồi nhân trọng số.',
     'Hệ thống tự chấm theo trọng số ngay khi số thực hiện được xác nhận.'),
    ('Truy nguyên một con số',
     'Phải mở lại tệp gốc và hỏi người lập.',
     'Bấm từ điểm số ra thẳng hoá đơn hoặc bút toán đã sinh ra nó.'),
    ('Sửa số sau khi đã báo cáo',
     'Sửa trong tệp, không ai biết đã sửa gì.',
     'Phải huỷ xác nhận kèm lý do; mọi thay đổi đều có vết.'),
    ('Đánh giá cuối kỳ',
     'Chép điểm KPI vào phiếu đánh giá bằng tay.',
     'Điểm KPI của kỳ tự chảy vào phiếu đánh giá và được chốt lại.'),
]

GLOSSARY = [
    ('Chu kỳ', 'Khoảng thời gian được giao việc và chấm điểm: năm, quý hoặc tháng.'),
    ('Mục tiêu (OKR)', 'Điều phòng muốn đạt trong quý, ví dụ "hoàn thành kế hoạch doanh thu".'),
    ('Kết quả then chốt', 'Thước đo cho biết mục tiêu đã đạt tới đâu.'),
    ('Chỉ tiêu KPI', 'Con số giao cho một người trong một kỳ, ví dụ doanh thu Telco tháng 7.'),
    ('Phiếu giao KPI', 'Tập hợp các chỉ tiêu của một người trong một kỳ, tổng trọng số 100.'),
    ('Trọng số', 'Mức quan trọng của một chỉ tiêu trong phiếu; trọng số lớn ảnh hưởng điểm nhiều hơn.'),
    ('Độ phủ dữ liệu', 'Phần trăm trọng số đã thực sự có số liệu được xác nhận.'),
    ('Điểm trên phần có số liệu', 'Điểm chỉ tính trên các chỉ tiêu đã có số, đọc kèm độ phủ.'),
    ('Vết kiểm toán', 'Nhật ký mọi thay đổi số liệu, không sửa và không xoá được.'),
]


def split_rows(rows, size=MAX_TABLE_ROWS):
    """Long tables become several slides: a PowerPoint table grows past the
    bottom of the slide without complaining."""
    return [tuple(rows[index:index + size]) for index in range(0, len(rows), size)] or [()]


def _engagement_rows(engagement):
    meetings = engagement.get('meetings') or []
    if not meetings:
        return (('Chưa có thông tin', 'Chưa có thông tin',
                 'Bổ sung ngày và nội dung hai buổi làm việc rồi tạo lại tệp báo cáo.'),)
    # An empty field is "not filled in yet", not an empty cell on a slide the
    # customer reads.
    return tuple((meeting.get('date') or 'Chưa có thông tin',
                  meeting.get('title') or 'Chưa có thông tin',
                  '; '.join(meeting.get('topics') or []) or 'Chưa có thông tin')
                 for meeting in meetings)


def _requirement_rows(engagement):
    requirements = engagement.get('requirements') or []
    if not requirements:
        return (('Chưa có thông tin', 'Chưa có thông tin'),)
    return tuple((item.get('need', ''), item.get('answer', '')) for item in requirements)


def _timeline_rows(bundle):
    months = bundle['months']
    scored = [month for month in months if month['measured']]
    return (
        ('Tiếp nhận yêu cầu', 'Hai buổi làm việc với phòng, thống nhất cách giao mục tiêu và KPI',
         'Đã xong'),
        ('Dựng hệ thống', f"Tạo {bundle['users']} tài khoản, {bundle['cycles']} chu kỳ "
                          f"và thư viện {bundle['library']} chỉ tiêu KPI", 'Đã xong'),
        ('Nạp dữ liệu kinh doanh', f"{bundle['invoices']} hoá đơn và {bundle['entries']} bút toán "
                                   f"chi phí, dự thu vào sổ kế toán", 'Đã xong'),
        ('Giao mục tiêu và KPI', f"{len(bundle['objectives'])} mục tiêu quý III, "
                                 f"{bundle['targets']} chỉ tiêu trong {bundle['cards']} phiếu giao",
         'Đã xong'),
        ('Chấm điểm thử trên số thật', f"Đã chấm {len(scored)} tháng có số liệu, "
                                       f"{bundle['confirmed']} số thực hiện được xác nhận",
         'Đang chạy'),
        ('Đánh giá quý III', f"{bundle['reviews']} phiếu đánh giá đã mở, đang ở chặng đầu",
         'Đang chạy'),
    )


def _progress_chart(bundle):
    months = {month['month']: month for month in bundle['months']}
    july = months.get(7, {})
    items = [
        ('Tổ chức và tài khoản', 100.0),
        ('Chu kỳ, mục tiêu, KPI', 100.0),
        ('Dữ liệu kinh doanh vào sổ', 100.0),
        ('Số liệu KPI của cá nhân',
         (100.0 * july.get('measured', 0) / july['cards']) if july.get('cards') else 0.0),
        ('Chấm điểm và báo cáo', 100.0),
        ('Đánh giá quý III', 100.0 / max(bundle['review_stage_count'], 1)),
    ]
    tones = tuple('green' if value >= 99 else 'amber' if value >= 40 else 'red'
                  for _name, value in items)
    return Chart(
        key='tien-do-theo-hang-muc', kind='bar', title='Tiến độ theo hạng mục (%)',
        categories=tuple(name for name, _value in items),
        series=(Series('Hoàn thành', tuple(value for _name, value in items),
                       colour='accent', point_colours=tones),),
        unit='%', decimals=0,
        note='Màu xanh là đã xong, vàng là đang làm dở, đỏ là chưa bắt đầu.')


def _revenue_chart(bundle):
    months = sorted(bundle['revenue_by_month'])
    return Chart(
        key='doanh-thu-theo-thang', kind='column',
        title='Doanh thu đã ghi nhận theo tháng (tỷ đồng)',
        categories=tuple(MONTH_LABEL[month] for month in months),
        series=(Series('Doanh thu', tuple(bundle['revenue_by_month'][m] for m in months)),),
        unit='tỷ đồng', decimals=1,
        note='Nguồn: sổ kế toán của chính đơn vị, gồm hoá đơn đã phát hành và bút toán dự thu.')


def _plan_chart(bundle):
    months = sorted(bundle['month_plan'])
    actual = tuple(bundle['revenue_by_month'].get(month) for month in months)
    return Chart(
        key='ke-hoach-va-thuc-hien-quy-3', kind='combo',
        title='Quý III: kế hoạch và thực hiện theo tháng (tỷ đồng)',
        categories=tuple(MONTH_LABEL[month] for month in months),
        series=(Series('Kế hoạch', tuple(bundle['month_plan'][m] for m in months),
                       colour='muted'),
                Series('Thực hiện', actual, colour='accent'),
                Series('Luỹ kế thực hiện', tuple(_running(actual)), colour='green', kind='line')),
        unit='tỷ đồng', decimals=1, native=False,
        note='Tháng chưa có số liệu để trống, không vẽ thành 0.')


def _running(values):
    total = None
    for value in values:
        if value is None:
            yield None
            continue
        total = value if total is None else total + value
        yield total


def _partner_chart(bundle):
    partners = bundle['partners']
    return Chart(
        key='doanh-thu-theo-doi-tac', kind='bar',
        title='Doanh thu theo đối tác, 10 đối tác lớn nhất (tỷ đồng)',
        categories=tuple(name for name, _value in partners),
        series=(Series('Doanh thu', tuple(value for _name, value in partners)),),
        unit='tỷ đồng', decimals=1,
        note=f"Tổng cộng {bundle['partner_count']} đối tác có doanh thu trong sổ.")


def _cost_chart(bundle):
    months = sorted(set(bundle['cost_by_month']) | set(bundle['revenue_by_month']))
    return Chart(
        key='doanh-thu-va-chi-phi', kind='column',
        title='Doanh thu và chi phí theo tháng (tỷ đồng)',
        categories=tuple(MONTH_LABEL[month] for month in months),
        series=(Series('Doanh thu', tuple(bundle['revenue_by_month'].get(m) for m in months),
                       colour='accent'),
                Series('Chi phí', tuple(bundle['cost_by_month'].get(m) for m in months),
                       colour='amber')),
        unit='tỷ đồng', decimals=1,
        note='Chi phí lấy từ sổ chi phí tổng hợp; tháng chưa có số liệu để trống.')


def _okr_chart(bundle):
    objectives = bundle['objectives']
    tones = tuple('green' if o['data_coverage'] > 0 and o['score'] >= 0.7
                  else 'amber' if o['data_coverage'] > 0 and o['score'] >= 0.4
                  else 'red' if o['data_coverage'] > 0 else 'muted'
                  for o in objectives)
    return Chart(
        key='muc-tieu-quy-3', kind='bar',
        title='Mục tiêu Quý III/2026: mức đạt của từng mục tiêu (%)',
        categories=tuple(f"{o['code']} · {short_name(o['name'], 26)} · {vn(o['weight'], 0)}%"
                         for o in objectives),
        # An objective nobody has reported on is a gap, not a nought: drawn as
        # 0 it reads as "achieved nothing" instead of "nothing reported yet".
        series=(Series('Mức đạt',
                       tuple(100.0 * o['score'] if o['data_coverage'] > 0 else None
                             for o in objectives),
                       point_colours=tones),),
        unit='%', decimals=0,
        note='Mục tiêu ghi "chưa có số" là chưa ai báo cáo kết quả, không phải đạt 0%.')


def _kpi_chart(bundle):
    months = bundle['months']
    return Chart(
        key='diem-kpi-theo-thang', kind='combo',
        title='Điểm KPI và độ phủ dữ liệu theo tháng (%)',
        categories=tuple(month['label'] for month in months),
        series=(Series('Điểm trên phần có số liệu',
                       tuple((100.0 * month['score_covered']) if month['score_covered'] is not None
                             else None for month in months), colour='accent'),
                Series('Độ phủ dữ liệu', tuple(month['coverage'] for month in months),
                       colour='green', kind='line')),
        unit='%', decimals=0, native=False,
        note='Điểm cao mà độ phủ thấp nghĩa là mới chấm được một phần, phải đọc kèm nhau.')


def _automation_chart(bundle):
    automation = bundle['automation']
    return Chart(
        key='tu-dong-va-nhap-tay', kind='doughnut',
        title='Trọng số phiếu KPI: phần hệ thống tự chấm và phần cần người nhập',
        categories=('Tự động từ sổ kế toán', 'Chờ người phụ trách nhập'),
        series=(Series('Trọng số', (automation['share'], 100.0 - automation['share']),
                       point_colours=('accent', 'rule')),),
        unit='%', decimals=1,
        note='Phần tự động không ai phải gõ lại và không thể nhập sai lệch với sổ.')


def _coverage_rows(bundle):
    rows = []
    for month in bundle['months']:
        rows.append((
            month['label'],
            str(month['cards']),
            str(month['measured']),
            percent(month['score_covered']) if month['score_covered'] is not None else 'Chưa có số liệu',
            share(month['coverage']),
        ))
    return tuple(rows)


def _example_table(example):
    rows = []
    for line in example['lines'][:MAX_TABLE_ROWS]:
        # The unit belongs with the figure it measures: "49,15" alone leaves
        # the reader guessing between tỷ đồng and số hợp đồng.
        unit = f" {line['unit']}" if line['unit'] else ''
        rows.append((
            line['kpi'][:58],
            vn(line['weight'], 0),
            (vn(line['target'], 2) + unit) if line['target'] is not None else '—',
            vn(line['actual'], 2) if line['actual'] is not None else 'Chưa có số liệu',
            percent(line['achievement']) if line['achievement'] is not None else '—',
            percent(line['score'], 0),
            line['source'],
        ))
    return Table(
        headers=('Chỉ tiêu KPI', 'Trọng số', 'Chỉ tiêu giao', 'Thực hiện', 'Đạt', 'Điểm', 'Số liệu đến từ'),
        rows=tuple(rows), align='lrrrrrl',
        widths=(3.8, 0.7, 1.5, 1.1, 0.7, 0.7, 1.5),
        note=f"Tổng trọng số của phiếu là {vn(example['weight'], 0)}; "
             f"{vn(example['measured_weight'], 0)} trọng số đã có số liệu. "
             f"Cột thực hiện cùng đơn vị với cột chỉ tiêu giao.")


def deck(bundle):
    """The slides, in order. Content only: no library, no arithmetic."""
    months = {month['month']: month for month in bundle['months']}
    july = months.get(7, {})
    automation = bundle['automation']
    slides = [
        Slide('cover',
              title='Báo cáo tiến độ triển khai hệ thống OKR · KPI',
              lead=f"Phòng {bundle['department']} — {bundle['company']}",
              bullets=(f"Số liệu trong báo cáo được đọc trực tiếp từ hệ thống đang chạy "
                       f"lúc {bundle['built_at']}.",
                       'Mọi con số đều mở ngược ra được chứng từ gốc trên hệ thống.')),
        Slide('kpis',
              title='Tình hình đến hôm nay, gói trong sáu con số',
              lead='Toàn bộ là số thật của phòng, không phải số minh hoạ.',
              kpis=(Kpi(vn(bundle['revenue_total'], 1) + ' tỷ', 'Doanh thu đã ghi nhận',
                        note=f"{bundle['invoices']} hoá đơn và {bundle['accrual_entries']} "
                             f"bút toán dự thu · {bundle['partner_count']} đối tác"),
                    Kpi(vn(bundle['cost_total'], 1) + ' tỷ', 'Chi phí đã vào sổ',
                        tone='amber', note=f"{bundle['cost_entries']} bút toán chi phí"),
                    Kpi(str(bundle['targets']), 'Chỉ tiêu KPI đã giao',
                        note=f"trong {bundle['cards']} phiếu của {bundle['staff']} nhân sự"),
                    Kpi(percent(bundle['okr_score'], 0), 'Mức đạt mục tiêu Quý III',
                        note=f"{bundle['okr_measured']}/{len(bundle['objectives'])} mục tiêu đã có số liệu"),
                    Kpi(percent(july.get('score_covered'), 0) if july.get('score_covered') is not None
                        else 'Chưa có', 'Điểm KPI tháng 7 trên phần có số liệu',
                        tone='green',
                        note=f"{july.get('measured', 0)}/{july.get('cards', 0)} người đã có số liệu"),
                    Kpi(str(bundle['reviews']), 'Phiếu đánh giá quý đã mở',
                        note=f"{bundle['audit_events']} sự kiện kiểm toán đã ghi")),
              footnote='Đọc chi tiết từng con số ở các trang sau.'),
        Slide('table',
              title='Đã đi đến đâu',
              lead='Sáu bước của đợt triển khai và trạng thái hiện tại của từng bước.',
              table=Table(headers=('Bước', 'Đã làm gì', 'Trạng thái'),
                          rows=_timeline_rows(bundle), align='llc',
                          widths=(2.2, 6.2, 1.4))),
        Slide('chart',
              title='Tiến độ theo từng hạng mục',
              lead='Phần chưa đạt 100% là phần đang chờ số liệu của đơn vị, không phải phần chưa làm.',
              chart=_progress_chart(bundle)),

        Slide('section', title='1. Tiếp nhận yêu cầu',
              lead='Hai buổi làm việc và những gì đã thống nhất.'),
        Slide('table',
              title='Hai buổi làm việc với phòng',
              lead='Nội dung đã trao đổi và chốt lại.',
              table=Table(headers=('Thời gian', 'Buổi làm việc', 'Nội dung chốt'),
                          rows=_engagement_rows(bundle['engagement']), align='lll',
                          widths=(1.8, 3.0, 5.0))),
        Slide('table',
              title='Yêu cầu đã tiếp nhận và nơi đáp ứng trong hệ thống',
              lead='Mỗi yêu cầu của phòng ứng với một màn hình đang chạy thật.',
              table=Table(headers=('Yêu cầu của phòng', 'Đáp ứng trên hệ thống'),
                          rows=_requirement_rows(bundle['engagement']), align='ll',
                          widths=(4.5, 5.3))),

        Slide('section', title='2. Chức năng đã đưa vào vận hành',
              lead='Năm nhóm chức năng, tất cả đang chạy với dữ liệu thật của phòng.'),
    ]
    for group, entries in FUNCTIONS:
        slides.append(Slide(
            'table',
            title=f'Chức năng nhóm {group}',
            lead='Tên trong cột đầu là tên đúng của màn hình trên hệ thống.',
            table=Table(headers=('Màn hình', 'Dùng để làm gì'),
                        rows=tuple((name, note) for name, note in entries),
                        align='ll', widths=(3.0, 6.8))))

    slides += [
        Slide('section', title='3. Dữ liệu thật đã đưa vào hệ thống',
              lead='Hai tệp của đơn vị đã thành sổ sách và chỉ tiêu trên hệ thống.'),
        Slide('table',
              title='Từ tệp của đơn vị vào hệ thống',
              lead='Mỗi loại số liệu vào đúng nơi nghiệp vụ của nó, không gom chung một chỗ.',
              table=Table(
                  headers=('Tệp của đơn vị', 'Vào đâu trên hệ thống', 'Kết quả'),
                  rows=((
                      'Bảng kê phiếu thu 2026', 'Hoá đơn bán hàng theo từng đối tác và từng mảng',
                      f"{bundle['invoices']} hoá đơn đã vào sổ"),
                      ('Bảng kê phiếu thu 2026 (phần chưa xuất hoá đơn)',
                       'Bút toán dự thu cuối tháng', 'Đã ghi nhận đủ doanh thu của kỳ'),
                      ('Bảng chi phí 2026', 'Bút toán chi phí tổng hợp theo tháng',
                       f"{bundle['cost_entries']} bút toán đã vào sổ"),
                      ('Bảng giao KPI tháng 7, 8, 9',
                       'Chỉ tiêu KPI và phiếu giao của từng người',
                       f"{bundle['targets']} chỉ tiêu trong {bundle['cards']} phiếu"),
                      ('Quyết định giao mục tiêu Quý III',
                       'Mục tiêu và kết quả then chốt của phòng',
                       f"{len(bundle['objectives'])} mục tiêu, {bundle['krs']} kết quả then chốt")),
                  align='lll', widths=(3.4, 3.6, 2.8))),
        Slide('chart',
              title='Doanh thu đã ghi nhận theo tháng',
              lead=f"Tổng cộng {vn(bundle['revenue_total'], 1)} tỷ đồng, chưa gồm thuế giá trị gia tăng.",
              chart=_revenue_chart(bundle)),
        Slide('chart',
              title='Quý III: kế hoạch so với thực hiện',
              lead=f"Kế hoạch quý là {vn(bundle['quarter_plan'], 2)} tỷ; đã thực hiện "
                   f"{vn(bundle['quarter_actual'], 2)} tỷ.",
              chart=_plan_chart(bundle)),
        Slide('chart',
              title='Doanh thu theo đối tác',
              lead='Hệ thống cộng theo đối tác ngay từ sổ, không phải lọc tay từ bảng kê.',
              chart=_partner_chart(bundle)),
        Slide('chart',
              title='Doanh thu và chi phí đặt cạnh nhau',
              lead='Cùng một nguồn sổ sách nên hai đường số liệu luôn khớp kỳ với nhau.',
              chart=_cost_chart(bundle)),
        Slide('table',
              title='Đối chiếu tệp gốc với hệ thống',
              lead='Lấy chính tệp của đơn vị so với số hệ thống đang giữ.',
              table=Table(
                  headers=('Nội dung đối chiếu', 'Số trên tệp của đơn vị', 'Số trên hệ thống', 'Chênh lệch'),
                  rows=tuple(
                      (f'Doanh thu tháng {month}', vn(value, 2) + ' tỷ',
                       vn(bundle['revenue_by_month'].get(month, 0.0), 2) + ' tỷ',
                       vn(value - bundle['revenue_by_month'].get(month, 0.0), 2))
                      for month, value in sorted(bundle['file_revenue'].items())) + tuple(
                      (f'Chi phí tháng {month}', vn(value, 2) + ' tỷ',
                       vn(bundle['cost_by_month'].get(month, 0.0), 2) + ' tỷ',
                       vn(value - bundle['cost_by_month'].get(month, 0.0), 2))
                      for month, value in sorted(bundle['file_cost'].items())),
                  align='lrrr', widths=(3.6, 2.2, 2.2, 1.8),
                  note='Cột chênh lệch bằng 0 nghĩa là hệ thống giữ đúng số của đơn vị.')),
        Slide('picture',
              title='Hoá đơn trên hệ thống',
              lead='Từng hoá đơn còn nguyên đối tác, ngày và số tiền như trên bảng kê.',
              picture=Picture('08-invoice-list', CAPTIONS['08-invoice-list'])),

        Slide('section', title='4. Với dữ liệu này, hệ thống đọc ra được gì',
              lead='Các báo cáo dưới đây đang xem được ngay hôm nay.'),
        Slide('picture_bullets',
              title='Bàn điều hành lãnh đạo — Quý III/2026',
              lead='Một màn hình trả lời: phòng đang ở đâu và số liệu đã đủ chưa.',
              picture=Picture('16-cockpit-quarter', CAPTIONS['16-cockpit-quarter']),
              bullets=(f"Mức đạt mục tiêu quý: {percent(bundle['okr_score'], 0)}, tính theo trọng số từng mục tiêu.",
                       f"Độ phủ dữ liệu {share(bundle['okr_coverage'], 0)}: phần mục tiêu đã có số liệu thật.",
                       f"{len(bundle['objectives']) - bundle['okr_measured']} mục tiêu chưa có số liệu được ghi "
                       f"là chưa chấm điểm, không bị tô đỏ oan.",
                       'Khối phiếu KPI bên dưới gộp cả ba tháng của quý.')),
        Slide('chart',
              title='Bốn mục tiêu của Quý III',
              lead='Mục tiêu nặng ký ảnh hưởng điểm chung nhiều hơn, đúng như trọng số đã giao.',
              chart=_okr_chart(bundle)),
        Slide('chart_table',
              title='Điểm KPI theo từng tháng',
              lead='Điểm phải đọc kèm độ phủ dữ liệu thì mới đúng nghĩa.',
              chart=_kpi_chart(bundle),
              table=Table(headers=('Kỳ', 'Số phiếu', 'Đã có số liệu', 'Điểm trên phần có số liệu', 'Độ phủ'),
                          rows=_coverage_rows(bundle), align='lrrrr',
                          widths=(2.2, 1.4, 1.8, 2.6, 1.4))),
        Slide('picture',
              title='Bảng điểm phòng ban',
              lead='Cùng một cách tính với bàn điều hành, nên hai màn hình luôn nói cùng một con số.',
              picture=Picture('12-department-report', CAPTIONS['12-department-report'])),
        Slide('picture_bullets',
              title='Phiếu đánh giá quý của từng người',
              lead='Điểm KPI không ai gõ tay vào phiếu đánh giá.',
              picture=Picture('15-review-form', CAPTIONS['15-review-form']),
              bullets=(f"{bundle['reviews']} phiếu đã mở cho chu kỳ Quý III/2026.",
                       f"Phiếu gồm {bundle['review_sections']} phần chấm và đi qua "
                       f"{bundle['review_stage_count']} chặng.",
                       'Điểm KPI của quý tự chảy vào phiếu và được chốt lại khi vào chặng quản lý.',
                       f"Điểm KPI bình quân đang là {percent(bundle['review_score_live'], 0)} "
                       f"với độ phủ {share(bundle['review_coverage_live'], 0)}.")),

        Slide('section', title='5. Hệ thống chấm điểm từng người như thế nào',
              lead='Năm bước, mỗi bước đều có dấu vết và người chịu trách nhiệm.'),
        Slide('bullets',
              title='Năm bước từ số liệu đến điểm của một người',
              lead='Không bước nào cần người làm báo cáo tính tay.',
              bullets=(
                  '1. Số liệu vào sổ: hoá đơn, bút toán chi phí và dự thu được ghi như nghiệp vụ kế toán bình thường.',
                  '2. Chỉ tiêu của từng người: mỗi phiếu giao KPI có các dòng chỉ tiêu, mỗi dòng một trọng số.',
                  '3. Số thực hiện của kỳ: hệ thống tự lấy từ sổ với chỉ tiêu có nguồn số liệu; các chỉ tiêu còn lại do người phụ trách nhập.',
                  '4. Xác nhận: quản lý xác nhận số liệu thì số đó mới được tính vào điểm, kèm tên người xác nhận.',
                  '5. Điểm: hệ thống nhân mức đạt với trọng số từng dòng, ra điểm phiếu và cuộn lên phòng, lên quý.')),
    ]

    for index, example in enumerate(bundle['examples'], start=1):
        slides.append(Slide(
            'table',
            title=f"Ví dụ {index}: phiếu của {example['name']} — {example['label']}",
            lead=(f"{example['job'][:70]} · đã có số liệu cho {share(example['coverage'], 0)} trọng số, "
                  f"điểm trên phần đó là {percent(example['score_covered'], 0)}."),
            table=_example_table(example),
            footnote='Dòng ghi "Chưa có số liệu" là chỉ tiêu đang chờ người phụ trách nhập, '
                     'không phải chỉ tiêu bị 0 điểm.'))

    slides += [
        Slide('chart',
              title='Vì sao chưa phải ai cũng có điểm',
              lead=f"Hệ thống tự chấm {share(automation['share'])} trọng số phiếu; phần còn lại "
                   f"chờ người phụ trách nhập số.",
              chart=_automation_chart(bundle),
              footnote=f"{bundle['sources']} nguồn số liệu đang lấy tự động từ sổ kế toán. "
                       f"Khi phần còn lại có số, toàn bộ {july.get('cards', 0)} người đều có điểm "
                       f"mà không phải làm thêm thao tác nào."),
        Slide('picture',
              title='Chỉ tiêu lấy số tự động từ sổ kế toán',
              lead='Khai báo một lần, các kỳ sau tự chạy.',
              picture=Picture('11-metric-sources', CAPTIONS['11-metric-sources'])),

        Slide('section', title='6. Vì sao tin được những con số này',
              lead='Bốn lớp bảo đảm, kiểm chứng được ngay trên màn hình.'),
        Slide('bullets',
              title='Từ điểm số lần ngược về chứng từ',
              lead='Bất kỳ ai có quyền đều tự kiểm tra được, không cần hỏi người lập báo cáo.',
              bullets=(
                  'Điểm của một người → dòng chỉ tiêu trong phiếu giao KPI của người đó.',
                  'Dòng chỉ tiêu → số thực hiện của kỳ, kèm người xác nhận và thời điểm xác nhận.',
                  'Số thực hiện → nguồn số liệu → hoá đơn hoặc bút toán đã vào sổ.',
                  f"Đối chiếu với tệp gốc của đơn vị: chênh lệch bằng 0 ở tất cả các dòng.")),
        Slide('picture_bullets',
              title='Vết kiểm toán số thực hiện',
              lead='Mọi lần nhập, xác nhận, sửa hay huỷ xác nhận đều để lại dấu.',
              picture=Picture('13-audit-trail', CAPTIONS['13-audit-trail']),
              bullets=(f"Đã ghi {bundle['audit_events']} sự kiện cho {bundle['confirmed']} số liệu đã xác nhận.",
                       'Mỗi dòng lưu số trước, số sau, người thực hiện, thời điểm và lý do.',
                       'Không ai sửa hay xoá được danh sách này, kể cả quản trị viên hệ thống.',
                       'Huỷ xác nhận một số đã vào điểm thì bắt buộc nêu lý do.')),
        Slide('table',
              title='Các chốt kiểm soát đang bật',
              lead='Đây là phần làm cho điểm đánh giá bảo vệ được trước người bị đánh giá.',
              table=Table(headers=('Chốt kiểm soát', 'Nghĩa là', 'Ai làm được'),
                          rows=tuple(CONTROLS), align='lll',
                          widths=(3.0, 4.8, 2.0))),

        Slide('section', title='7. Năng lực hệ thống và hiệu quả mang lại',
              lead='Hệ thống làm được gì, và điều đó đổi thành cái gì cho đơn vị.'),
        Slide('table',
              title='Năng lực hệ thống, nói bằng số đang chạy thật',
              lead='Không phải tính năng trên giấy: tất cả đang hoạt động với dữ liệu của phòng.',
              table=Table(
                  headers=('Năng lực', 'Đang chạy thật ở mức nào'),
                  rows=(
                      ('Quản lý theo ba cấp chu kỳ', f"Năm, quý, tháng — {bundle['cycles']} chu kỳ; điểm tháng cuộn lên quý"),
                      ('Thư viện chỉ tiêu dùng lại', f"{bundle['library']} chỉ tiêu KPI sẵn sàng giao cho kỳ sau"),
                      ('Giao việc tới từng người', f"{bundle['targets']} chỉ tiêu trong {bundle['cards']} phiếu giao"),
                      ('Chấm điểm theo trọng số', 'Tự tính mức đạt từng dòng rồi nhân trọng số, không tính tay'),
                      ('Lấy số tự động từ sổ kế toán', f"{bundle['sources']} nguồn số liệu, phủ {share(automation['share'])} trọng số phiếu"),
                      ('Kiểm soát chất lượng số liệu', 'Xác nhận có người chịu trách nhiệm, sửa phải nêu lý do'),
                      ('Vết kiểm toán không xoá được', f"{bundle['audit_events']} sự kiện đã ghi"),
                      ('Chu trình đánh giá nhiều chặng', f"{bundle['review_stage_count']} chặng, {bundle['reviews']} phiếu đang chạy"),
                      ('Nhập và xuất Excel', 'Nạp mục tiêu, phiếu giao và số thực hiện từ tệp mẫu'),
                      ('Báo cáo cho lãnh đạo', 'Bàn điều hành, bảng điểm phòng ban, tiến độ so với kế hoạch')),
                  align='ll', widths=(3.4, 6.4))),
        Slide('kpis',
              title='Hiệu quả đo được ngay trong đợt này',
              lead='Bốn thứ đơn vị nhận được, mỗi thứ kèm bằng chứng kiểm tra được.',
              kpis=(Kpi(share(automation['share']), 'Trọng số phiếu KPI hệ thống tự chấm',
                        note='không ai phải gõ lại số từ sổ kế toán'),
                    Kpi('0', 'Chênh lệch khi đối chiếu với tệp gốc',
                        tone='green', note=f"trên {bundle['invoices']} hoá đơn và {bundle['entries']} bút toán"),
                    Kpi(str(bundle['audit_events']), 'Sự kiện kiểm toán đã ghi',
                        note='mọi thay đổi số liệu đều truy được'),
                    Kpi(str(bundle['reviews']), 'Phiếu đánh giá nhận điểm KPI tự động',
                        tone='green', note='không chép tay từ bảng tính'))),
        Slide('table',
              title='Trước và sau khi có hệ thống',
              lead='Cùng một công việc, khác cách làm.',
              table=Table(headers=('Công việc', 'Trước đây', 'Hiện nay trên hệ thống'),
                          rows=tuple(BEFORE_AFTER), align='lll',
                          widths=(2.4, 3.7, 3.7))),
        Slide('bullets',
              title='Hiệu quả sẽ tăng thêm khi dữ liệu đủ',
              lead='Không cần thêm chức năng, chỉ cần thêm số liệu.',
              bullets=(
                  f"Hôm nay {july.get('measured', 0)}/{july.get('cards', 0)} người có điểm vì "
                  f"{share(automation['share'])} trọng số lấy tự động từ sổ.",
                  f"Khi {share(100.0 - automation['share'])} trọng số còn lại được nhập, "
                  f"cả {july.get('cards', 0)} người đều có điểm đầy đủ.",
                  f"{len(bundle['objectives']) - bundle['okr_measured']} mục tiêu quý sẽ có điểm ngay "
                  f"khi kết quả then chốt của chúng được báo cáo.",
                  'Số liệu tháng 9 chốt xong là có ngay điểm quý III đầy đủ cho phiếu đánh giá.')),
        Slide('table',
              title='Việc cần đơn vị phối hợp',
              lead='Phần còn thiếu đã được chỉ đích danh, không nói chung chung.',
              table=Table(
                  headers=('Việc cần làm', 'Hiện trạng', 'Kết quả khi làm xong'),
                  rows=(
                      ('Nhập số thực hiện cho các chỉ tiêu không lấy tự động được',
                       f"{july.get('waiting', 0)}/{july.get('cards', 0)} phiếu tháng 7 chưa có số liệu",
                       'Toàn bộ nhân sự có điểm KPI hàng tháng'),
                      ('Báo cáo tiến độ các kết quả then chốt',
                       f"{bundle['krs'] - bundle['krs_reported']}/{bundle['krs']} kết quả then chốt chưa ai báo",
                       'Điểm mục tiêu quý phản ánh đúng thực tế'),
                      ('Chốt số liệu tháng 9',
                       'Tháng 9 chưa có số thực hiện nào được xác nhận',
                       'Đủ ba tháng để chấm trọn quý III'),
                      ('Chạy tiếp các chặng đánh giá',
                       f"{bundle['reviews']} phiếu đang ở chặng đầu",
                       'Hoàn tất đánh giá quý III theo đúng quy chế')),
                  align='lll', widths=(3.6, 3.3, 3.0))),
        Slide('close',
              title='Kết luận về tính khả thi',
              lead='Giải pháp đã chạy được trên chính số liệu của đơn vị, không phải trên dữ liệu mẫu.',
              bullets=(
                  f"Đã chứng minh: số liệu kinh doanh vào sổ đúng đến từng đồng, hệ thống tự chấm "
                  f"{share(automation['share'])} trọng số phiếu và cho ra điểm phòng, điểm cá nhân ngay.",
                  'Đã chứng minh: mọi điểm số truy ngược được tới chứng từ và mọi thay đổi đều có vết.',
                  'Việc còn lại là bổ sung số liệu cho phần chỉ tiêu nhập tay và chạy tiếp các chặng đánh giá.',
                  'Đề nghị: chốt lịch nhập số hàng tháng và người chịu trách nhiệm cho từng nhóm chỉ tiêu.')),
    ]

    slides += _appendix(bundle)
    return tuple(slides)


def _appendix(bundle):
    """The detail the project team asks for after the meeting."""
    slides = [Slide('section', title='Phụ lục',
                    lead='Phần chi tiết dành cho tổ dự án.')]
    if bundle['months']:
        slides.append(Slide(
            'table',
            title='Phân bố kết quả theo từng tháng',
            lead='Phiếu chưa có số liệu được đếm riêng, không xếp vào nhóm lệch tiến độ.',
            table=Table(
                headers=('Kỳ', 'Số phiếu', 'Đã có số liệu', 'Đúng tiến độ', 'Có rủi ro',
                         'Lệch tiến độ', 'Chưa chấm điểm'),
                rows=tuple(
                    (month['label'], str(month['cards']), str(month['measured']),
                     str(month['bands']['green']), str(month['bands']['amber']),
                     str(month['bands']['red']), str(month['bands']['none']))
                    for month in bundle['months']),
                align='lrrrrrr', widths=(2.0, 1.3, 1.6, 1.4, 1.3, 1.4, 1.6))))
    # The same rounding as the slide that shows these figures earlier: a
    # reader who sees 82,6% on one page and 83% on another stops trusting
    # both.
    report_rows = tuple(
        (row['cycle_id'][1], str(row['employee_count']), str(row.get('measured_employee_count', 0)),
         percent(row['avg_composite']),
         percent(row['avg_score_covered']) if row.get('measured_employee_count') else 'Chưa có số liệu',
         share(row['avg_data_coverage']), percent(row['avg_objective_score']),
         (row['objective_cycle_id'] or [0, '—'])[1])
        for row in bundle['department_report'])
    slides.append(Slide(
        'table',
        title='Bảng điểm phòng ban, số chi tiết',
        lead='Cột cuối cho biết điểm mục tiêu được lấy từ chu kỳ nào.',
        table=Table(
            headers=('Kỳ', 'Số người', 'Đã có số liệu', 'Điểm KPI', 'Điểm trên phần có số liệu',
                     'Độ phủ', 'Điểm mục tiêu', 'Lấy từ chu kỳ'),
            rows=report_rows, align='lrrrrrrl',
            widths=(1.8, 1.1, 1.4, 1.2, 1.9, 1.0, 1.3, 1.8))))
    slides.append(Slide(
        'table',
        title='Từ điển thuật ngữ',
        lead='Giải nghĩa ngắn gọn các từ dùng trong báo cáo này.',
        table=Table(headers=('Thuật ngữ', 'Nghĩa là gì'), rows=tuple(GLOSSARY),
                    align='ll', widths=(2.6, 7.2))))
    slides.append(Slide(
        'table',
        title='Nguồn của từng nhóm số liệu trong báo cáo',
        lead='Ai muốn kiểm chứng thì mở đúng màn hình này trên hệ thống.',
        table=Table(
            headers=('Nhóm số liệu', 'Màn hình để kiểm chứng'),
            rows=(('Doanh thu, chi phí', 'Hoá đơn · Bút toán sổ nhật ký'),
                  ('Chỉ tiêu và điểm cá nhân', 'Hiệu suất › Kế hoạch › Bảng điểm cá nhân'),
                  ('Số thực hiện từng kỳ', 'Hiệu suất › Thực hiện › Kết quả theo kỳ'),
                  ('Mục tiêu quý', 'Hiệu suất › Kế hoạch › Mục tiêu'),
                  ('Điểm phòng ban', 'Hiệu suất › Báo cáo › Bảng điểm phòng ban'),
                  ('Lịch sử thay đổi số liệu', 'Hiệu suất › Báo cáo › Vết kiểm toán số thực hiện'),
                  ('Đánh giá quý', 'Hiệu suất › Đánh giá › Phiếu đánh giá')),
            align='ll', widths=(3.4, 6.4))))
    return slides


# ------------------------------------------------------------ the picture --
def check_pictures(slides, images):
    """A customer deck with a hole where a screenshot should be is worse than
    a build that stops."""
    missing = sorted({picture.name for picture in pictures_of(slides)
                      if not (images / f'{picture.name}.png').exists()})
    if missing:
        raise SystemExit(
            'Thiếu ảnh màn hình: %s.\nChạy "cd uat && node capture_kddv_guide.mjs" '
            'rồi dựng lại báo cáo.' % ', '.join(missing))


def check_menus(client):
    """Refuse to claim a screen the customer does not have on their menu."""
    menus = {row['name'] for row in client.search_read('ir.ui.menu', [], ['name'], context=VI)}
    claimed = {name for _group, entries in FUNCTIONS for name, _note in entries}
    missing = sorted(claimed - menus)
    if missing:
        raise SystemExit('Báo cáo nhắc tới màn hình không có trên hệ thống: %s'
                         % ', '.join(missing))


def font_files():
    """A font with Vietnamese diacritics, for the PDF and the charts.

    IBM Plex is the product's face but is not installed here and is not in the
    repository; naming it anyway would make Word substitute Calibri and move
    every line break. So: Plex if somebody vendors it, then Segoe UI which
    every Windows machine has, then DejaVu which ships inside matplotlib and
    therefore cannot be missing wherever this deck can be built.
    """
    import matplotlib
    mpl_fonts = pathlib.Path(matplotlib.__file__).parent / 'mpl-data' / 'fonts' / 'ttf'
    candidates = [
        (_REPO / 'tools' / 'fonts' / 'IBMPlexSans-Regular.ttf',
         _REPO / 'tools' / 'fonts' / 'IBMPlexSans-SemiBold.ttf', 'IBM Plex Sans'),
        (pathlib.Path('C:/Windows/Fonts/segoeui.ttf'),
         pathlib.Path('C:/Windows/Fonts/segoeuib.ttf'), 'Segoe UI'),
        (mpl_fonts / 'DejaVuSans.ttf', mpl_fonts / 'DejaVuSans-Bold.ttf', 'DejaVu Sans'),
    ]
    for regular, bold, name in candidates:
        if regular.exists() and bold.exists():
            return regular, bold, name
    raise SystemExit('Không tìm thấy phông chữ có dấu tiếng Việt để dựng báo cáo.')


def write_charts(slides, out_dir):
    """Every chart as a PNG: the reference rendering, reused by the PDF and
    handed to the customer for their own reports."""
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.ticker import FuncFormatter

    regular, _bold, family = font_files()
    matplotlib.font_manager.fontManager.addfont(str(regular))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for chart in charts_of(slides):
        figure = Figure(figsize=CHART_SIZE, dpi=170, facecolor=HEX['paper'])
        FigureCanvasAgg(figure)
        # The band above the axes belongs to the title and, when there is
        # one, the legend under it - drawn over each other they were both
        # unreadable.
        legend_band = 0.06 if len(chart.series) > 1 else 0.0
        axes = figure.add_axes((0.30 if chart.kind == 'bar' else 0.085, 0.17,
                                0.64 if chart.kind == 'bar' else 0.885,
                                0.70 - legend_band))
        axes.set_facecolor(HEX['paper'])
        for spine in ('top', 'right'):
            axes.spines[spine].set_visible(False)
        for spine in ('left', 'bottom'):
            axes.spines[spine].set_color(HEX['rule'])
        axes.tick_params(colors=HEX['ink2'], labelsize=9)
        for label in axes.get_xticklabels() + axes.get_yticklabels():
            label.set_fontfamily(family)
        _draw_chart(axes, chart, family, FuncFormatter)
        figure.text(0.085, 0.945, chart.title, color=HEX['ink'], fontsize=13,
                    fontfamily=family, va='top')
        if chart.note:
            figure.text(0.085, 0.045, chart.note, color=HEX['muted'], fontsize=8.5,
                        fontfamily=family)
        path = out_dir / f'{chart.key}.png'
        figure.savefig(path, format='png', facecolor=HEX['paper'])
        written[chart.key] = path
    return written


def _draw_chart(axes, chart, family, FuncFormatter):
    """One chart, drawn the way its kind wants to be read."""
    positions = range(len(chart.categories))
    show = FuncFormatter(lambda value, _pos: vn(value, chart.decimals))
    bars = [series for series in chart.series if series.kind == 'column']
    lines = [series for series in chart.series if series.kind == 'line']

    if chart.kind == 'doughnut':
        series = chart.series[0]
        colours = [HEX[tone] for tone in (series.point_colours or ('accent', 'rule'))]
        wedges, _texts = axes.pie(
            [value or 0.0 for value in series.values], colors=colours,
            startangle=90, counterclock=False, wedgeprops={'width': 0.42})
        axes.set_aspect('equal')
        axes.legend(wedges, [f'{name} · {vn(value, chart.decimals)}%'
                             for name, value in zip(chart.categories, series.values)],
                    loc='center left', bbox_to_anchor=(1.0, 0.5), frameon=False,
                    prop={'family': family, 'size': 9})
        return

    if chart.kind == 'bar':                       # horizontal: long labels fit
        series = chart.series[0]
        colours = [HEX[tone] for tone in (series.point_colours or
                                          [series.colour] * len(series.values))]
        drawn = axes.barh(list(positions), [value or 0.0 for value in series.values],
                          color=colours, height=0.62)
        axes.set_yticks(list(positions))
        axes.set_yticklabels(list(chart.categories), fontfamily=family, fontsize=9)
        axes.invert_yaxis()
        axes.xaxis.set_major_formatter(show)
        axes.xaxis.grid(True, color=HEX['rule'], linewidth=0.6)
        axes.set_axisbelow(True)
        for rectangle, value in zip(drawn, series.values):
            axes.annotate(vn(value, chart.decimals) if value is not None else 'chưa có số',
                          (rectangle.get_width(), rectangle.get_y() + rectangle.get_height() / 2),
                          xytext=(5, 0), textcoords='offset points', va='center',
                          fontsize=9, fontfamily=family, color=HEX['ink2'])
        return

    # A single series drawn at the full category width reads as a block of
    # colour rather than as a bar.
    width = min(0.8 / max(len(bars), 1), 0.46)
    for index, series in enumerate(bars):
        offsets = [position - 0.4 + width * (index + 0.5) for position in positions]
        colours = [HEX[tone] for tone in (series.point_colours or
                                          [series.colour] * len(series.values))]
        drawn = axes.bar(offsets, [value if value is not None else 0.0 for value in series.values],
                         width=width * 0.92, color=colours, label=series.name)
        for rectangle, value in zip(drawn, series.values):
            axes.annotate(vn(value, chart.decimals) if value is not None else 'chưa có số',
                          (rectangle.get_x() + rectangle.get_width() / 2, rectangle.get_height()),
                          xytext=(0, 4), textcoords='offset points', ha='center',
                          fontsize=8.5, fontfamily=family,
                          color=HEX['ink2'] if value is not None else HEX['muted'])
    for series in lines:
        axes.plot(list(positions), [value for value in series.values],
                  color=HEX[series.colour], marker='o', linewidth=2.2,
                  label=series.name, zorder=5)
    axes.set_xticks(list(positions))
    axes.set_xticklabels(chart.categories, fontfamily=family, fontsize=9)
    axes.yaxis.set_major_formatter(show)
    axes.yaxis.grid(True, color=HEX['rule'], linewidth=0.6)
    axes.set_axisbelow(True)
    if len(chart.series) > 1:
        axes.legend(frameon=False, prop={'family': family, 'size': 9}, ncol=len(chart.series),
                    loc='lower left', bbox_to_anchor=(0, 1.015))


def fit(png, box):
    """Centre a picture inside a box without distorting it. The screenshots
    carry no DPI, so anything that guesses their size gets them four times too
    wide."""
    from PIL import Image
    with Image.open(png) as picture:
        width, height = picture.size
    scale = min(box[2] / width, box[3] / height)
    drawn = (width * scale, height * scale)
    return (box[0] + (box[2] - drawn[0]) / 2, box[1] + (box[3] - drawn[1]) / 2, *drawn)


# ------------------------------------------------------------- PowerPoint --
def render_pptx(slides, out, charts, images):
    from pptx import Presentation
    from pptx.util import Inches, Pt

    _, _, family = font_files()
    deck_file = Presentation()
    deck_file.slide_width, deck_file.slide_height = SLIDE_EMU
    deck_file.core_properties.title = 'Báo cáo tiến độ OKR · KPI'
    deck_file.core_properties.language = 'vi-VN'
    blank = deck_file.slide_layouts[6]
    for slide in slides:
        page = deck_file.slides.add_slide(blank)
        _pptx_background(page, slide, family, Inches, Pt)
        PPTX_HANDLERS[slide.kind](page, slide, charts, images, family, Inches, Pt)
    out.parent.mkdir(parents=True, exist_ok=True)
    deck_file.save(str(out))
    return len(slides)


def _pptx_text(page, text, box, Inches, Pt, size=14, colour='ink', bold=False,
               family='Segoe UI', align=None, wrap=True):
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    frame_box = page.shapes.add_textbox(Inches(box[0]), Inches(box[1]),
                                        Inches(box[2]), Inches(box[3]))
    frame = frame_box.text_frame
    frame.word_wrap = wrap
    paragraph = frame.paragraphs[0]
    run = paragraph.add_run()
    run.text = text
    run.font.size, run.font.bold, run.font.name = Pt(size), bold, family
    run.font.color.rgb = RGBColor.from_string(RGB[colour])
    if align:
        paragraph.alignment = {'center': PP_ALIGN.CENTER, 'right': PP_ALIGN.RIGHT}[align]
    return frame_box


def _pptx_background(page, slide, family, Inches, Pt):
    from pptx.dml.color import RGBColor
    page.background.fill.solid()
    page.background.fill.fore_color.rgb = RGBColor.from_string(
        RGB['accent'] if slide.kind in ('cover', 'section') else RGB['paper'])
    if slide.kind in ('cover', 'section'):
        return
    if slide.title:
        _pptx_text(page, slide.title, (MARGIN, 0.42, SLIDE_W - 2 * MARGIN, 0.62),
                   Inches, Pt, size=23, bold=True, family=family)
    if slide.lead:
        _pptx_text(page, slide.lead, (MARGIN, 1.05, SLIDE_W - 2 * MARGIN, 0.5),
                   Inches, Pt, size=12.5, colour='muted', family=family)
    if slide.footnote:
        _pptx_text(page, slide.footnote, (MARGIN, SLIDE_H - 0.62, SLIDE_W - 2 * MARGIN, 0.45),
                   Inches, Pt, size=10, colour='muted', family=family)


def _pptx_cover(page, slide, _charts, _images, family, Inches, Pt):
    _pptx_text(page, slide.title, (MARGIN + 0.2, 2.35, SLIDE_W - 2 * MARGIN - 0.4, 1.3),
               Inches, Pt, size=36, bold=True, colour='paper', family=family)
    _pptx_text(page, slide.lead, (MARGIN + 0.2, 3.75, SLIDE_W - 2 * MARGIN - 0.4, 0.7),
               Inches, Pt, size=18, colour='paper2', family=family)
    top = 4.7
    for line in slide.bullets:
        _pptx_text(page, line, (MARGIN + 0.2, top, SLIDE_W - 2 * MARGIN - 0.4, 0.45),
                   Inches, Pt, size=12, colour='paper3', family=family)
        top += 0.42


def _pptx_section(page, slide, _charts, _images, family, Inches, Pt):
    _pptx_text(page, slide.title, (MARGIN + 0.2, 3.0, SLIDE_W - 2 * MARGIN - 0.4, 1.0),
               Inches, Pt, size=32, bold=True, colour='paper', family=family)
    if slide.lead:
        _pptx_text(page, slide.lead, (MARGIN + 0.2, 4.1, SLIDE_W - 2 * MARGIN - 0.4, 0.7),
                   Inches, Pt, size=16, colour='paper2', family=family)


def _pptx_bullets(page, slide, _charts, _images, family, Inches, Pt):
    top = BODY_TOP
    for line in slide.bullets:
        _pptx_text(page, '•  ' + line, (MARGIN, top, SLIDE_W - 2 * MARGIN, 0.72),
                   Inches, Pt, size=14, family=family)
        top += max(0.55, 0.36 + 0.24 * (len(line) // 95))


def _pptx_kpis(page, slide, _charts, _images, family, Inches, Pt):
    from pptx.dml.color import RGBColor
    from pptx.util import Emu
    count = len(slide.kpis)
    columns = 3 if count > 4 else max(count, 1)
    rows = (count + columns - 1) // columns
    gap = 0.28
    width = (SLIDE_W - 2 * MARGIN - gap * (columns - 1)) / columns
    height = min(1.9, (BODY_BOTTOM - BODY_TOP - gap * (rows - 1)) / rows)
    for index, kpi in enumerate(slide.kpis):
        column, row = index % columns, index // columns
        left, top = MARGIN + column * (width + gap), BODY_TOP + row * (height + gap)
        card = page.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor.from_string(RGB['paper2'])
        card.line.color.rgb = RGBColor.from_string(RGB['rule'])
        card.shadow.inherit = False
        card.text_frame.word_wrap = True
        _pptx_text(page, kpi.value, (left + 0.22, top + 0.16, width - 0.44, 0.7),
                   Inches, Pt, size=30, bold=True, colour=kpi.tone, family=family)
        _pptx_text(page, kpi.label, (left + 0.22, top + 0.88, width - 0.44, 0.5),
                   Inches, Pt, size=11.5, colour='ink', family=family)
        if kpi.note:
            _pptx_text(page, kpi.note, (left + 0.22, top + 1.32, width - 0.44, 0.45),
                       Inches, Pt, size=9.5, colour='muted', family=family)


def _pptx_table(page, slide, _charts, _images, family, Inches, Pt, box=None):
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    spec = slide.table
    box = box or (MARGIN, BODY_TOP, SLIDE_W - 2 * MARGIN,
                  BODY_BOTTOM - BODY_TOP - (0.3 if spec.note else 0))
    rows, columns = len(spec.rows) + 1, len(spec.headers)
    shape = page.shapes.add_table(rows, columns, Inches(box[0]), Inches(box[1]),
                                  Inches(box[2]), Inches(box[3]))
    table = shape.table
    # python-pptx always writes its default blue banded style and offers no
    # API to change it; switch to "no style" and paint with the tokens.
    style = table._tbl.tblPr
    style.set('firstRow', '1')
    for element in style.findall('.//{*}tableStyleId'):
        element.text = '{2D5ABB26-0587-4C30-8999-92F81FD0307C}'
    widths = spec.widths or tuple([1] * columns)
    total = sum(widths)
    for index, weight in enumerate(widths[:columns]):
        table.columns[index].width = int(Inches(box[2]).emu * weight / total)
    align = spec.align or 'l' * columns
    for column, header in enumerate(spec.headers):
        _pptx_cell(table.cell(0, column), header, family, Pt, RGBColor, PP_ALIGN, MSO_ANCHOR,
                   bold=True, fill='accent', colour='paper', align='l')
    for row, values in enumerate(spec.rows, start=1):
        for column, value in enumerate(values):
            _pptx_cell(table.cell(row, column), str(value), family, Pt, RGBColor, PP_ALIGN,
                       MSO_ANCHOR, fill='paper' if row % 2 else 'paper2',
                       align=align[column] if column < len(align) else 'l')
    if spec.note:
        _pptx_text(page, spec.note, (MARGIN, BODY_BOTTOM - 0.02, SLIDE_W - 2 * MARGIN, 0.4),
                   Inches, Pt, size=9.5, colour='muted', family=family)


def _pptx_cell(cell, text, family, Pt, RGBColor, PP_ALIGN, MSO_ANCHOR,
               bold=False, fill='paper', colour='ink', align='l'):
    cell.fill.solid()
    cell.fill.fore_color.rgb = RGBColor.from_string(RGB[fill])
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = cell.margin_right = Pt(6)
    cell.margin_top = cell.margin_bottom = Pt(3)
    frame = cell.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.alignment = {'l': PP_ALIGN.LEFT, 'r': PP_ALIGN.RIGHT,
                           'c': PP_ALIGN.CENTER}[align]
    run = paragraph.add_run()
    run.text = text
    run.font.size, run.font.bold, run.font.name = Pt(10.5), bold, family
    run.font.color.rgb = RGBColor.from_string(RGB[colour])


def _pptx_chart(page, slide, charts, _images, family, Inches, Pt, box=None):
    spec = slide.chart
    box = box or (MARGIN, BODY_TOP, SLIDE_W - 2 * MARGIN, BODY_BOTTOM - BODY_TOP - 0.35)
    if spec.native:
        _pptx_native_chart(page, spec, box, family, Inches, Pt)
    else:
        picture = charts[spec.key]
        page.shapes.add_picture(str(picture), *[Inches(value) for value in fit(picture, box)[:3]])
    if spec.note:
        _pptx_text(page, spec.note, (MARGIN, BODY_BOTTOM - 0.05, SLIDE_W - 2 * MARGIN, 0.4),
                   Inches, Pt, size=9.5, colour='muted', family=family)


def _pptx_native_chart(page, spec, box, family, Inches, Pt):
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION

    kinds = {'column': XL_CHART_TYPE.COLUMN_CLUSTERED,
             'stacked': XL_CHART_TYPE.COLUMN_STACKED,
             'bar': XL_CHART_TYPE.BAR_CLUSTERED,
             'line': XL_CHART_TYPE.LINE_MARKERS,
             'doughnut': XL_CHART_TYPE.DOUGHNUT}
    code = '#,##0' + ('.' + '0' * spec.decimals if spec.decimals else '')
    data = CategoryChartData()
    data.categories = spec.categories
    for series in spec.series:
        data.add_series(series.name, series.values, number_format=code)
    frame = page.shapes.add_chart(kinds[spec.kind], *[Inches(value) for value in box], data)
    chart = frame.chart
    chart.font.name, chart.font.size = family, Pt(10)
    chart.has_title = False
    if len(spec.series) > 1:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
    else:
        chart.has_legend = spec.kind == 'doughnut'
        if chart.has_legend:
            chart.legend.position = XL_LEGEND_POSITION.RIGHT
            chart.legend.include_in_layout = False
    plot = chart.plots[0]
    if spec.kind != 'doughnut':
        plot.gap_width, plot.overlap = 60, -10
    plot.vary_by_categories = spec.kind == 'doughnut'
    for series, wanted in zip(plot.series, spec.series):
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = RGBColor.from_string(RGB[wanted.colour])
        series.format.line.fill.background()
        for point, tone in zip(series.points, wanted.point_colours):
            point.format.fill.solid()
            point.format.fill.fore_color.rgb = RGBColor.from_string(RGB[tone])
    plot.has_data_labels = True
    labels = plot.data_labels
    labels.number_format, labels.number_format_is_linked = code, False
    labels.font.size, labels.font.name = Pt(9), family
    labels.font.color.rgb = RGBColor.from_string(RGB['ink2'])
    if spec.kind in ('column', 'bar'):
        labels.position = XL_LABEL_POSITION.OUTSIDE_END
    if spec.kind != 'doughnut':
        axis = chart.value_axis
        axis.tick_labels.number_format, axis.tick_labels.number_format_is_linked = code, False
        axis.has_major_gridlines = True
        axis.major_gridlines.format.line.color.rgb = RGBColor.from_string(RGB['rule'])


def _pptx_chart_table(page, slide, charts, images, family, Inches, Pt):
    half = (SLIDE_W - 2 * MARGIN) * 0.56
    _pptx_chart(page, slide, charts, images, family, Inches, Pt,
                box=(MARGIN, BODY_TOP, half, BODY_BOTTOM - BODY_TOP - 0.35))
    _pptx_table(page, slide, charts, images, family, Inches, Pt,
                box=(MARGIN + half + 0.3, BODY_TOP,
                     SLIDE_W - 2 * MARGIN - half - 0.3, BODY_BOTTOM - BODY_TOP - 0.7))


def _pptx_picture(page, slide, _charts, images, family, Inches, Pt, box=None):
    path = images / f'{slide.picture.name}.png'
    box = box or (MARGIN, BODY_TOP, SLIDE_W - 2 * MARGIN, BODY_BOTTOM - BODY_TOP - 0.3)
    placed = fit(path, box)
    page.shapes.add_picture(str(path), Inches(placed[0]), Inches(placed[1]),
                            width=Inches(placed[2]))
    _pptx_text(page, slide.picture.caption,
               (MARGIN, placed[1] + placed[3] + 0.06, SLIDE_W - 2 * MARGIN, 0.4),
               Inches, Pt, size=9.5, colour='muted', family=family)


def _pptx_picture_bullets(page, slide, charts, images, family, Inches, Pt):
    picture_width = (SLIDE_W - 2 * MARGIN) * 0.60
    _pptx_picture(page, slide, charts, images, family, Inches, Pt,
                  box=(MARGIN, BODY_TOP, picture_width, BODY_BOTTOM - BODY_TOP - 0.3))
    left = MARGIN + picture_width + 0.35
    top = BODY_TOP
    for line in slide.bullets:
        _pptx_text(page, '•  ' + line, (left, top, SLIDE_W - MARGIN - left, 1.1),
                   Inches, Pt, size=12, family=family)
        top += max(0.62, 0.34 + 0.26 * (len(line) // 44))


def _pptx_close(page, slide, charts, images, family, Inches, Pt):
    _pptx_bullets(page, slide, charts, images, family, Inches, Pt)


PPTX_HANDLERS = {
    'cover': _pptx_cover,
    'section': _pptx_section,
    'bullets': _pptx_bullets,
    'kpis': _pptx_kpis,
    'table': _pptx_table,
    'chart': _pptx_chart,
    'chart_table': _pptx_chart_table,
    'picture': _pptx_picture,
    'picture_bullets': _pptx_picture_bullets,
    'close': _pptx_close,
}


# --------------------------------------------------------------------- PDF --
# Neither PowerPoint nor LibreOffice is installed on the build machine, so the
# PDF is drawn from the same slides rather than converted. One slide is always
# one page: a deck whose pages drift out of step with its slides is worse than
# no PDF at all.
PDF_SCALE = 72.0


def _pdf_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    regular, bold, family = font_files()
    pdfmetrics.registerFont(TTFont(family, str(regular)))
    pdfmetrics.registerFont(TTFont(family + ' Bold', str(bold)))
    pdfmetrics.registerFontFamily(family, normal=family, bold=family + ' Bold')
    return family, family + ' Bold'


def render_pdf(slides, out, charts, images):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor

    regular, bold = _pdf_font()
    out.parent.mkdir(parents=True, exist_ok=True)
    page_size = (SLIDE_W * PDF_SCALE, SLIDE_H * PDF_SCALE)
    pdf = canvas.Canvas(str(out), pagesize=page_size)
    pdf.setTitle('Báo cáo tiến độ OKR · KPI')
    for slide in slides:
        if slide.kind in ('cover', 'section'):
            pdf.setFillColor(HexColor(HEX['accent']))
            pdf.rect(0, 0, *page_size, stroke=0, fill=1)
        else:
            pdf.setFillColor(HexColor(HEX['paper']))
            pdf.rect(0, 0, *page_size, stroke=0, fill=1)
            if slide.title:
                _pdf_text(pdf, slide.title, MARGIN, 0.42, 23, bold, 'ink')
            if slide.lead:
                _pdf_text(pdf, slide.lead, MARGIN, 1.12, 12.5, regular, 'muted')
            if slide.footnote:
                _pdf_text(pdf, slide.footnote, MARGIN, SLIDE_H - 0.42, 9.5, regular, 'muted')
        PDF_HANDLERS[slide.kind](pdf, slide, charts, images, regular, bold)
        pdf.showPage()
    pdf.save()
    return len(slides)


def _pdf_y(top, height=0.0):
    """Inches from the top edge -> reportlab's bottom-left origin."""
    return (SLIDE_H - top - height) * PDF_SCALE


def _pdf_text(pdf, text, left, top, size, font, colour, width=None):
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    width = width if width is not None else (SLIDE_W - 2 * MARGIN)
    style = ParagraphStyle('text', fontName=font, fontSize=size, leading=size * 1.32,
                           textColor=HexColor(HEX[colour]))
    paragraph = Paragraph(text.replace('&', '&amp;').replace('<', '&lt;'), style)
    used_width, used_height = paragraph.wrapOn(pdf, width * PDF_SCALE, SLIDE_H * PDF_SCALE)
    paragraph.drawOn(pdf, left * PDF_SCALE, _pdf_y(top) - used_height)
    return used_height / PDF_SCALE


def _pdf_cover(pdf, slide, _charts, _images, regular, bold):
    _pdf_text(pdf, slide.title, MARGIN + 0.2, 2.4, 34, bold, 'paper', SLIDE_W - 2 * MARGIN - 0.4)
    _pdf_text(pdf, slide.lead, MARGIN + 0.2, 3.9, 17, regular, 'paper2', SLIDE_W - 2 * MARGIN - 0.4)
    top = 4.8
    for line in slide.bullets:
        top += _pdf_text(pdf, line, MARGIN + 0.2, top, 12, regular, 'paper3',
                         SLIDE_W - 2 * MARGIN - 0.4) + 0.12


def _pdf_section(pdf, slide, _charts, _images, regular, bold):
    _pdf_text(pdf, slide.title, MARGIN + 0.2, 3.0, 30, bold, 'paper', SLIDE_W - 2 * MARGIN - 0.4)
    if slide.lead:
        _pdf_text(pdf, slide.lead, MARGIN + 0.2, 4.15, 15, regular, 'paper2',
                  SLIDE_W - 2 * MARGIN - 0.4)


def _pdf_bullets(pdf, slide, _charts, _images, regular, _bold):
    top = BODY_TOP
    for line in slide.bullets:
        top += _pdf_text(pdf, '•  ' + line, MARGIN, top, 13.5, regular, 'ink') + 0.22


def _pdf_kpis(pdf, slide, _charts, _images, regular, bold):
    from reportlab.lib.colors import HexColor
    count = len(slide.kpis)
    columns = 3 if count > 4 else max(count, 1)
    rows = (count + columns - 1) // columns
    gap = 0.28
    width = (SLIDE_W - 2 * MARGIN - gap * (columns - 1)) / columns
    height = min(1.9, (BODY_BOTTOM - BODY_TOP - gap * (rows - 1)) / rows)
    for index, kpi in enumerate(slide.kpis):
        column, row = index % columns, index // columns
        left, top = MARGIN + column * (width + gap), BODY_TOP + row * (height + gap)
        pdf.setFillColor(HexColor(HEX['paper2']))
        pdf.setStrokeColor(HexColor(HEX['rule']))
        pdf.roundRect(left * PDF_SCALE, _pdf_y(top, height), width * PDF_SCALE,
                      height * PDF_SCALE, 6, stroke=1, fill=1)
        _pdf_text(pdf, kpi.value, left + 0.22, top + 0.2, 28, bold, kpi.tone, width - 0.44)
        _pdf_text(pdf, kpi.label, left + 0.22, top + 0.95, 11.5, regular, 'ink', width - 0.44)
        if kpi.note:
            _pdf_text(pdf, kpi.note, left + 0.22, top + 1.38, 9.5, regular, 'muted', width - 0.44)


def _pdf_table(pdf, slide, _charts, _images, regular, bold, box=None):
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Table as PdfTable, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    spec = slide.table
    box = box or (MARGIN, BODY_TOP, SLIDE_W - 2 * MARGIN,
                  BODY_BOTTOM - BODY_TOP - (0.35 if spec.note else 0))
    body = ParagraphStyle('cell', fontName=regular, fontSize=10, leading=12.5,
                          textColor=HexColor(HEX['ink']))
    head = ParagraphStyle('head', parent=body, fontName=bold,
                          textColor=HexColor(HEX['paper']))
    rows = [[Paragraph(str(value), head) for value in spec.headers]]
    rows += [[Paragraph(str(value), body) for value in row] for row in spec.rows]
    widths = spec.widths or tuple([1] * len(spec.headers))
    total = sum(widths)
    columns = [box[2] * PDF_SCALE * weight / total for weight in widths[:len(spec.headers)]]
    align = spec.align or 'l' * len(spec.headers)
    table = PdfTable(rows, colWidths=columns)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor(HEX['accent'])),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [HexColor(HEX['paper']), HexColor(HEX['paper2'])]),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, HexColor(HEX['rule'])),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ] + [('ALIGN', (index, 1), (index, -1),
          {'l': 'LEFT', 'r': 'RIGHT', 'c': 'CENTER'}[letter])
         for index, letter in enumerate(align[:len(spec.headers)])]))
    _used_width, used_height = table.wrapOn(pdf, box[2] * PDF_SCALE, box[3] * PDF_SCALE)
    if used_height > box[3] * PDF_SCALE:
        # In PowerPoint the same table would silently grow off the slide; here
        # it is caught while the deck is being built.
        raise SystemExit('Bảng của trang "%s" cao %.2f", vượt khung %.2f" — hãy tách bớt dòng.'
                         % (slide.title, used_height / PDF_SCALE, box[3]))
    table.drawOn(pdf, box[0] * PDF_SCALE, _pdf_y(box[1]) - used_height)
    if spec.note:
        _pdf_text(pdf, spec.note, MARGIN, BODY_BOTTOM + 0.05, 9.5, regular, 'muted')


def _pdf_image(pdf, path, box):
    from reportlab.lib.utils import ImageReader
    placed = fit(path, box)
    pdf.drawImage(ImageReader(str(path)), placed[0] * PDF_SCALE,
                  _pdf_y(placed[1], placed[3]), placed[2] * PDF_SCALE,
                  placed[3] * PDF_SCALE, mask='auto')
    return placed


def _pdf_chart(pdf, slide, charts, _images, regular, _bold, box=None):
    box = box or (MARGIN, BODY_TOP, SLIDE_W - 2 * MARGIN, BODY_BOTTOM - BODY_TOP - 0.35)
    _pdf_image(pdf, charts[slide.chart.key], box)
    if slide.chart.note:
        _pdf_text(pdf, slide.chart.note, MARGIN, BODY_BOTTOM + 0.02, 9.5, regular, 'muted')


def _pdf_chart_table(pdf, slide, charts, images, regular, bold):
    half = (SLIDE_W - 2 * MARGIN) * 0.56
    _pdf_chart(pdf, slide, charts, images, regular, bold,
               box=(MARGIN, BODY_TOP, half, BODY_BOTTOM - BODY_TOP - 0.35))
    _pdf_table(pdf, slide, charts, images, regular, bold,
               box=(MARGIN + half + 0.3, BODY_TOP, SLIDE_W - 2 * MARGIN - half - 0.3,
                    BODY_BOTTOM - BODY_TOP - 0.7))


def _pdf_picture(pdf, slide, _charts, images, regular, _bold, box=None):
    box = box or (MARGIN, BODY_TOP, SLIDE_W - 2 * MARGIN, BODY_BOTTOM - BODY_TOP - 0.3)
    placed = _pdf_image(pdf, images / f'{slide.picture.name}.png', box)
    _pdf_text(pdf, slide.picture.caption, MARGIN, placed[1] + placed[3] + 0.08, 9.5,
              regular, 'muted')


def _pdf_picture_bullets(pdf, slide, charts, images, regular, bold):
    picture_width = (SLIDE_W - 2 * MARGIN) * 0.60
    _pdf_picture(pdf, slide, charts, images, regular, bold,
                 box=(MARGIN, BODY_TOP, picture_width, BODY_BOTTOM - BODY_TOP - 0.3))
    left = MARGIN + picture_width + 0.35
    top = BODY_TOP
    for line in slide.bullets:
        top += _pdf_text(pdf, '•  ' + line, left, top, 11.5, regular, 'ink',
                         SLIDE_W - MARGIN - left) + 0.18


PDF_HANDLERS = {
    'cover': _pdf_cover,
    'section': _pdf_section,
    'bullets': _pdf_bullets,
    'kpis': _pdf_kpis,
    'table': _pdf_table,
    'chart': _pdf_chart,
    'chart_table': _pdf_chart_table,
    'picture': _pdf_picture,
    'picture_bullets': _pdf_picture_bullets,
    'close': _pdf_bullets,
}


# -------------------------------------------------------------------- main --
def build(client, source, engagement, out, charts_dir, images):
    check_menus(client)
    bundle = facts(collect(client), source, engagement)
    slides = deck(bundle)
    check_pictures(slides, images)
    charts = write_charts(slides, charts_dir)
    render_pptx(slides, out, charts, images)
    render_pdf(slides, out.with_suffix('.pdf'), charts, images)
    return {'slides': len(slides), 'charts': len(charts),
            'pictures': len({picture.name for picture in pictures_of(slides)})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='https://okr.aipower.vn')
    parser.add_argument('--db', default='okr_aipower')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default=os.environ.get('OKR_ADMIN_PASSWORD'))
    parser.add_argument('--source', default=str(DEFAULT_SOURCE_DATA))
    parser.add_argument('--engagement', default=str(DEFAULT_ENGAGEMENT))
    parser.add_argument('--images', default=str(DEFAULT_IMAGES))
    parser.add_argument('--charts', default=str(DEFAULT_CHARTS))
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args()
    if not args.password:
        parser.error('pass --password or set OKR_ADMIN_PASSWORD')
    source = json.loads(pathlib.Path(args.source).read_text(encoding='utf-8'))
    engagement_path = pathlib.Path(args.engagement)
    engagement = (json.loads(engagement_path.read_text(encoding='utf-8'))
                  if engagement_path.exists() else {})
    client = Client(args.url, args.db, args.user, args.password)
    out = pathlib.Path(args.out)
    written = build(client, source, engagement, out, pathlib.Path(args.charts),
                    pathlib.Path(args.images))
    print('%s (%s slide)' % (out, written['slides']))
    print('%s' % out.with_suffix('.pdf'))
    print('%s (%s biểu đồ, %s ảnh màn hình)' % (args.charts, written['charts'],
                                                written['pictures']))


if __name__ == '__main__':
    main()
