# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
{
    'name': 'AIC HRM Pro - OKR/KPI Library',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Performance',
    'summary': 'Role-based OKR and KPI starter library, extensible into company knowledge',
    'description': """
A curated starter library of objectives, key results and KPIs per role
(Sales, Marketing, Engineering, Product, HR, Customer Success, Finance,
Operations, Data, Design, plus industry-specific roles for manufacturing,
trading and professional services) - industry-informed wording written for
this product.

Provides:

- Role catalog with objective templates (+ key result lines) and role-tagged
  KPI templates
- Industry dimension: filter roles by industry (manufacturing, trading,
  services, software); untagged roles apply across industries
- One-click apply: pick an industry and role and a cycle, get draft
  objectives, key results and KPI targets for an employee
- Knowledge capture wizard: administrators paste structured text to grow the
  library into company-specific knowledge (kept per company, separate from
  the shared built-ins)
""",
    'author': 'AIPOWER CO.,LTD',
    'website': 'https://github.com/trungtm78/aic_hrm_pro',
    'license': 'OPL-1',
    'depends': ['aic_okr_kpi'],
    'data': [
        'security/ir.model.access.csv',
        'security/aic_hrm_library_rules.xml',
        'data/aic_hrm_library_roles.xml',
        'data/aic_hrm_library_templates.xml',
        'data/aic_hrm_knowledge.xml',
        'views/aic_hrm_library_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
