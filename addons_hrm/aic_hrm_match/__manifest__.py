# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'Staffing Match',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Employees',
    'summary': 'Rank the people who can actually take a task: availability, '
               'skills, certifications and customer history, every score '
               'backed by the record it came from',
    'description': """
Staffing Match
==============

Answers one question well: *who can take this task, and why them?*

Point it at a project task or raise a standalone staffing request, give it a
window and the effort, and it returns a ranked shortlist. Every number on that
list opens the record it came from - the four tasks that fill someone's
calendar, the three similar projects they delivered, the certificate that
expires before the work ends.

- Hard constraints eliminate, soft criteria rank. Someone who is fully booked is
  not "a low score", they are excluded with the reason shown.
- Nobody is dropped silently. Every evaluated person keeps a record, and every
  exclusion keeps the gate that produced it.
- Twelve criteria, seven enabled out of the box. Weights are data, not code:
  change them, preview the impact against a real past request, then activate.
- The decision is a record. Picking someone other than the top match asks for a
  category and a reason, and the overrides become a report.

Standalone. Depends only on Odoo Community (Employees, Skills, Project).
Two free connectors extend it when the matching apps are installed.
""",
    'author': 'AIPOWER CO., LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'price': 25.0,
    'currency': 'USD',
    'support': 'sales@aipower.vn',
    'depends': ['hr', 'hr_skills', 'project', 'mail', 'web'],
    'data': [
        'security/aic_hrm_match_groups.xml',
        'security/ir.model.access.csv',
        'security/aic_hrm_match_rules.xml',
        'security/aic_hrm_match_rules_cp6.xml',
        'data/aic_hrm_match_data.xml',
    ],
    'assets': {
    },
    'images': [
        'static/description/banner.png',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
    'auto_install': False,
}
