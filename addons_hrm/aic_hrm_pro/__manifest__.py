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
- AIC OKR & KPI: objectives, key results, KPI engine, check-ins, dashboards, Excel import
- AIC HRM Review: review route maps, 360 feedback, calibration, 9-box, IDP/PIP

Ships a fictional demo dataset modelled on a real digital-product
department: weighted objectives totalling 100%, a KPI catalog with
directions and aggregation methods, and personal scorecards summing to
100%.
""",
    'author': 'AIPOWER CO.,LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'price': 149.0,
    'currency': 'USD',
    'support': 'ai.1click2power@gmail.com',
    'depends': ['aic_hrm_base', 'aic_okr_kpi', 'aic_hrm_review'],
    'data': [],
    'demo': [
        'demo/aic_hrm_demo.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
