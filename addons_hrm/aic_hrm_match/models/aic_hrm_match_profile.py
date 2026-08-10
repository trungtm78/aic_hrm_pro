# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What the engine needs to know about a person beyond their skills.

Separate from ``hr.employee`` for one reason that matters: cost and billing
rates live here, and a record rule can hide a row but never a column. Putting
them on the employee would mean either every planner sees everyone's rate or
nobody sees any.

Rows are created on demand rather than for every employee up front. Most people
are never candidates, and a table of empty rows is a table nobody maintains and
everybody mistrusts.
"""
from odoo import api, fields, models
from odoo.tools import sql


class AicHrmMatchProfile(models.Model):
    _name = 'aic.hrm.match.profile'
    _description = 'Staffing Profile'
    _order = 'employee_id, id'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one(
        'hr.employee', required=True, index=True, ondelete='cascade')
    # The company the *person* belongs to, kept separate from the company that
    # raises a request: cross-company staffing means those differ, and one
    # company_id cannot express both without blocking the case it exists for.
    resource_company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)

    staffable = fields.Boolean(
        default=True,
        help="Whether this person may appear in a shortlist at all. Turn it "
             "off for roles that are never project-staffed rather than "
             "deleting the record.")
    match_opt_out = fields.Boolean(
        string='Opted out',
        help="Excluded from ranking at the person's own request. Recorded "
             "rather than enforced by removing their data, so a planner can "
             "see that somebody was excluded and why.")
    opt_out_reason = fields.Char()
    available_from = fields.Date(
        help="Earliest date this person can take new work. Somebody joining "
             "next month is a real candidate for work that starts after that.")

    resource_calendar_id = fields.Many2one(
        'resource.calendar', related='employee_id.resource_calendar_id',
        store=True, readonly=True)
    tz = fields.Selection(related='employee_id.tz', store=True, readonly=True)
    work_location_id = fields.Many2one(
        'hr.work.location', related='employee_id.work_location_id',
        store=True, readonly=True)
    willing_to_travel = fields.Boolean()

    seniority_id = fields.Many2one('aic.hrm.match.seniority')
    experience_start_date = fields.Date(
        help="When this person started working in the field, which is not the "
             "same as when they joined this company.")

    # Field-level groups, not a record rule: a rule filters rows, and the thing
    # to hide here is a column.
    currency_id = fields.Many2one(
        'res.currency', related='resource_company_id.currency_id',
        readonly=True)
    cost_hourly = fields.Monetary(
        groups='aic_hrm_match.group_match_admin',
        help="Internal cost per hour, used by the cost-fit criterion.")
    billing_rate_hourly = fields.Monetary(
        groups='aic_hrm_match.group_match_admin')

    max_concurrent_requests = fields.Integer(
        default=0,
        help="How many staffing requests this person may be committed to at "
             "once. Zero means no limit.")

    active = fields.Boolean(default=True)

    def init(self):
        """One profile per person per company, NULL-safe.

        ``resource_company_id`` is required so a plain unique constraint would
        do, but this is expressed the same way as every other scope key in the
        module so the pattern does not have two forms.
        """
        super().init()
        sql.create_unique_index(
            self.env.cr, 'aic_hrm_match_profile_employee_company_uniq',
            self._table, ['employee_id', 'COALESCE(resource_company_id, 0)'])

    # No @api.constrains mirroring the index above. Odoo runs constraints after
    # the row reaches the database, so the index fires first and the check
    # could never run - it would read as protection while doing nothing.
    # Profiles are created by _ensure_profiles rather than typed, so a
    # duplicate is a programming error and the database is the right place to
    # refuse it.

    @api.model
    def _ensure_profiles(self, employees):
        """Return the profiles for these people, creating the missing ones.

        The engine calls this once per run for the whole pool, so it reads and
        creates in batch rather than per employee.
        """
        if not employees:
            return self.browse()
        company = self.env.company
        existing = self.search([
            ('employee_id', 'in', employees.ids),
            ('resource_company_id', '=', company.id),
        ])
        missing = employees - existing.mapped('employee_id')
        created = self.create([
            {'employee_id': employee.id, 'resource_company_id': company.id}
            for employee in missing
        ]) if missing else self.browse()
        return existing | created
