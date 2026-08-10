# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Where criteria are implemented, and how a third party adds one.

Discovery is by naming convention: any ``_score_<code>`` method on this model -
including one contributed by another module through ``_inherit`` - registers
itself under the criterion code it is named after. A connector therefore adds a
criterion with two artefacts and no change to this module: one XML record for
the catalogue entry, one method here.

The matching ``_prefetch_<code>`` is what makes the performance budget
structural rather than a matter of discipline. Every query a criterion needs
happens in the prefetch phase, against the whole pool at once; the scoring
phase is then plain arithmetic over dictionaries and cannot issue a query even
by accident.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class AicHrmMatchScorer(models.AbstractModel):
    _name = 'aic.hrm.match.scorer'
    _description = 'Staffing Criterion Scorers'

    _SCORE_PREFIX = '_score_'
    _PREFETCH_PREFIX = '_prefetch_'

    @api.model
    def get_scorer_codes(self):
        """Every criterion code this database can actually score.

        Read from the class rather than a registry table, so installing a
        connector makes its criteria implemented immediately and uninstalling
        it makes them visibly unimplemented rather than silently inert.
        """
        return {
            attribute[len(self._SCORE_PREFIX):]
            for attribute in dir(type(self))
            if attribute.startswith(self._SCORE_PREFIX)
        }

    @api.model
    def prefetch(self, code, ctx):
        """Load everything the criterion needs, for the whole pool, once."""
        method = getattr(self, '%s%s' % (self._PREFETCH_PREFIX, code), None)
        if method is not None:
            method(ctx)

    # -- shipped criteria ----------------------------------------------------

    @api.model
    def _prefetch_availability(self, ctx):
        """Free hours for the whole pool, in one pass over the calendars."""
        availability = self.env['aic.hrm.match.availability']
        employees = self.env['hr.employee'].browse(ctx.scoped_ids)
        window_start, window_end = ctx.window
        ctx.data['availability'] = availability.get_free_hours_batch(
            employees, window_start, window_end)
        ctx.data['availability_capacity'] = {
            employee.id: availability.get_gross_hours(
                employee, window_start, window_end)
            for employee in employees
        }

    @api.model
    def _score_availability(self, ctx):
        """Free hours against the effort the seat needs.

        Returned raw. The engine normalises once, against the slot's required
        hours as the saturation point - dividing here as well is how a score
        ends up squared and nobody notices, because it is still monotonic.
        """
        free_hours = ctx.data.get('availability', {})
        capacity = ctx.data.get('availability_capacity', {})
        needed = ctx.slot.required_hours or (
            ctx.slot.fte_ratio * max(capacity.values(), default=0.0))
        scores = {}
        for employee_id in ctx.scoped_ids:
            free = free_hours.get(employee_id)
            if free is None:
                scores[employee_id] = None
                continue
            scores[employee_id] = free
            ctx.add_evidence(
                employee_id, 'availability',
                '%.1f free of %.1f hours needed' % (free, needed))
        return scores

    @api.model
    def score(self, code, ctx):
        """Return ``{employee_id: raw value or None}``.

        ``None`` means "no data", which the criterion's missing-data policy
        then interprets. It is deliberately not zero: scoring an unknown as the
        worst possible turns a gap in the HR record into a permanent
        disadvantage for the person it is missing for.
        """
        method = getattr(self, '%s%s' % (self._SCORE_PREFIX, code), None)
        if method is None:
            # Reached only if a policy was activated before a connector was
            # removed. Activation refuses unimplemented criteria, so this is
            # the "it disappeared underneath us" case: skip the criterion,
            # leave a trace, and let the run's confidence flag show it.
            _logger.warning(
                "No scorer registered for criterion %r; it contributed "
                "nothing to this ranking.", code)
            return {}
        return method(ctx)
