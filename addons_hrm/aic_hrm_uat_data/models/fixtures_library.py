# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Library fixtures: a role pack before and after it is applied.

Applying a pack has to produce DRAFT objectives - a starting point somebody
edits, never an approved plan the library decided on its own. And applying the
same pack twice has to be safe, because the second click is a normal human
event, not an abuse case.
"""
from odoo import api, models


class AicHrmUatFixtureLibrary(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def _catalog(self):
        catalog = super()._catalog()
        catalog.update({
            'library.unapplied.D0': {
                'doc': "A company-owned role pack with one objective "
                       "template and two key-result lines, applied to "
                       "nothing yet.",
                'entity': 'library', 'state': 'unapplied', 'lifecycle': 'D0',
                'shape': 'normal',
                'depends': ['org.base.D0'],
                'setup': '_setup_library_pack',
                'outputs': ['industry_id', 'role_id', 'template_id',
                            'kr_line_count'],
            },
            'library.applied.D0': {
                'doc': "The same pack applied to one person: draft "
                       "objectives, the employee stamped with the role, and "
                       "a second apply that must not double anything.",
                'entity': 'library', 'state': 'applied', 'lifecycle': 'D0',
                'shape': 'normal',
                'depends': ['library.unapplied.D0', 'cycle.open.D-45'],
                'setup': '_setup_library_applied',
                'outputs': ['objective_ids', 'employee_id', 'role_id',
                            'objective_count_after_first_apply'],
            },
        })
        return catalog

    def _setup_library_pack(self, ctx):
        industry = self.env['aic.hrm.library.industry'].create({
            'name': 'UAT Software & SaaS', 'code': 'UAT-SAAS',
        })
        self._track([industry])
        role = self.env['aic.hrm.library.role'].create({
            'name': 'UAT Product Designer',
            'code': 'UAT-DESIGNER',
            'industry_ids': [(4, industry.id)],
            'description': 'UAT role pack used by the acceptance dataset.',
            'collection_playbook': 'UAT: pull usage from the product '
                                   'analytics export every Monday.',
        })
        self._track([role])
        template = self.env['aic.hrm.objective.template'].create({
            'name': 'UAT Make the product easier to adopt',
            'role_id': role.id,
            'objective_type': 'committed',
            'description': 'UAT template objective.',
            'kr_line_ids': [
                (0, 0, {'name': 'UAT Task success rate',
                        'metric_type': 'percent', 'direction': 'higher',
                        'unit': '%', 'default_target': 90.0, 'weight': 1.0}),
                (0, 0, {'name': 'UAT Time on task',
                        'metric_type': 'number', 'direction': 'lower',
                        'unit': 'seconds', 'default_target': 45.0,
                        'weight': 1.0}),
            ],
        })
        self._track([template])
        return {'industry_id': industry.id, 'role_id': role.id,
                'template_id': template.id,
                'kr_line_count': len(template.kr_line_ids)}

    def _setup_library_applied(self, ctx):
        pack = ctx['library.unapplied.D0']
        org = ctx['org.base.D0']
        cycle = self.env['aic.hrm.cycle'].browse(
            ctx['cycle.open.D-45']['cycle_id'])
        template = self.env['aic.hrm.objective.template'].browse(
            pack['template_id'])
        employee = self.env['hr.employee'].browse(org['member_employee_id'])

        created = template.action_apply(cycle, employee=employee)
        self._track(created)
        first_count = len(created)

        # The role a pack was applied from becomes a property of the person,
        # which is what makes "progress by library role" answerable.
        employee.aic_library_role_id = pack['role_id']

        return {
            'objective_ids': created.ids,
            'employee_id': employee.id,
            'role_id': pack['role_id'],
            'objective_count_after_first_apply': first_count,
        }
