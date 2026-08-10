# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'Staffing OKR Link',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Feed scorecard results and key-result outcomes into staffing '
               'decisions when the performance suite is installed',
    'description': """
Staffing OKR Link
=================

Free connector. Installs itself once both Staffing Match and the OKR/KPI engine
are present, and does nothing otherwise.

- Adds past-performance criteria sourced from personal scorecards. They ship
  flagged as sensitive, so a planner sees the ranking without seeing anyone's
  performance figures unless they hold the data-access group.
- Stamps delivery outcomes onto the experience ledger from the key result a
  task delivered against, replacing the neutral default with a real signal.
- Lets a staffing request draw its candidate pool from a performance team.

Removing this module leaves historical rankings readable: every score line keeps
its own copy of the criterion that produced it.
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['aic_hrm_match', 'aic_okr_kpi'],
    'data': [
    ],
    'installable': True,
    'application': False,
    'auto_install': True,
}
