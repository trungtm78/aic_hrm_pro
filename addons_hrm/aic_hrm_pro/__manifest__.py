# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIC HRM Pro',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'Enterprise OKR/KPI performance management suite: goals, scoring, monitoring, reviews, talent',
    'description': """
AIC HRM Pro — the complete enterprise performance management suite.

Installs the full stack:

- AIC HRM Base: cycles, RAG profiles, scoring engine, security
- AIC OKR & KPI: objectives at five levels, key results, KPI engine,
  check-ins, alert rules, review meetings, pace diagnosis, leadership
  cockpit, alignment tree, Excel/CSV import, rollover
- AIC HRM Review: review route maps, anonymous 360 feedback, calibration,
  9-box, IDP/PIP
- AIC HRM Library: 10 industries x 25 roles of ready-made objective and
  KPI packs, per-role data-collection playbooks, and a built-in guide to
  OKR, the Balanced Scorecard and key success factors

Optional bridges, installed separately when the matching app is present:
AIC HRM Project (task progress feeds key results) and AIC HRM Sale
(quotations, orders and invoices feed sales KPIs).

Ships a fictional demo dataset modelled on a real digital-product
department: weighted objectives totalling 100%, a KPI catalog with
directions and aggregation methods, and personal scorecards summing to
100%.
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://aipower.vn/en',
    'license': 'OPL-1',
    'price': 130.0,
    'currency': 'USD',
    'support': 'sales@aipower.vn',
    # The library ships with the suite. It is a headline reason to buy -
    # 10 industries, 25 roles, ready-made objective/KPI packs and the
    # built-in management guide - so a buyer who installs the app must get
    # it without hunting for a second module.
    'depends': [
        'aic_hrm_base', 'aic_okr_kpi', 'aic_hrm_review', 'aic_hrm_library',
    ],
    'data': [],
    # Listing cover. Odoo reads the first entry as the store image.
    'images': ['static/description/banner.png'],
    'demo': [
        'demo/aic_hrm_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
