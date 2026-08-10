# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Which criteria count, and how much.

Changing how people are ranked is a decision, not an edit. An active policy is
frozen; altering it means forking a new version, and the superseded one stays
readable so a ranking from last quarter can still be explained. An archived
version is frozen for the same reason - history that can be rewritten is not
history.

Activation is where the checking happens, because everything it refuses would
otherwise become a ranking run under rules that never executed.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import sql

# Everything that changes what a ranking produces. Editable in draft, frozen
# once activated: the rest (name, notes) may be corrected at any time.
_FROZEN_FIELDS = {
    'code', 'version', 'aggregation', 'top_n', 'rejected_limit',
    'persist_mode', 'fairness_mode', 'fairness_strength',
    'anonymize_until_decision', 'show_own_candidacy', 'partial_tolerance',
    'unverified_factor', 'min_effective_weight_pct', 'allow_cross_company',
    'rounding_digits', 'engine_model', 'engine_fallback_allowed',
    'tiebreak_version', 'applies_domain', 'is_default', 'company_id',
}
_FROZEN_STATES = ('active', 'archived')

# Advisory-lock namespace for activation, distinct from the allocation one so
# the two can never be mistaken for each other on the same integer.
_POLICY_LOCK_NAMESPACE = 0x41494332


class AicHrmMatchPolicy(models.Model):
    _name = 'aic.hrm.match.policy'
    _description = 'Staffing Scoring Policy'
    _order = 'code, version desc, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Names the policy across all of its versions.")
    version = fields.Integer(default=1, required=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='draft', required=True, readonly=True, index=True)

    sequence = fields.Integer(default=10)
    is_default = fields.Boolean(
        help="Used when no other policy claims a request.")
    applies_domain = fields.Char(
        default='[]',
        help="Domain on the staffing request. Lets one company run different "
             "weights for client-critical work and for internal projects.")
    company_id = fields.Many2one('res.company', index=True)

    line_ids = fields.One2many(
        'aic.hrm.match.policy.line', 'policy_id', string='Weights',
        # One2many is copy=False by default in Odoo, unlike many2many. Without
        # this a forked version arrives with no weights at all - and an empty
        # policy is refused at activation, so the mistake surfaces as a
        # confusing "no enabled criteria" rather than as lost data.
        copy=True)

    aggregation = fields.Selection([
        ('weighted_sum', 'Weighted average'),
        ('weighted_geomean', 'Weighted geometric mean'),
        ('lexicographic', 'Strict priority order'),
    ], default='weighted_sum', required=True,
        help="Geometric mean punishes any criterion near zero, which suits a "
             "role where being weak anywhere disqualifies.")
    top_n = fields.Integer(
        default=20,
        help="How many candidates keep a full score breakdown. Everyone "
             "evaluated still keeps a record and, if excluded, their reason.")
    rejected_limit = fields.Integer(default=500)
    persist_mode = fields.Selection([
        ('full', 'Every score line for everybody'),
        ('ranked_only', 'Full lines for the shortlist'),
    ], default='ranked_only', required=True,
        help="Controls how much presentation detail is stored. It never drops "
             "a candidate or an exclusion reason.")

    fairness_mode = fields.Selection([
        ('off', 'Measure only'),
        ('load_balance', 'Favour the less loaded'),
        ('rotation', 'Rotate between rounds'),
        ('development', 'Favour development opportunities'),
    ], default='off', required=True,
        help="Off by default. Fairness is always measured; adjusting the score "
             "for it is a policy choice a customer makes, not one a vendor "
             "makes for them.")
    fairness_strength = fields.Float(default=0.5)

    anonymize_until_decision = fields.Boolean(
        help="Rank without showing names. The audit record always keeps the "
             "real identity; only the shortlist is blind.")
    show_own_candidacy = fields.Boolean(
        help="Let people see their own standing in a ranking. Never anybody "
             "else's.")

    partial_tolerance = fields.Float(default=0.0)
    unverified_factor = fields.Float(
        default=0.9,
        help="How much an unverified skill claim is discounted.")
    min_effective_weight_pct = fields.Float(
        default=50.0,
        help="Below this share of usable weight a candidate is flagged as "
             "low confidence. Somebody scored on two criteria out of twelve "
             "must not quietly come first.")
    explain_required = fields.Boolean(default=True)
    allow_cross_company = fields.Boolean()
    rounding_digits = fields.Integer(default=3)

    engine_model = fields.Char(
        help="Replaces the built-in ranking engine. A replacement still has "
             "to write runs, candidates and score lines: the contract is "
             "'produce an explainable ranking', not 'do as you like'.")
    engine_fallback_allowed = fields.Boolean(
        help="Whether a broken engine may silently fall back to the built-in "
             "one. Off by default: a staffing decision made by different code "
             "than the policy names is not the decision that was authorised.")
    tiebreak_version = fields.Integer(default=1)

    has_sensitive_criterion = fields.Boolean(
        compute='_compute_has_sensitive_criterion', store=True,
        help="Whether any enabled criterion is restricted. Stored because the "
             "record rules that hide performance figures filter on it, and a "
             "rule cannot evaluate a non-stored field.")

    active = fields.Boolean(default=True)

    def init(self):
        super().init()
        sql.create_unique_index(
            self.env.cr, 'aic_hrm_match_policy_code_version_uniq',
            self._table, ['code', 'version', 'COALESCE(company_id, 0)'])
        # Partial indexes, so "one active version" and "one default" hold in
        # the database rather than only in the method that sets them.
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS aic_hrm_match_policy_one_active
            ON aic_hrm_match_policy (code, COALESCE(company_id, 0))
            WHERE state = 'active'
        """)
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS aic_hrm_match_policy_one_default
            ON aic_hrm_match_policy (COALESCE(company_id, 0))
            WHERE is_default AND state = 'active'
        """)

    @api.depends('line_ids.enabled', 'line_ids.criterion_id.is_sensitive')
    def _compute_has_sensitive_criterion(self):
        for policy in self:
            policy.has_sensitive_criterion = any(
                line.enabled and line.criterion_id.is_sensitive
                for line in policy.line_ids)

    # -- freezing ------------------------------------------------------------

    def write(self, vals):
        frozen = self.filtered(lambda p: p.state in _FROZEN_STATES)
        if frozen and _FROZEN_FIELDS & set(vals):
            raise UserError(_(
                "%(names)s cannot be changed: a ranking has to stay "
                "explainable, and if the weights behind it can be edited "
                "afterwards the explanation is fiction. Create a new version "
                "instead.", names=', '.join(frozen.mapped('display_name'))))
        return super().write(vals)

    def _assert_editable(self):
        """Refuse a change to a published policy, from anywhere.

        Called by the weight lines too. Freezing the policy record while
        leaving its weights editable would protect the wrapper and not the
        thing that actually decides the ranking.
        """
        frozen = self.filtered(lambda p: p.state in _FROZEN_STATES)
        if frozen:
            raise UserError(_(
                "%(names)s is published, so its weights are fixed. Create a "
                "new version to change how candidates are ranked.",
                names=', '.join(frozen.mapped('display_name'))))

    def action_new_version(self):
        """Fork the next revision, copying the weights, leaving this one alone."""
        self.ensure_one()
        successor = self.copy({
            'name': self.name,
            'code': self.code,
            'version': self._next_version(),
            'state': 'draft',
            'is_default': False,
        })
        return successor

    def _next_version(self):
        highest = self.search([
            ('code', '=', self.code),
            ('company_id', '=', self.company_id.id),
        ], order='version desc', limit=1)
        return (highest.version or 0) + 1

    def action_activate(self):
        """Publish this version, retiring whichever one it replaces.

        Everything refused here would otherwise become a ranking run under
        rules that never executed, which is the worst failure this product can
        have: a decision about people, made by a system, under a rule nobody
        applied.
        """
        for policy in self:
            policy._assert_activatable()
            self.env.cr.execute(
                'SELECT pg_advisory_xact_lock(%s, %s)',
                (_POLICY_LOCK_NAMESPACE, hash(policy.code) % 2147483647))
            superseded = self.search([
                ('id', '!=', policy.id),
                ('code', '=', policy.code),
                ('company_id', '=', policy.company_id.id),
                ('state', '=', 'active'),
            ])
            superseded.with_context(policy_supersede=True).write(
                {'state': 'archived'})
            # Flush the retirement before publishing the successor. Both writes
            # would otherwise land in one flush, and the partial unique index
            # that enforces "one active version" sees the intermediate state
            # where two are active at once.
            superseded.flush_recordset(['state'])
            super(AicHrmMatchPolicy, policy).write({'state': 'active'})
        return True

    def _assert_activatable(self):
        self.ensure_one()
        enabled = self.line_ids.filtered('enabled')
        if not enabled:
            raise UserError(_(
                "%(name)s has no enabled criteria, so it would rank everybody "
                "identically.", name=self.display_name))

        unimplemented = enabled.filtered(
            lambda line: line.criterion_id and not line.criterion_id.implemented)
        if unimplemented:
            raise UserError(_(
                "No scorer is installed for: %(codes)s. Activating anyway "
                "would produce staffing decisions under a rule that never "
                "ran, with nothing on screen to say so. Disable the line or "
                "install the module that provides it.",
                codes=', '.join(unimplemented.mapped('criterion_code'))))

        if sum(enabled.mapped('weight')) <= 0.0:
            raise UserError(_(
                "%(name)s gives no criterion any weight, so every candidate "
                "would score the same.", name=self.display_name))

        if self.fairness_mode == 'load_balance' and any(
                line.criterion_code == 'workload_balance' for line in enabled):
            raise UserError(_(
                "Load balancing and the workload criterion measure the same "
                "thing, so running both counts one signal twice. Keep the "
                "criterion, or the fairness mode, not both."))


