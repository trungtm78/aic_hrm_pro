# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIConnect HRM Base - Cycles, Scoring & Access',
    'version': '18.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'Foundation for the AIConnect HRM Pro suite: performance cycles, RAG profiles, scoring engine, security',
    'description': """
Foundation module for the AIConnect HRM Pro performance management suite.

Provides:

- Performance cycles (year / half / quarter / month / custom periods) with lifecycle states and locking
- Configurable RAG (Red-Amber-Green) threshold profiles
- Target revision engine (mid-cycle change governance with approval and full history)
- Auto-metric sources (pull values from any Odoo model, admin-governed allowlist)
- Shared owner / scoring mixins and pure scoring math utilities
- Security groups and manager-chain record rules
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['hr', 'mail', 'web'],
    'data': [
        'security/aic_hrm_groups.xml',
        'security/ir.model.access.csv',
        'security/aic_hrm_rules.xml',
        'data/aic_hrm_data.xml',
        'views/aic_hrm_cycle_views.xml',
        'views/aic_hrm_config_views.xml',
        'views/aic_hrm_menus.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
