# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIConnect HRM UAT Data (internal)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'Named, reproducible UAT fixtures for the AIConnect HRM suite',
    'description': """
INTERNAL TESTING MODULE - NEVER SHIPPED TO A CUSTOMER.

Builds the UAT dataset as a named asset: every state in the product's
state maps, every lifecycle position that matters (fresh, mid-flight,
stale) and every collection shape (empty, normal, full, with holes),
each one addressable by a fixture id and each one with a cleanup recipe
that provably returns the database to where it started.

It exposes an RPC that creates business data, which is exactly why it is
withheld from the Apps Store package (tools/build_store_package.py) and
why aic_hrm_pro/tests/test_packaging.py asserts its absence. On top of
the module boundary it is gated twice at runtime: HR administrator group
AND the `aic_hrm.uat_mode` system parameter.
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://aipower.vn/en',
    'license': 'OPL-1',
    'depends': [
        'aic_hrm_base', 'aic_okr_kpi', 'aic_hrm_review', 'aic_hrm_library',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/uat_mode.xml',
        'views/aic_hrm_uat_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
