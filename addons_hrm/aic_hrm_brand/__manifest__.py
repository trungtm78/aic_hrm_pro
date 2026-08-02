# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIConnect HRM - White Label',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'Present the suite under the customer-facing product identity',
    'description': """
AIConnect HRM Pro — white label
=========================

A performance suite is sold as a product, not as a stack. This module
replaces the platform's own identity on the surfaces an end user sees:
the browser title, the favicon, the login footer, the help links in the
user menu, and the automation account that authors tracking messages.

It changes presentation only. Source headers, LICENSE files, the
technical documentation and every third-party copyright notice stay
exactly as they are - removing those would be a licence violation,
and none of them is visible to someone using the application.
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://aipower.vn',
    'license': 'OPL-1',
    'depends': ['web', 'aic_hrm_base'],
    'data': [
        'data/brand_identity.xml',
        'views/brand_templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'aic_hrm_brand/static/src/brand_user_menu.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
