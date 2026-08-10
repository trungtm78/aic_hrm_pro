# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""One ranking, kept whole so it can be defended later.

Three levels, and each exists for a reason a two-level design would lose.

``run`` freezes the moment and the parameters. Weights move on, so without it
"why was she chosen in March" has no answer in June. It is immutable once
computed: re-ranking creates a new run rather than rewriting what a decision
was based on.

``candidate`` is one person's outcome - including the people who were excluded.
The invariant the whole product rests on is that nobody is dropped silently: a
ranking that quietly omits people is worse than no ranking, because it looks
complete.

``score.line`` and its evidence are why. The number on the shortlist has to be
the one the breakdown adds up to, and each line points at the records behind it
so a score is a link rather than an opinion.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError

RUN_SEQUENCE = 'aic.hrm.match.run'

# Fields a computed run may still accept. Everything else is the record of what
# happened, and a record of what happened that can be edited is not one.
_MUTABLE_AFTER_COMPUTE = {'state', 'notes', 'compare_run_id'}


class AicHrmMatchRun(models.Model):
    _name = 'aic.hrm.match.run'
    _description = 'Staffing Ranking Run'
    _inherit = ['mail.thread']
    _order = 'as_of desc, id desc'

    reference = fields.Char(
        required=True, copy=False, readonly=True, index=True,
        default=lambda self: _('New'))
    request_id = fields.Many2one(
        'aic.hrm.match.request', required=True, index=True, ondelete='cascade')
    slot_id = fields.Many2one(
        'aic.hrm.match.request.slot', index=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', related='request_id.request_company_id', store=True,
        index=True)

    policy_id = fields.Many2one(
        'aic.hrm.match.policy', required=True, ondelete='restrict')
    policy_version = fields.Integer(readonly=True)

    as_of = fields.Datetime(
        readonly=True,
        help="The moment this ranking was frozen. Every decay and validity "
             "check inside it is measured against this, not against now, so "
             "reopening the run tomorrow shows the same scores.")
    user_id = fields.Many2one('res.users', readonly=True,
                              default=lambda self: self.env.user)
    parameter_snapshot = fields.Text(
        readonly=True,
        help="What the run was configured with, resolved: the policy weights, "
             "the pool, the frozen moment. Enough to explain the ranking after "
             "the policy has moved on.")
    input_hash = fields.Char(
        readonly=True, index=True,
        help="Fingerprint of the inputs. Two runs with the same fingerprint "
             "saw the same world and must produce the same order.")

    candidate_ids = fields.One2many(
        'aic.hrm.match.candidate', 'run_id', string='Candidates')
    candidate_count = fields.Integer(readonly=True)
    eligible_count = fields.Integer(readonly=True)
    rejected_count = fields.Integer(readonly=True)
    duration_ms = fields.Integer(readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('computed', 'Computed'),
        ('failed', 'Failed'),
        ('decided', 'Decided'),
        ('archived', 'Archived'),
    ], default='draft', required=True, index=True, tracking=True)
    failure_reason = fields.Text(readonly=True)
    notes = fields.Text()
    compare_run_id = fields.Many2one('aic.hrm.match.run')

    _sql_constraints = [
        ('reference_uniq', 'unique(reference)', 'That ranking reference already exists.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference') or vals['reference'] == _('New'):
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    RUN_SEQUENCE) or _('New')
        return super().create(vals_list)

    def write(self, vals):
        computed = self.filtered(lambda r: r.state != 'draft')
        if computed and set(vals) - _MUTABLE_AFTER_COMPUTE:
            raise UserError(_(
                "%(names)s has already produced a ranking. A record of what "
                "happened that can be edited afterwards is not a record. "
                "Re-rank instead - it creates a new run and leaves this one "
                "readable.", names=', '.join(computed.mapped('reference'))))
        return super().write(vals)


