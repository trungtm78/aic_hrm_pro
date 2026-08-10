# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The demand side: what needs staffing, and what each seat requires.

A **slot** is the unit of staffing, not the request. "We need three people" is
not one requirement repeated three times - the seats have different skills,
different effort, and filling all three with the same person is not an answer.
Making the slot the unit is what lets required hours mean something exact, and
what stops one person's capacity being counted against two seats.

A request also outlives the task that prompted it. It holds why somebody was
chosen, so deleting a tidied-up task must not take the decision record with it.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

REQUEST_SEQUENCE = 'aic.hrm.match.request'


class AicHrmMatchRequest(models.Model):
    _name = 'aic.hrm.match.request'
    _description = 'Staffing Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True, tracking=True)
    reference = fields.Char(
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'),
        help="Quoted in meetings, and the key the tie-break is salted with so "
             "re-running a request produces the same order.")
    request_type = fields.Selection([
        ('task', 'From a task'),
        ('role', 'A role on a project'),
        ('standalone', 'Standalone need'),
    ], default='standalone', required=True)

    # set null, never cascade: the request is the record of a decision, and a
    # deleted task must not be able to erase it.
    task_id = fields.Many2one('project.task', ondelete='set null', index=True)
    task_ref_snapshot = fields.Char(readonly=True)
    project_id = fields.Many2one('project.project', ondelete='set null')
    partner_id = fields.Many2one(
        'res.partner', compute='_compute_partner_id', store=True,
        readonly=False, index=True, string='Customer')

    date_start = fields.Datetime(required=True, tracking=True)
    date_end = fields.Datetime(required=True, tracking=True)
    priority = fields.Selection([
        ('0', 'Normal'), ('1', 'Important'), ('2', 'Urgent'),
    ], default='0')

    request_company_id = fields.Many2one(
        'res.company', required=True, index=True, string='Requesting company',
        default=lambda self: self.env.company)
    company_ids = fields.Many2many(
        'res.company', string='Companies to staff from',
        help="Which companies candidates may come from. Defaults to the "
             "requesting company; widening it is what cross-company staffing "
             "means, and it is deliberately opt-in.")

    slot_ids = fields.One2many(
        'aic.hrm.match.request.slot', 'request_id', string='Slots')
    run_ids = fields.One2many(
        'aic.hrm.match.run', 'request_id', string='Rankings')
    latest_run_id = fields.Many2one(
        'aic.hrm.match.run', compute='_compute_latest_run_id',
        help="The most recent ranking that actually produced something. "
             "max(id) would point the screen at a failed or half-built run.")
    headcount = fields.Integer(
        compute='_compute_headcount', store=True,
        help="How many people this request needs. Derived from the slots "
             "rather than typed, so the two cannot disagree.")

    # Only advances when a decision is made, never on a re-rank. It is what
    # rotates tie-breaks between genuine staffing rounds while keeping a rerun
    # of the same round stable.
    rotation_epoch = fields.Integer(default=0, readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ranked', 'Ranked'),
        ('decided', 'Decided'),
        ('staffed', 'Staffed'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], default='draft', required=True, tracking=True)
    active = fields.Boolean(default=True)

    _reference_company_uniq = models.Constraint(
        'unique (reference, request_company_id)',
        'That staffing reference is already used in this company.',
    )

    @api.depends('run_ids.state', 'run_ids.as_of')
    def _compute_latest_run_id(self):
        for request in self:
            usable = request.run_ids.filtered(
                lambda run: run.state in ('computed', 'decided'))
            request.latest_run_id = usable.sorted(
                key=lambda run: (run.as_of or fields.Datetime.now(), run.id),
                reverse=True)[:1]

    @api.depends('slot_ids')
    def _compute_headcount(self):
        for request in self:
            request.headcount = len(request.slot_ids)

    @api.depends('project_id')
    def _compute_partner_id(self):
        for request in self:
            if request.project_id.partner_id:
                request.partner_id = request.project_id.partner_id

    @api.constrains('date_start', 'date_end')
    def _check_window(self):
        for request in self:
            if request.date_end <= request.date_start:
                raise ValidationError(_(
                    "%(name)s must end after it starts.",
                    name=request.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('task_id'):
                task = self.env['project.task'].browse(vals['task_id'])
                vals.setdefault('task_ref_snapshot', task.display_name)
                vals.setdefault('project_id', task.project_id.id)
            if not vals.get('reference') or vals['reference'] == _('New'):
                company = vals.get('request_company_id') or self.env.company.id
                vals['reference'] = self.env['ir.sequence'].with_company(
                    company).next_by_code(REQUEST_SEQUENCE) or _('New')
            if not vals.get('company_ids'):
                vals['company_ids'] = [(6, 0, [
                    vals.get('request_company_id') or self.env.company.id])]
        return super().create(vals_list)

    def unlink(self):
        """A request that reached a decision is evidence, not scratch work.

        Archiving keeps the trail; deleting removes the only record of who was
        considered and why they were not chosen.
        """
        decided = self.filtered(lambda r: r.state not in ('draft', 'cancelled'))
        if decided:
            raise ValidationError(_(
                "%(names)s already carry staffing decisions. Archive them "
                "instead of deleting - the ranking behind a decision is the "
                "only record of why the other candidates were not chosen.",
                names=', '.join(decided.mapped('display_name'))))
        return super().unlink()


class AicHrmMatchRequestSlot(models.Model):
    """One seat to fill."""
    _name = 'aic.hrm.match.request.slot'
    _description = 'Staffing Slot'
    _order = 'request_id, sequence, id'

    request_id = fields.Many2one(
        'aic.hrm.match.request', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)

    # Read from the request rather than repeated, so a planner cannot leave the
    # seat and the engagement disagreeing about when the work happens.
    date_start = fields.Datetime(related='request_id.date_start', store=True)
    date_end = fields.Datetime(related='request_id.date_end', store=True)
    company_id = fields.Many2one(
        'res.company', related='request_id.request_company_id', store=True)

    required_hours = fields.Float(
        help="Effort this seat needs. Belongs to the slot, not the request: "
             "two seats on one engagement rarely need the same effort.")
    fte_ratio = fields.Float(
        default=1.0,
        help="Used instead of required hours when the need is expressed as a "
             "share of somebody's time.")
    seniority_id = fields.Many2one('aic.hrm.match.seniority')
    job_id = fields.Many2one('hr.job')
    allow_partial_availability = fields.Boolean(
        help="Accept somebody who can cover most of the effort rather than "
             "all of it. Off by default: a half-available person on a full-time "
             "seat is a staffing problem deferred, not solved.")

    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    max_hourly_cost = fields.Monetary(currency_field='currency_id')

    skill_line_ids = fields.One2many(
        'aic.hrm.match.request.slot.skill', 'slot_id', string='Skills required')
    required_certification_skill_ids = fields.Many2many(
        'hr.skill', string='Certifications required',
        help="Credentials the work cannot be done without. Kept apart from the "
             "skills above because they are not a matter of degree: somebody "
             "holds a valid one for the whole window or they are not offered, "
             "and no weighting makes an expired licence acceptable.")
    assigned_employee_id = fields.Many2one(
        'hr.employee', readonly=True, ondelete='set null',
        help="Filled from the decision, never typed.")

    @api.constrains('required_hours', 'fte_ratio')
    def _check_effort(self):
        for slot in self:
            if slot.required_hours < 0.0:
                raise ValidationError(_(
                    "A slot cannot require negative hours."))
            if slot.fte_ratio < 0.0:
                raise ValidationError(_(
                    "A slot cannot require a negative share of somebody's "
                    "time."))


class AicHrmMatchRequestSlotSkill(models.Model):
    """One capability a seat needs, and how much of it."""
    _name = 'aic.hrm.match.request.slot.skill'
    _description = 'Staffing Slot Skill Requirement'
    _order = 'slot_id, sequence, id'
    _rec_name = 'skill_id'

    slot_id = fields.Many2one(
        'aic.hrm.match.request.slot', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    skill_id = fields.Many2one('hr.skill', required=True, ondelete='restrict')
    skill_type_id = fields.Many2one(
        'hr.skill.type', related='skill_id.skill_type_id', store=True)
    min_level_id = fields.Many2one('hr.skill.level', ondelete='restrict')
    min_level_progress = fields.Float(
        compute='_compute_min_level_progress', store=True,
        help="The minimum level expressed on the 0-100 scale the engine "
             "compares against.")

    requirement = fields.Selection([
        ('mandatory', 'Mandatory'),
        ('important', 'Important'),
        ('nice_to_have', 'Nice to have'),
    ], default='important', required=True,
        help="Mandatory eliminates; the others only move the score.")
    weight = fields.Float(default=1.0)
    stretch_allowed = fields.Boolean(
        help="Allow somebody slightly below the minimum to be considered, as "
             "a development opportunity. Off by default: relaxing a mandatory "
             "requirement has to be a deliberate act on the requirement "
             "itself, not a side effect of a fairness setting elsewhere.")

    @api.depends('min_level_id.level_progress')
    def _compute_min_level_progress(self):
        for line in self:
            line.min_level_progress = line.min_level_id.level_progress or 0.0

    @api.constrains('skill_id', 'min_level_id')
    def _check_level_belongs_to_skill_type(self):
        for line in self:
            if not line.min_level_id:
                continue
            if line.min_level_id.skill_type_id != line.skill_id.skill_type_id:
                raise ValidationError(_(
                    "Level %(level)s belongs to %(other)s, not to %(skill)s. "
                    "Comparing across two scales makes the gap meaningless.",
                    level=line.min_level_id.display_name,
                    other=line.min_level_id.skill_type_id.display_name,
                    skill=line.skill_id.display_name))

    @api.constrains('slot_id', 'skill_id')
    def _check_skill_listed_once(self):
        for line in self:
            duplicate = self.search_count([
                ('id', '!=', line.id),
                ('slot_id', '=', line.slot_id.id),
                ('skill_id', '=', line.skill_id.id),
            ])
            if duplicate:
                raise ValidationError(_(
                    "%(skill)s is already required on this slot. Raise the "
                    "minimum level instead of listing it twice.",
                    skill=line.skill_id.display_name))