class AicHrmMatchPolicyLine(models.Model):
    """One criterion's weight inside a policy."""
    _name = 'aic.hrm.match.policy.line'
    _description = 'Staffing Policy Weight'
    _order = 'policy_id, sequence, id'
    _rec_name = 'criterion_code'

    policy_id = fields.Many2one(
        'aic.hrm.match.policy', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(default=10)

    # Nullable with set null, plus a snapshot. restrict would block
    # uninstalling a connector; cascade would erase the record of what a past
    # ranking was configured with.
    criterion_id = fields.Many2one(
        'aic.hrm.match.criterion', ondelete='set null', index=True)
    criterion_code = fields.Char(readonly=True)
    criterion_name = fields.Char(readonly=True)
    criterion_provider = fields.Char(readonly=True)

    weight = fields.Float(default=1.0)
    mode_override = fields.Selection([
        ('soft', 'Ranks only'),
        ('hard', 'Eliminates'),
        ('both', 'Eliminates and ranks'),
    ])
    threshold_override = fields.Float()
    missing_policy_override = fields.Selection([
        ('neutral', 'Ignore the criterion for that person'),
        ('zero', 'Treat as the worst possible'),
        ('one', 'Treat as the best possible'),
        ('exclude_candidate', 'Remove the candidate'),
    ])
    min_score = fields.Float()
    enabled = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            policy = self.env['aic.hrm.match.policy'].browse(
                vals.get('policy_id'))
            policy._assert_editable()
            criterion = self.env['aic.hrm.match.criterion'].browse(
                vals.get('criterion_id'))
            if criterion:
                vals.setdefault('criterion_code', criterion.code)
                vals.setdefault('criterion_name', criterion.name)
                vals.setdefault('criterion_provider', criterion.provider_module)
        return super().create(vals_list)

    def write(self, vals):
        self.mapped('policy_id')._assert_editable()
        return super().write(vals)

    def unlink(self):
        self.mapped('policy_id')._assert_editable()
        return super().unlink()
