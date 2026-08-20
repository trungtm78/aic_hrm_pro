# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The vocabulary a staffing request is matched against.

Tags form a tree because capability is not flat: somebody who has delivered
React has delivered Frontend work, and a flat tag list makes the engine miss
that and rank an expert below a stranger who happened to type the same word.

Categories exist so the *dimensions* of similarity are data too. A consultancy
matches on industry and methodology; a software house matches on technology and
domain. Neither should have to edit Python to say so.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import sql


class AicHrmMatchTagCategory(models.Model):
    """A dimension of similarity: industry, technology, methodology."""
    _name = 'aic.hrm.match.tag.category'
    _description = 'Staffing Tag Category'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(
        required=True, index=True,
        help="Stable identifier used by imports and by scorer configuration. "
             "Changing it breaks references; add a new category instead.")
    sequence = fields.Integer(default=10)
    similarity_weight = fields.Float(
        default=1.0,
        help="How much this dimension counts when comparing a person's history "
             "against a request. Industry overlap usually matters less than "
             "technology overlap, and how much less is a business decision.")
    is_hierarchical = fields.Boolean(
        default=True,
        help="Whether tags in this category form a tree. Technologies nest "
             "(React under Frontend); industries usually do not.")
    tag_ids = fields.One2many('aic.hrm.match.tag', 'category_id', string='Tags')
    active = fields.Boolean(default=True)

    # NOTE(backport-18): Odoo 18 uses the legacy _sql_constraints list instead.
    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'A tag category with this code already exists.'),
    ]

    @api.constrains('similarity_weight')
    def _check_similarity_weight(self):
        for category in self:
            if category.similarity_weight < 0.0:
                raise ValidationError(_(
                    "Category %(name)s: the similarity weight cannot be "
                    "negative. A negative weight inverts the meaning of the "
                    "whole dimension - matching the customer's industry would "
                    "count against the candidate.",
                    name=category.display_name))