class AicHrmMatchCandidate(models.Model):
    """One person's outcome in one ranking, whether or not they made the list."""
    _name = 'aic.hrm.match.candidate'
    _description = 'Staffing Candidate'
    _order = 'run_id, rank, id'
    _rec_name = 'display_ref'

    run_id = fields.Many2one(
        'aic.hrm.match.run', required=True, index=True, ondelete='cascade')
    slot_id = fields.Many2one('aic.hrm.match.request.slot', index=True)
    company_id = fields.Many2one(
        'res.company', related='run_id.company_id', store=True, index=True)

    identity_ref = fields.Char(
        required=True, readonly=True, index=True,
        help="Opaque handle for this candidate. Always present, so a blind "
             "ranking has something to show that is not a name.")
    # Not required, and behind a field group. When the policy ranks blind the
    # engine leaves this empty and the mapping lives in aic.hrm.match.identity,
    # which only an administrator can read. A row hidden in one view is not
    # anonymous - RPC, export and pivot all still see it.
    employee_id = fields.Many2one(
        'hr.employee', index=True, ondelete='set null')
    display_ref = fields.Char(compute='_compute_display_ref')

    raw_score = fields.Float(
        readonly=True,
        help="The weighted score before any fairness adjustment. Kept "
             "separate so an adjustment is visible as a decision rather than "
             "folded invisibly into the merit.")
    fairness_adjustment = fields.Float(readonly=True)
    total_score = fields.Float(readonly=True, index=True, aggregator='avg')
    rank = fields.Integer(
        readonly=True, index=True,
        help="Position among the shortlisted. Excluded candidates have none: "
             "a number there would read as a placing.")

    eligible = fields.Boolean(readonly=True, index=True)
    rejection_code = fields.Selection(
        selection='_selection_rejection_code', readonly=True, index=True)
    rejection_detail = fields.Text(readonly=True)
    low_confidence = fields.Boolean(
        readonly=True,
        help="Too little of the policy's weight could be scored for this "
             "person. Somebody judged on two criteria out of twelve must not "
             "quietly come first.")

    is_stretch = fields.Boolean(
        readonly=True, index=True,
        help="Offered despite falling short of a requirement the seat marked "
             "as open to it. Flagged rather than hidden: a development posting "
             "nobody can find afterwards is indistinguishable from a mistake, "
             "and the person deserves the credit either way.")

    # capacity - leave - booked = free, so a reader can check the row
    # rather than take the free hours on trust.
    capacity_hours = fields.Float(readonly=True)
    leave_hours = fields.Float(readonly=True)
    booked_hours = fields.Float(readonly=True)
    free_hours = fields.Float(readonly=True)
    score_line_ids = fields.One2many(
        'aic.hrm.match.score.line', 'candidate_id', string='Breakdown')

    _sql_constraints = [
        ('run_employee_uniq', 'unique(run_id, employee_id)', 'That person already has a result in this ranking.'),
    ]

    @api.model
    def _selection_rejection_code(self):
        """Structured reasons, extensible by connectors.

        Grouping the excluded by free text fragments every numeric explanation
        into its own bucket, so the screen that should read "118 people had no
        capacity" reads as 118 separate sentences.
        """
        return [
            ('no_capacity', 'No capacity in the window'),
            ('missing_mandatory_skill', 'Missing a required skill'),
            ('certification_expired', 'Certificate does not cover the work'),
            ('opted_out', 'Opted out of staffing'),
            ('not_staffable', 'Not available for project staffing'),
            ('available_later', 'Not available until later'),
            ('too_expensive', 'Above the cost ceiling'),
            ('cross_company_blocked', 'In another company'),
            ('criterion_threshold', 'Below a required threshold'),
        ]

    @api.depends('employee_id', 'identity_ref')
    def _compute_display_ref(self):
        for candidate in self:
            candidate.display_ref = (candidate.employee_id.display_name
                                     or candidate.identity_ref)


