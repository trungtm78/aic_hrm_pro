# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The catalogue of things a person can be judged on.

A criterion is data. A consultancy that cares more about customer history than
about technology depth changes a weight, not a line of Python, and a third
party adds a criterion of its own by shipping one record plus one method.

The ``code`` is the whole binding: the scorer registry discovers
``_score_<code>``, so a criterion whose code has no method is visibly
unimplemented rather than quietly contributing nothing to every ranking.
"""
import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import sql


class AicHrmMatchCriterion(models.Model):
    _name = 'aic.hrm.match.criterion'
    _description = 'Staffing Criterion'
    _order = 'category, sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Binds this criterion to the method that scores it. The registry "
             "looks for _score_<code>, so renaming a code silently detaches "
             "the criterion from its implementation.")
    description = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('availability', 'Availability'),
        ('skill', 'Skills'),
        ('experience', 'Experience'),
        ('relationship', 'Customer relationship'),
        ('cost', 'Cost'),
        ('logistics', 'Location and time zone'),
        ('performance', 'Past performance'),
        ('development', 'Development'),
        ('fairness', 'Fairness'),
        ('custom', 'Custom'),
    ], required=True, default='custom')

    mode = fields.Selection([
        ('soft', 'Ranks only'),
        ('hard', 'Eliminates'),
        ('both', 'Eliminates and ranks'),
    ], default='soft', required=True,
        help="Eliminating criteria remove a candidate with a stated reason; "
             "ranking criteria only move the score. Somebody with no free "
             "hours is not a low score, they are unavailable.")
    direction = fields.Selection([
        ('higher', 'Higher is better'),
        ('lower', 'Lower is better'),
    ], default='higher', required=True)
    weight = fields.Float(default=1.0)

    normalization = fields.Selection([
        ('none', 'Already 0 to 1'),
        ('ratio', 'Proportion of a target'),
        ('log', 'Diminishing returns'),
        ('minmax', 'Spread across the pool'),
        ('zscore', 'Standard score'),
        ('rank', 'Percentile'),
    ], default='none', required=True,
        help="Pool-independent kinds are preferred: a score that means the "
             "same thing across two runs is what makes them comparable.")
    saturation_value = fields.Float(
        help="The raw value that counts as a full score, for proportion and "
             "diminishing-returns normalisation.")

    missing_policy = fields.Selection([
        ('neutral', 'Ignore the criterion for that person'),
        ('zero', 'Treat as the worst possible'),
        ('one', 'Treat as the best possible'),
        ('exclude_candidate', 'Remove the candidate'),
    ], default='neutral', required=True,
        help="What to do when there is no data. Ignoring is the default "
             "because scoring an unknown as zero turns a gap in the HR record "
             "into a permanent disadvantage for the person it is missing for.")

    threshold = fields.Float(
        help="Normalised score below which an eliminating criterion removes "
             "the candidate.")
    is_tiebreak = fields.Boolean()
    tiebreak_sequence = fields.Integer(default=10)

    applies_domain = fields.Char(
        default='[]',
        help="Domain on the staffing request. Lets a criterion switch itself "
             "on only where it is relevant - a security clearance matters on "
             "defence work and nowhere else.")
    param_json = fields.Text(
        default='{}',
        help="Scorer parameters as a JSON object: half-life, similarity mode, "
             "and anything a third-party criterion needs. Kept open so adding "
             "a knob does not mean adding a column.")
    evidence_template = fields.Char(
        translate=True,
        help="How this criterion explains itself on a candidate's breakdown.")

    is_sensitive = fields.Boolean(
        help="Whether the contribution of this criterion is restricted. "
             "Appraisal-derived scores are: a planner may rank a shortlist "
             "without being shown anybody's performance figures.")
    unit = fields.Char()
    enabled = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', index=True,
        help="Leave empty to share across companies.")

    provider_module = fields.Char(
        default='aic_hrm_match',
        help="Which module supplies the scorer. Recorded on every run so an "
             "audit can answer whose code produced a decision.")
    provider_version = fields.Char()

    implemented = fields.Boolean(
        compute='_compute_implemented',
        help="Whether a scorer exists for this code in the running database.")

    def init(self):
        super().init()
        # COALESCE for the same reason as everywhere else: Postgres treats
        # every NULL as distinct, so a plain unique(code, company_id) would let
        # two shared criteria carry one code while looking like it worked.
        sql.create_unique_index(
            self.env.cr, 'aic_hrm_match_criterion_code_scope_uniq',
            self._table, ['code', 'COALESCE(company_id, 0)'])

    @api.depends('code')
    def _compute_implemented(self):
        registry = self.env['aic.hrm.match.scorer'].get_scorer_codes()
        for criterion in self:
            criterion.implemented = criterion.code in registry

    @api.constrains('weight')
    def _check_weight(self):
        for criterion in self:
            if criterion.weight < 0.0:
                raise ValidationError(_(
                    "%(name)s: a weight cannot be negative. A negative weight "
                    "inverts what the criterion means rather than reducing "
                    "its influence.", name=criterion.display_name))

    @api.constrains('param_json')
    def _check_param_json(self):
        for criterion in self:
            try:
                params = json.loads(criterion.param_json or '{}')
            except ValueError as error:
                raise ValidationError(_(
                    "%(name)s: the parameters are not valid JSON (%(error)s). "
                    "Caught here rather than inside the scoring loop, where it "
                    "would surface on one candidate and look like a data "
                    "problem.", name=criterion.display_name,
                    error=error)) from error
            if not isinstance(params, dict):
                raise ValidationError(_(
                    "%(name)s: the parameters must be a JSON object.",
                    name=criterion.display_name))

    def get_params(self):
        """Scorer parameters as a plain dict.

        Parsed once per run by the context builder, never inside the scoring
        loop: two thousand candidates times twelve criteria is twenty-four
        thousand parses of the same short string.
        """
        self.ensure_one()
        return json.loads(self.param_json or '{}')
