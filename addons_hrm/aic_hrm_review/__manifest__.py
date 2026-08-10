# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'Appraisal 360',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'AIConnect review cycles: route maps, anonymous 360 feedback, calibration, 9-box, IDP and PIP',
    'description': """
Performance review suite for AIConnect HRM Pro.

Provides:

- Review templates with configurable stage route maps (self / manager / peer / upward / calibration / sign-off)
- Review cycles that snapshot goal scores from a performance cycle
- Anonymous 360 feedback with minimum-rater aggregation rules
- Calibration sessions with mandatory justification for score changes
- 9-box grid (performance x potential) with drag calibration
- Individual development plans (IDP) and performance improvement plans (PIP)
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['aic_okr_kpi'],
    'data': [
        'security/ir.model.access.csv',
        'security/aic_hrm_review_rules.xml',
        'views/aic_hrm_review_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