class AicHrmMatchTag(models.Model):
    """One capability, market or method, optionally nested under a broader one."""
    _name = 'aic.hrm.match.tag'
    _description = 'Staffing Tag'
    _order = 'category_id, complete_name, id'
    _parent_store = True
    _parent_name = 'parent_id'
    _rec_name = 'complete_name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    complete_name = fields.Char(
        compute='_compute_complete_name', store=True, recursive=True)
    category_id = fields.Many2one(
        'aic.hrm.match.tag.category', required=True, index=True,
        ondelete='restrict', string='Category')
    parent_id = fields.Many2one(
        'aic.hrm.match.tag', string='Parent Tag', index=True,
        ondelete='cascade')
    parent_path = fields.Char(index=True, unaccent=False)
    child_ids = fields.One2many('aic.hrm.match.tag', 'parent_id',
                                string='Child Tags')
    color = fields.Integer()
    company_id = fields.Many2one(
        'res.company', index=True,
        help="Leave empty to share the tag across every company. A company "
             "value makes it private to that company.")
    active = fields.Boolean(default=True)

    def init(self):
        """Uniqueness that also holds for the shared tags.

        A plain ``unique (code, category_id, company_id)`` does not do the job:
        Postgres treats every NULL as distinct, so any number of shared tags
        could carry the same code while the constraint appeared to be working.
        COALESCE collapses the shared case onto a single value. Expressed as an
        index rather than a table constraint because a table constraint cannot
        contain an expression, and written here rather than through
        ``models.Constraint`` so it behaves identically on both series.

        ``create_unique_index`` rather than ``create_index(..., unique=True)``:
        the keyword is Odoo 19 only, and on 18 the call raises TypeError during
        table setup - the module simply fails to install. This helper has the
        same signature in both series.
        """
        super().init()
        sql.create_unique_index(
            self.env.cr, 'aic_hrm_match_tag_code_scope_uniq',
            self._table, ["code", "category_id", "COALESCE(company_id, 0)"])

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for tag in self:
            if tag.parent_id:
                tag.complete_name = '%s / %s' % (tag.parent_id.complete_name,
                                                 tag.name)
            else:
                tag.complete_name = tag.name

    # No cycle check here on purpose. _parent_store rebuilds parent_path during
    # the write and raises "Recursion Detected." before any model constraint
    # gets a turn, so a check of our own could never fire - it would read as
    # protection while doing nothing.

    @api.constrains('parent_id', 'category_id')
    def _check_parent_category(self):
        for tag in self:
            if tag.parent_id and tag.parent_id.category_id != tag.category_id:
                raise ValidationError(_(
                    "%(child)s sits under %(parent)s, which belongs to a "
                    "different category. Nesting across dimensions makes the "
                    "distance between two tags meaningless.",
                    child=tag.display_name, parent=tag.parent_id.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        self._assert_codes_available([
            (vals.get('code'), vals.get('category_id'),
             vals.get('company_id') or False, None)
            for vals in vals_list
        ])
        return super().create(vals_list)

    def write(self, vals):
        if {'code', 'category_id', 'company_id'} & set(vals):
            self._assert_codes_available([
                (vals.get('code', tag.code),
                 vals.get('category_id', tag.category_id.id),
                 vals.get('company_id', tag.company_id.id) or False,
                 tag.id)
                for tag in self
            ])
        return super().write(vals)

    @api.model
    def _assert_codes_available(self, triples):
        """Readable message for the ordinary duplicate, raised before the INSERT.

        Not an ``@api.constrains``: Odoo runs those after the row reaches the
        database, so the unique index would always fire first and the user
        would meet a psycopg traceback instead of a sentence. The index below
        remains the guarantee that actually holds when two transactions insert
        the same code at once; this is the courtesy layer in front of it.

        The batch is also checked against itself, because a single create() of
        two identical codes never touches an existing row and would otherwise
        slip straight through to the index.
        """
        seen = set()
        for code, category_id, company_id, own_id in triples:
            if not code or not category_id:
                continue                       # required-field errors belong to the ORM
            key = (code, category_id, company_id)
            if key in seen:
                raise ValidationError(_(
                    "The tag code %(code)s appears twice in the same batch.",
                    code=code))
            seen.add(key)
            domain = [
                ('code', '=', code),
                ('category_id', '=', category_id),
                ('company_id', '=', company_id),
            ]
            if own_id:
                domain.append(('id', '!=', own_id))
            if self.with_context(active_test=False).search_count(domain):
                category = self.env['aic.hrm.match.tag.category'].browse(
                    category_id)
                raise ValidationError(_(
                    "The tag code %(code)s is already used in category "
                    "%(category)s for this company.",
                    code=code, category=category.display_name))

    def ancestor_distance(self, other):
        """Steps between two tags along the tree, or None if unrelated.

        Symmetric on purpose. A Frontend requirement is partly met by React
        experience, and a React requirement is partly met by somebody with
        general Frontend work: credit has to run in both directions or half the
        tree is decorative.
        """
        self.ensure_one()
        other.ensure_one()
        if self == other:
            return 0
        mine = (self.parent_path or '').split('/')[:-1]
        theirs = (other.parent_path or '').split('/')[:-1]
        if len(mine) > len(theirs) and mine[:len(theirs)] == theirs:
            return len(mine) - len(theirs)
        if len(theirs) > len(mine) and theirs[:len(mine)] == mine:
            return len(theirs) - len(mine)
        return None

    def expand_related(self):
        """``{tag_id: distance}`` for every tag related to this recordset.

        Built once per ranking run. The alternative - comparing ``parent_path``
        prefixes inside the scoring loop - is on the order of a million string
        comparisons for two thousand candidates, and it is the difference
        between a ranking that returns and one the planner gives up on.

        When several requested tags reach the same relative, the shortest
        distance wins: the closest relationship is the one that describes it.
        """
        if not self:
            return {}
        # Descendants in one query: a subtree is exactly the rows whose
        # parent_path starts with this tag's own path.
        prefix_clauses = [('parent_path', '=like', tag.parent_path + '%')
                          for tag in self if tag.parent_path]
        descendants = self.browse()
        if prefix_clauses:
            descendants = self.with_context(active_test=False).search(
                ['|'] * (len(prefix_clauses) - 1) + prefix_clauses)
        # Ancestors need no query at all: their ids are already spelled out in
        # parent_path, which is the reason _parent_store exists.
        ancestors = self.browse()
        for tag in self:
            ancestors |= tag._ancestors()

        related = {}
        for candidate in (self | ancestors | descendants):
            distances = [tag.ancestor_distance(candidate) for tag in self]
            reachable = [d for d in distances if d is not None]
            if reachable:
                related[candidate.id] = min(reachable)
        return related

    def _ancestors(self):
        """Every tag on the path from the root down to (not including) self."""
        self.ensure_one()
        ids = [int(part) for part in (self.parent_path or '').split('/')[:-1]]
        return self.browse([i for i in ids if i != self.id])
