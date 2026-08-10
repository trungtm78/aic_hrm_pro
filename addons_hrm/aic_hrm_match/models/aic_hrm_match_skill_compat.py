# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""The single place that knows how this Odoo stores skill validity.

The two supported series disagree about something the staffing engine depends
on completely:

* **Odoo 19** models certification periods natively. ``hr.individual.skill.mixin``
  carries ``valid_from`` / ``valid_to``, ``hr.skill.type`` carries
  ``is_certification``, and the overlap rule deliberately lets one skill hold
  several periods so a renewed certificate sits beside the one it replaced.
* **Odoo 18** has none of that, and enforces ``unique(employee_id, skill_id)``.
  A second validity period is not merely unsupported there, it is forbidden by
  the table.

So the module owns shim columns and this service decides which side to read.
Two rules keep that from turning into a mess:

1. **Nothing outside this file touches either source directly.** The engine asks
   ``covers_window``; it never learns which column answered. A single caller
   reaching past this service is how the 18 build silently starts reading an
   empty Odoo 19 column.
2. **Capability is detected from the fields, never from a version number.** A
   patch release can move a field and a customer may run a fork; asking the
   model what it has is true in every case that asking the version is, plus the
   ones it is not.
"""
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrSkillTypeMatch(models.Model):
    _inherit = 'hr.skill.type'

    match_is_certification = fields.Boolean(
        string='Certification (staffing)',
        help="Whether skills of this type expire and therefore have to cover "
             "the whole of a booking. Used only where the Odoo release does "
             "not model certifications itself; see the staffing compatibility "
             "service.")


class HrEmployeeSkillMatch(models.Model):
    _inherit = 'hr.employee.skill'

    match_valid_from = fields.Date(
        string='Valid From (staffing)',
        help="Start of the period this skill or certificate is valid for. "
             "Used only where the Odoo release does not model validity itself.")
    match_valid_to = fields.Date(
        string='Valid To (staffing)',
        help="End of the validity period; empty means open-ended.")

    # -- verification --------------------------------------------------------
    #
    # Core hr_skills records what somebody claims; it has no notion of anybody
    # checking. The whole value of a verified certificate is that a second
    # person confirmed it, so the workflow lives here.

    verify_state = fields.Selection([
        ('draft', 'Not submitted'),
        ('submitted', 'Awaiting verification'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ], default='draft', required=True, index=True, string='Verification')
    verified_by_id = fields.Many2one(
        'res.users', readonly=True, ondelete='set null',
        help="Set by the system when somebody verifies. Never accepted from "
             "the caller: taking it from vals would let anybody claim a "
             "colleague signed off on their certificate.")
    verified_date = fields.Datetime(readonly=True)


_ALLOWED_VERIFY_TRANSITIONS = {
    'draft': {'submitted'},
    'submitted': {'verified', 'rejected', 'draft'},
    'rejected': {'submitted', 'draft'},
    # A verified record goes back to draft rather than straight to rejected:
    # withdrawing a confirmation is a separate act from refusing a claim.
    'verified': {'draft'},
}
_VERIFIER_TRANSITIONS = {'verified', 'rejected'}


class HrEmployeeSkillVerification(models.Model):
    """The verification workflow, enforced in write() rather than by a rule.

    A record rule evaluates the row as it already is, so it can say who may
    touch an unverified claim but not reliably refuse the transition *into*
    verified. That distinction is the whole control here.
    """
    _inherit = 'hr.employee.skill'

    def action_submit_for_verification(self):
        self.write({'verify_state': 'submitted'})

    def action_verify(self):
        self.write({'verify_state': 'verified'})

    def action_reject(self):
        self.write({'verify_state': 'rejected'})

    def write(self, vals):
        target = vals.get('verify_state')
        if target:
            vals = dict(vals)
            # Never from the caller. Accepting it would let anybody record that
            # a colleague signed off on their own certificate.
            vals.pop('verified_by_id', None)
            vals.pop('verified_date', None)
            self._assert_verification_allowed(target)
            if target == 'verified':
                vals['verified_by_id'] = self.env.user.id
                vals['verified_date'] = fields.Datetime.now()
            elif target in ('draft', 'submitted'):
                vals['verified_by_id'] = False
                vals['verified_date'] = False
        return super().write(vals)

    def _assert_verification_allowed(self, target):
        if self.env.su:
            return
        if target in _VERIFIER_TRANSITIONS and not self.env.user.has_group(
                'aic_hrm_match.group_match_planner'):
            raise UserError(_(
                "Only a staffing planner may verify or reject a certificate. "
                "A certificate confirmed by the person who claimed it "
                "attests to nothing."))
        for line in self:
            allowed = _ALLOWED_VERIFY_TRANSITIONS.get(line.verify_state, set())
            if target != line.verify_state and target not in allowed:
                raise UserError(_(
                    "%(skill)s cannot go from %(current)s to %(target)s.",
                    skill=line.display_name, current=line.verify_state,
                    target=target))


class AicHrmMatchSkillCompat(models.AbstractModel):
    """Read and write skill validity without caring which series is running."""
    _name = 'aic.hrm.match.skill.compat'
    _description = 'Staffing Skill Compatibility Service'

    # -- capability detection ------------------------------------------------

    @api.model
    def has_core_validity(self):
        """True when the running Odoo dates skills itself."""
        return 'valid_to' in self.env['hr.employee.skill']._fields

    @api.model
    def has_core_certification(self):
        """True when the running Odoo flags certification skill types itself.

        Asked separately from validity even though both landed in 19 together:
        they are different questions, and a fork could ship one without the
        other.
        """
        return 'is_certification' in self.env['hr.skill.type']._fields

    @api.model
    def _validity_fields(self):
        if self.has_core_validity():
            return 'valid_from', 'valid_to'
        return 'match_valid_from', 'match_valid_to'

    @api.model
    def _certification_field(self):
        if self.has_core_certification():
            return 'is_certification'
        return 'match_is_certification'

    # -- validity ------------------------------------------------------------

    @api.model
    def get_validity(self, skill_lines):
        """``{line_id: (valid_from, valid_to)}`` for a whole recordset.

        Batched because the engine asks once for every line it is about to
        score. Asking per line is exactly the per-record loop the performance
        budget rules out.
        """
        if not skill_lines:
            return {}
        from_field, to_field = self._validity_fields()
        return {
            line.id: (line[from_field] or False, line[to_field] or False)
            for line in skill_lines
        }

    @api.model
    def set_validity(self, skill_lines, valid_from=None, valid_to=None):
        """Record a validity period on whichever columns this series has."""
        if not skill_lines:
            return
        from_field, to_field = self._validity_fields()
        skill_lines.write({from_field: valid_from or False,
                           to_field: valid_to or False})

    @api.model
    def covers_window(self, skill_line, date_start, date_end):
        """Whether the recorded validity period spans the whole window.

        Comparing only the end date is the mistake this replaces: it lets a
        certificate that starts halfway through a project count for the whole
        of it. Boundaries are inclusive - a certificate valid to the last day
        of the work is valid for that work. A missing end means open-ended.

        This is the raw date question. For gating a booking use
        ``certification_covers_window``, which knows that an ordinary skill
        does not expire at all.
        """
        skill_line.ensure_one()
        valid_from, valid_to = self.get_validity(skill_line)[skill_line.id]
        if valid_from and date_start and str(valid_from) > str(date_start)[:10]:
            return False
        if valid_to and date_end and str(valid_to) < str(date_end)[:10]:
            return False
        return True

    @api.model
    def certification_covers_window(self, skill_line, date_start, date_end):
        """Whether this line may gate a booking over the given window.

        Only certifications expire, so only certifications are date-checked.
        Applying the window to ordinary skills would be actively wrong on Odoo
        19, where ``valid_from`` defaults to the day the line was created: a
        developer who has written Python for a decade, whose record HR entered
        this morning, would fail every project that started before today. The
        date on a plain skill records when it was captured, not when the person
        acquired it.
        """
        skill_line.ensure_one()
        if not self.is_certification(skill_line.skill_type_id):
            return True
        return self.covers_window(skill_line, date_start, date_end)

    # -- certification -------------------------------------------------------

    @api.model
    def is_certification(self, skill_types):
        """True when every given skill type expires."""
        if not skill_types:
            return False
        field = self._certification_field()
        return all(skill_type[field] for skill_type in skill_types)

    @api.model
    def set_certification(self, skill_types, value=True):
        if not skill_types:
            return
        skill_types.write({self._certification_field(): value})

    # -- series-specific access ----------------------------------------------

    # Models that exist on one series and not the other, which our groups still
    # need to touch. They cannot go in ir.model.access.csv: a row naming a model
    # that does not exist fails the install on the series that lacks it.
    _OPTIONAL_ACCESS = {
        # Odoo 18 keeps a Skills History row alongside every skill line and
        # writes one whenever a line changes, so touching a skill needs write
        # access here too. Odoo 19 dropped the model.
        'hr.employee.skill.log': {
            'group_match_user': (1, 1, 1, 1),
            'group_match_planner': (1, 1, 1, 1),
            'group_match_admin': (1, 1, 1, 1),
        },
    }

    @api.model
    def ensure_optional_access(self):
        """Grant access to models only some series have.

        Idempotent, and silent about models this series does not ship. Called
        from the install hook rather than declared as data because a CSV row
        naming a missing model aborts the install on the other series.
        """
        access = self.env['ir.model.access'].sudo()
        for model_name, grants in self._OPTIONAL_ACCESS.items():
            model = self.env['ir.model'].sudo().search(
                [('model', '=', model_name)], limit=1)
            if not model:
                continue
            for group_xmlid, perms in grants.items():
                group = self.env.ref('aic_hrm_match.%s' % group_xmlid,
                                     raise_if_not_found=False)
                if not group:
                    continue
                name = 'access_%s_match_%s' % (
                    model_name.replace('.', '_'), group_xmlid)
                existing = access.search([('name', '=', name)], limit=1)
                values = dict(
                    zip(('perm_read', 'perm_write', 'perm_create',
                         'perm_unlink'), (bool(p) for p in perms)))
                values.update(name=name, model_id=model.id, group_id=group.id)
                if existing:
                    existing.write(values)
                else:
                    access.create(values)

    @api.model
    def get_certification_type_ids(self):
        """Ids of every skill type whose skills expire.

        Returned as ids rather than records: the caller uses them to build a
        domain, and browsing them would be a query nobody needed.
        """
        field = self._certification_field()
        return self.env['hr.skill.type'].search([(field, '=', True)]).ids
