# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIC OKR & KPI',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'OKR and KPI management: objectives, key results, KPI engine, check-ins, assignments, dashboards',
    'description': """
Core OKR / KPI performance management for the AIC HRM Pro suite.

Provides:

- Objectives with weights, committed/aspirational types and cross-cycle alignment
- Key results with four metric types, baselines, targets and weighted roll-up scoring
- KPI library (KPI Institute documentation form) with cycle targets and period results
- Personal KPI assignments with a 100% weight gate and composite scoring
- Periodic check-ins with confidence tracking, stale-goal detection and alert rules
- Review meetings with auto-generated agendas and tracked action items
- Excel import wizard (3-sheet OKR/KPI/assignment) and cycle rollover wizard
- OWL alignment tree and leadership cockpit dashboards
""",
    'author': 'AIPOWER CO.,LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['aic_hrm_base'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/ir.model.access.csv',
        'security/aic_okr_kpi_rules.xml',
        'views/aic_hrm_objective_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
