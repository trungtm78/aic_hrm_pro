# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""What somebody has actually done, denormalised so the engine can read it fast.

Two criteria depend on this table completely - "has done similar work" and "has
worked for this customer" - and both are asked for two thousand people at once.
Deriving them live from ``project.task`` at ranking time is the difference
between a shortlist that returns and one the planner gives up waiting for.

It is also the evidence store. A score of 0.80 on customer familiarity has to
open into the four engagements behind it, so a row keeps the dates, the hours
and the record it came from rather than only contributing to a total.

Feeders (allocations, timesheets, a connector) each name their own rows through
``source`` plus ``source_key``. Keying on ``(employee, source, task)`` instead
looks obvious and is wrong twice: one person can hold two roles on one task, and
a timesheet line has no stable task of its own.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import sql

from . import utils


class AicHrmMatchExperience(models.Model):
    _name = 'aic.hrm.match.experience'
    _description = 'Staffing Experience Entry'
    _order = 'date_end desc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', required=True, index=True,
        default=lambda self: self.env.company)

    source = fields.Selection([
        ('allocation', 'Booking'),
        ('timesheet', 'Timesheet'),
        ('manual', 'Entered by hand'),
        ('import', 'Imported'),
        ('bridge', 'From a connector'),
    ], required=True, default='manual')
    source_key = fields.Char(
        required=True, index=True,
        help="Stable identity of the record this entry was derived from. Each "
             "feeder names its own rows, which is what lets a rebuild run "
             "twice without doubling the ledger.")
    source_model = fields.Char()
    source_res_id = fields.Many2oneReference(model_field='source_model')

    # set null, never cascade: the ledger is the record that somebody did the
    # work, and tidying up a task must not erase their history from every
    # future ranking.
    task_id = fields.Many2one('project.task', ondelete='set null', index=True)
    project_id = fields.Many2one('project.project', ondelete='set null')
    partner_id = fields.Many2one('res.partner', ondelete='set null', index=True)
    commercial_partner_id = fields.Many2one(
        'res.partner', related='partner_id.commercial_partner_id',
        store=True, index=True,
        help="The customer group. Work for a subsidiary counts towards the "
             "parent, which is how a planner thinks about the relationship.")

    date_start = fields.Date(required=True, index=True)
    date_end = fields.Date(required=True, index=True)
    hours = fields.Float()
    role = fields.Char()
    seniority_id = fields.Many2one('aic.hrm.match.seniority')
    is_lead_role = fields.Boolean()

    # Snapshotted at the time, not read live: what mattered about a project in
    # 2024 is what it was tagged with then, and re-tagging it later must not
    # rewrite somebody's history.
    tag_ids = fields.Many2many('aic.hrm.match.tag', string='Tags at the time')
    skill_ids = fields.Many2many('hr.skill', string='Skills used')

    outcome_score = fields.Float(
        help="How well it went, from 0 to 1, when something knows. Left empty "
             "rather than defaulted: inventing a number here would put a "
             "fabricated observation into the customer-affinity score.")
    outcome_source = fields.Char()

    # Deliberately a plain stored field with a cron behind it, not a compute.
    # A computed value that depends on the current date is stale the moment it
    # is written, and the engine recomputes against the run's frozen as_of
    # rather than trusting this. It exists so lists can sort and filter.
    recency_weight = fields.Float(
        default=1.0, readonly=True,
        help="Display-only decay, refreshed nightly. Ranking never reads it; "
             "it recomputes decay against the moment the run was frozen.")

    def init(self):
        """One row per source record per company.

        Company is part of the key because feeders number their own records:
        two companies running the same connector will produce the same key for
        different facts.
        """
        super().init()
        sql.create_unique_index(
            self.env.cr, 'aic_hrm_match_experience_source_uniq',
            self._table, ['COALESCE(company_id, 0)', 'source', 'source_key'])

    @api.constrains('outcome_score')
    def _check_outcome_score(self):
        for entry in self:
            if entry.outcome_score and not 0.0 <= entry.outcome_score <= 1.0:
                raise ValidationError(_(
                    "An outcome is a score between 0 and 1; %(value)s is "
                    "outside that.", value=entry.outcome_score))

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for entry in self:
            if entry.date_end < entry.date_start:
                raise ValidationError(_(
                    "An experience entry cannot end before it starts."))

    @api.model
    def _cron_refresh_recency(self):
        """Refresh the display-only decay.

        Runs nightly and in batches. Being a day out of date costs nothing,
        because nothing that decides anything reads this field.
        """
        today = fields.Date.context_today(self)
        for entry in self.search([]):
            age = (today - entry.date_end).days if entry.date_end else None
            entry.recency_weight = utils.half_life_decay(
                age_days=age, half_life_days=730.0, grace_days=0.0, floor=0.0)