class AicHrmMatchScoreLine(models.Model):
    """What one criterion contributed, and why."""
    _name = 'aic.hrm.match.score.line'
    _description = 'Staffing Score Line'
    _order = 'candidate_id, sequence, id'
    _rec_name = 'criterion_code'

    candidate_id = fields.Many2one(
        'aic.hrm.match.candidate', required=True, index=True,
        ondelete='cascade')
    run_id = fields.Many2one(
        'aic.hrm.match.run', related='candidate_id.run_id', store=True,
        index=True)
    sequence = fields.Integer(default=10)

    # Nullable with a snapshot beside it: restrict would block uninstalling a
    # connector, cascade would erase the record of what a past ranking used.
    criterion_id = fields.Many2one(
        'aic.hrm.match.criterion', ondelete='set null', index=True)
    criterion_code = fields.Char(readonly=True, index=True)
    criterion_name = fields.Char(readonly=True)
    criterion_provider = fields.Char(readonly=True)
    criterion_sensitive = fields.Boolean(
        readonly=True, index=True,
        help="Snapshotted rather than related, so removing the criterion "
             "cannot unlock rows that were restricted when they were written.")

    raw_value = fields.Float(readonly=True)
    raw_unit = fields.Char(readonly=True)
    normalized_score = fields.Float(readonly=True)
    weight = fields.Float(readonly=True)
    weighted_score = fields.Float(readonly=True)

    is_missing = fields.Boolean(
        readonly=True,
        help="No data for this person. The criterion is then left out of both "
             "sides of the average rather than scored as zero, which would "
             "turn a gap in the record into a permanent disadvantage.")
    is_knockout = fields.Boolean(
        readonly=True, help="This line is why the candidate was excluded.")
    passed = fields.Boolean(readonly=True)

    evidence_ids = fields.One2many(
        'aic.hrm.match.evidence', 'score_line_id', string='Evidence')

    _sql_constraints = [
        ('candidate_criterion_uniq', 'unique(candidate_id, criterion_code)', 'That criterion is already scored for this candidate.'),
    ]


class AicHrmMatchEvidence(models.Model):
    """A fact behind a score, pointing at the record it came from.

    A child model rather than one model/id pair on the score line, because the
    real answers are plural: "four overlapping bookings", "three similar
    projects". A single reference forces the screen to say "and others".
    """
    _name = 'aic.hrm.match.evidence'
    _description = 'Staffing Score Evidence'
    _order = 'score_line_id, sequence, id'
    _rec_name = 'label'

    score_line_id = fields.Many2one(
        'aic.hrm.match.score.line', required=True, index=True,
        ondelete='cascade')
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True)
    value = fields.Char()
    res_model = fields.Char()
    res_id = fields.Many2oneReference(model_field='res_model')


class AicHrmMatchIdentity(models.Model):
    """Who a blind candidate actually is.

    Separate because anonymity has to survive more than a hidden column. RPC,
    export, pivot and developer mode all read the same row, so the name is not
    on it at all - it is here, behind its own access list, and revealed by a
    server-side action when a decision is made.
    """
    _name = 'aic.hrm.match.identity'
    _description = 'Staffing Candidate Identity'
    _order = 'run_id, id'
    _rec_name = 'employee_id'

    run_id = fields.Many2one(
        'aic.hrm.match.run', required=True, index=True, ondelete='cascade')
    candidate_id = fields.Many2one(
        'aic.hrm.match.candidate', required=True, index=True,
        ondelete='cascade')
    employee_id = fields.Many2one(
        'hr.employee', required=True, index=True, ondelete='restrict')
    company_id = fields.Many2one(
        'res.company', related='run_id.company_id', store=True, index=True)
    revealed_date = fields.Datetime(readonly=True)

    _sql_constraints = [
        ('run_candidate_uniq', 'unique(run_id, candidate_id)', 'That candidate already has an identity in this ranking.'),
        ('run_employee_uniq', 'unique(run_id, employee_id)', 'That person already appears once in this ranking.'),
    ]
