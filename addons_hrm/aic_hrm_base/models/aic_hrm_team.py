# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AicHrmTeam(models.Model):
    """A working team inside (or across) departments.

    Departments give the org chart; teams give the delivery unit goals
    are actually set for. A team-level objective anchors here.
    """
    _name = 'aic.hrm.team'
    _description = 'Performance Team'
    _order = 'name'

    name = fields.Char(required=True)
    department_id = fields.Many2one(
        'hr.department',
        help="Home department; leave empty for cross-functional teams.")
    lead_id = fields.Many2one('hr.employee', string='Team Lead')
    member_ids = fields.Many2many(
        'hr.employee', 'aic_hrm_team_member_rel', 'team_id', 'employee_id',
        string='Members')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)
    active = fields.Boolean(default=True)

    _name_company_uniq = models.Constraint(
        'unique (name, company_id)',
        'A team with this name already exists in this company.',
    )
