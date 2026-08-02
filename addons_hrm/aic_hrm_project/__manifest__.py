# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIConnect HRM - Project Bridge',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'Key results measured by real project work: task links and automatic progress',
    'description': """
Connects AIConnect HRM Pro key results to Odoo Projects.

Provides:

- Link project tasks to a key result (from either side)
- Automatic KR progress from linked tasks: count-done or percent-done modes,
  synced on task state changes and by a daily safety-net cron
- project.task allowlisted for auto-metric sources out of the box
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['aic_okr_kpi', 'project'],
    'data': [
        'data/aic_hrm_project_data.xml',
        'views/aic_hrm_project_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
