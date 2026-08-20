# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Org-chart fixtures: the people every other fixture hangs off.

The awkward people are the point. A suite that only ever tests employees who
have a login, a department and a job position never meets the ones that break
it: the external rater nobody can speak for, the leaver whose scorecard still
exists, the employee an import created from a spreadsheet cell with no
position column filled in.
"""
from odoo import api, models


class AicHrmUatFixtureOrg(models.Model):
    _inherit = 'aic.hrm.uat.fixture'

    @api.model
    def _catalog(self):
        catalog = super()._catalog()
        catalog['org.base.D0'] = {
            'doc': "Three departments, two job positions, and the full cast: "
                   "HR admin, manager, member, three peers, an external rater "
                   "with no login, a leaver, an employee with no department "
                   "and an employee with no job position.",
            'entity': 'org',
            'state': 'base',
            'lifecycle': 'D0',
            'shape': 'normal',
            'depends': [],
            'setup': '_setup_org_base',
            'outputs': [
                'company_id', 'dept_product_id', 'dept_success_id',
                'dept_finance_id', 'job_pm_id', 'job_designer_id',
                'admin_user_id', 'manager_user_id', 'member_user_id',
                'admin_login', 'manager_login', 'member_login', 'password',
                'manager_employee_id', 'member_employee_id',
                'peer_employee_ids', 'external_rater_id', 'leaver_id',
                'no_department_employee_id', 'no_job_employee_id',
            ],
        }
        return catalog

    # Shared by every persona the UAT run logs in as. A single well-known
    # password keeps the Playwright side free of a credential store; the
    # database it belongs to is locked to UAT by dbfilter and never leaves
    # this machine.
    UAT_PASSWORD = 'uat_demo_2026'

    def _make_user(self, name, login, group_xmlids):
        user = self.env['res.users'].create({
            'name': name,
            'login': login,
            'password': self.UAT_PASSWORD,
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
            ] + [self.env.ref(x).id for x in group_xmlids])],
        })
        return self._track([user])[0]

    def _setup_org_base(self, ctx):
        env = self.env
        company = env.company

        departments = env['hr.department'].create([
            {'name': 'UAT Digital Products'},
            {'name': 'UAT Customer Success'},
            {'name': 'UAT Finance'},
        ])
        self._track(departments)
        product, success, finance = departments

        jobs = env['hr.job'].create([
            {'name': 'UAT Product Manager', 'department_id': product.id},
            {'name': 'UAT UI/UX Designer', 'department_id': product.id},
        ])
        self._track(jobs)
        job_pm, job_designer = jobs

        admin_user = self._make_user(
            'UAT HR Admin', 'uat_admin', ['aic_hrm_base.group_hrm_admin'])
        manager_user = self._make_user(
            'UAT Manager', 'uat_manager', ['aic_hrm_base.group_hrm_manager'])
        member_user = self._make_user(
            'UAT Member', 'uat_member', ['aic_hrm_base.group_hrm_user'])
        peer_users = [
            self._make_user('UAT Peer %s' % index, 'uat_peer%s' % index,
                            ['aic_hrm_base.group_hrm_user'])
            for index in (1, 2, 3)
        ]

        Employee = env['hr.employee']
        manager = Employee.create({
            'name': 'UAT Manager', 'user_id': manager_user.id,
            'department_id': product.id, 'job_id': job_pm.id,
            'company_id': company.id,
        })
        self._track([manager])

        member = Employee.create({
            'name': 'UAT Member', 'user_id': member_user.id,
            'department_id': product.id, 'job_id': job_designer.id,
            'parent_id': manager.id, 'company_id': company.id,
        })
        self._track([member])

        peers = Employee.create([
            {'name': 'UAT Peer %s' % index, 'user_id': user.id,
             'department_id': product.id, 'job_id': job_designer.id,
             'parent_id': manager.id, 'company_id': company.id}
            for index, user in zip((1, 2, 3), peer_users)
        ])
        self._track(peers)

        # No login of their own: the '360 external' role, and every employee
        # the spreadsheet import creates for a name it could not match. The
        # forgery hole fixed in aic_hrm_review lived exactly here.
        external = Employee.create({
            'name': 'UAT External Rater', 'department_id': success.id,
            'company_id': company.id,
        })
        self._track([external])

        # A leaver still owns last cycle's scorecard. Archived, not deleted.
        leaver = Employee.create({
            'name': 'UAT Leaver', 'department_id': success.id,
            'job_id': job_designer.id, 'company_id': company.id,
        })
        self._track([leaver])
        leaver.active = False

        no_department = Employee.create({
            'name': 'UAT No Department', 'company_id': company.id})
        self._track([no_department])

        no_job = Employee.create({
            'name': 'UAT No Job Position', 'department_id': finance.id,
            'company_id': company.id})
        self._track([no_job])

        return {
            'company_id': company.id,
            'dept_product_id': product.id,
            'dept_success_id': success.id,
            'dept_finance_id': finance.id,
            'job_pm_id': job_pm.id,
            'job_designer_id': job_designer.id,
            'admin_user_id': admin_user.id,
            'manager_user_id': manager_user.id,
            'member_user_id': member_user.id,
            'admin_login': admin_user.login,
            'manager_login': manager_user.login,
            'member_login': member_user.login,
            'password': self.UAT_PASSWORD,
            'manager_employee_id': manager.id,
            'member_employee_id': member.id,
            'peer_employee_ids': peers.ids,
            'external_rater_id': external.id,
            'leaver_id': leaver.id,
            'no_department_employee_id': no_department.id,
            'no_job_employee_id': no_job.id,
        }
