# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Everything one ranking run needs, gathered once and then read.

A plain Python object rather than a model, because it is the boundary that
makes the performance budget structural instead of a matter of discipline.
Prefetch fills ``data``; scoring reads it. A scorer that wants a number it did
not prefetch finds nothing there, which is a visible bug, rather than issuing a
query per candidate and turning a three-second ranking into a five-minute one
that still returns the right answer.

The request is copied into a frozen dict for the same reason: a scorer holding
a live recordset can write to it, and a scoring pass that mutates the thing it
is scoring is not reproducible.
"""


class MatchContext:
    """One ranking run's inputs."""

    __slots__ = ('env', 'request', 'slot', 'policy_lines', 'employee_ids',
                 'data', 'params', 'as_of', 'window', 'evidence', 'rejections',
                 'scoped_ids', 'allowed_company_ids')

    def __init__(self, env, request, slot, policy_lines, employee_ids, as_of,
                 allowed_company_ids=None):
        self.env = env
        self.slot = slot
        self.as_of = as_of
        self.window = (slot.date_start, slot.date_end)
        self.employee_ids = list(employee_ids)

        # The pool as the caller's own access rights allowed it. Every raw SQL
        # statement in the module is parameterised by this rather than by a
        # fresh query, because SQL does not go through record rules and a
        # scorer that builds its own pool would quietly cross a company line.
        self.scoped_ids = list(employee_ids)
        self.allowed_company_ids = list(allowed_company_ids or
                                        env.companies.ids)

        # Frozen copy: what the run was asked for cannot change while it runs.
        self.request = {
            'id': request.id,
            'reference': request.reference,
            'rotation_epoch': request.rotation_epoch,
            'partner_id': request.partner_id.id,
            'commercial_partner_id': request.partner_id.commercial_partner_id.id,
            'project_id': request.project_id.id,
            'company_id': request.request_company_id.id,
            'date_start': request.date_start,
            'date_end': request.date_end,
        }

        # Parsed once here, never in the scoring loop: two thousand candidates
        # times twelve criteria is twenty-four thousand parses of the same
        # short string.
        self.policy_lines = policy_lines
        self.params = {
            line.criterion_code: (line.criterion_id.get_params()
                                  if line.criterion_id else {})
            for line in policy_lines
        }

        self.data = {}
        self.evidence = {}
        self.rejections = {}

    # -- scorer-facing helpers ----------------------------------------------

    def param(self, code, key, default=None):
        """A scorer parameter, or the default. Never raises: a missing knob is
        a configuration that did not set it, not a broken run."""
        return self.params.get(code, {}).get(key, default)

    def add_evidence(self, employee_id, code, text, res_model=None,
                     res_id=None):
        """Record why a criterion scored what it did.

        Collected as the score is produced rather than reconstructed
        afterwards: an explanation assembled later is a second implementation
        of the same logic, and the two drift.
        """
        self.evidence.setdefault((employee_id, code), []).append({
            'label': text, 'res_model': res_model, 'res_id': res_id,
        })

    def reject(self, employee_id, code, reason_code, detail=''):
        """Eliminate a candidate, with the reason attached.

        Nobody is dropped silently: the run keeps a record for every person it
        looked at, and an exclusion carries the gate that produced it.
        """
        self.rejections.setdefault(employee_id, []).append({
            'criterion_code': code,
            'rejection_code': reason_code,
            'detail': detail,
        })

    @property
    def rejected_ids(self):
        return set(self.rejections)

    @property
    def eligible_ids(self):
        return [i for i in self.employee_ids if i not in self.rejections]
