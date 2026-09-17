# -*- coding: utf-8 -*-
"""Check that every screen the customer document names actually exists.

The document tells a customer where to click. When the menu was regrouped,
those directions silently went stale - "menu Hiệu suất → Chu kỳ" still read
fine, and led nowhere. Prose cannot be spell-checked against a product, but
menu labels can.

This reads the bold screen names out of the document and compares them with
the Vietnamese labels of the live menu tree.

    python tools/check_doc_claims.py
    python tools/check_doc_claims.py --url http://127.0.0.1:8073 --db AIC_HRM_Pro
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from seed_uat import Client, OdooRpcError  # noqa: E402

DOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'Docs', 'Gioi-thieu-he-thong-AIC-HRM-Pro.html')

# Words that appear in bold for emphasis, not as a screen name.
NOT_A_SCREEN = {
    'Phần A', 'Phần B', 'Phần C', 'Mới', 'Xem trước', 'Nạp', 'Gửi duyệt',
    'Mở', 'Sinh chương trình họp', 'việc phải làm', 'ba thứ ở giữa hai lần họp',
    'tự chạy', 'dữ liệu', 'Cấu hình', 'đóng băng', 'chặn', 'một nguồn',
    'không đụng dòng nhập tay, không đụng dòng đã xác nhận',
    'Đổi điểm phải nêu lý do, và không xoá được.', 'Lưới 9 ô',
    'đó đúng là chữ hiện trên màn hình', 'Hai lớp tách bạch:',
    'Luật tay thắng máy.', 'Vì sao bắt buộc đúng 100%.',
    'Nói thẳng một hạn chế:', 'Cách đọc:', 'Cách đọc bốn ô đầu:',
    'Đáng chú ý:', 'Nói rõ 5 ca chưa đạt.', 'Đối chiếu được:',
    'Một quy ước giúp tìm nhanh:', 'Tài liệu này chia làm ba phần.',
    'Vì sao phải tính kỳ vọng theo lịch đã trôi.',
    'Mỗi lần check-in được giữ lại như một mốc lịch sử',
    'Đọc con số hiệu năng cho đúng:', 'Một yếu tố thành công không có chỉ tiêu nào đo',
    'Lời nhắc gắn thẳng vào bản ghi', 'tệ nhất lên trước',
    'Dòng báo cáo tiến độ', 'thứ tự công việc trong năm', 'giá trị hiện tại',
    'mức tự tin', 'vướng mắc', 'nháp', 'kết quả then chốt', 'ngưỡng RAG',
    'trần điểm', 'Bước 1', 'Bước 2', 'Bước 3', 'Bước 4',
}


def screen_names(html):
    """Bold words that look like a screen name: short, capitalised, no verb.

    A direction is often written as a path - "Hiệu suất → Kế hoạch → Chu kỳ" -
    and every segment of it has to be a real label, so the path is split and
    each piece checked on its own. That is precisely the check that was
    missing when the menu was regrouped.
    """
    found = set()
    for match in re.findall(r'<b>([^<]{2,60})</b>', html):
        for piece in re.split(r'[→>]', match):
            name = piece.strip().rstrip('.:,')
            if not name or name in NOT_A_SCREEN:
                continue
            if name[0].islower() or name[0].isdigit():
                continue
            if re.match(r'^[\d\s%/.,+−-]+$', name):
                continue
            if len(name.split()) > 5:
                continue
            found.add(name)
    return sorted(found)


def menu_labels(client):
    root = client.execute('ir.model.data', 'check_object_reference',
                          'aic_hrm_base', 'menu_aic_hrm_root')[1]
    labels, frontier = set(), [root]
    while frontier:
        children = client.execute(
            'ir.ui.menu', 'search_read', [['parent_id', 'in', frontier]],
            ['name'], context={'lang': 'vi_VN'})
        frontier = [child['id'] for child in children]
        labels.update(child['name'].strip() for child in children)
    return labels


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--doc', default=DOC)
    parser.add_argument('--url', default='https://okr.aipower.vn')
    parser.add_argument('--db', default='okr_aipower')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default=os.environ.get('OKR_ADMIN_PASSWORD'))
    args = parser.parse_args(argv)
    if not args.password:
        parser.error('pass --password or set OKR_ADMIN_PASSWORD')

    html = io.open(args.doc, encoding='utf-8').read()
    client = Client(args.url, args.db, args.user, args.password)
    labels = menu_labels(client)
    print('menu labels on %s: %s' % (args.db, len(labels)))

    named = screen_names(html)
    hits = [n for n in named if n in labels]
    misses = [n for n in named if n not in labels]

    print('bold names in the document: %s' % len(named))
    print('  match a real menu:   %s' % len(hits))
    print('  not a menu label:    %s' % len(misses))
    print('\nNames the document uses that are NOT menu labels')
    print('(each one is either prose emphasis - fine - or a wrong direction):')
    for name in misses:
        print('   %s' % name)

    # Coverage is measured against the whole text, not only the bold names: a
    # screen named in a table or a diagram box is documented just as well.
    text = re.sub(r'<[^>]+>', ' ', html)
    unmentioned = sorted(label for label in labels if label not in text)
    print('\nMenu labels the document never mentions anywhere: %s'
          % (len(unmentioned) or 'none'))
    for label in unmentioned:
        print('   %s' % label)
    return 1 if unmentioned else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except OdooRpcError as error:
        print('RPC error: %s' % error, file=sys.stderr)
        sys.exit(2)
