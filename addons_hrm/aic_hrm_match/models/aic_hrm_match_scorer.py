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

from odoo import _, api, models

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

    _GATE_PREFIX = '_gate_'

    @api.model
    def prefetch(self, code, ctx):
        """Load everything the criterion needs, for the whole pool, once."""
        method = getattr(self, '%s%s' % (self._PREFETCH_PREFIX, code), None)
        if method is not None:
            method(ctx)

    @api.model
    def gate(self, code, ctx, line):
        """Let a criterion remove people on its own terms, before scoring.

        Some questions do not have a score. Having no free hours is a fact
        about a calendar; an expired licence is a fact about a date. Turning
        either into a number between zero and one and comparing it with a
        threshold would let a high score elsewhere buy its way past, which on
        regulated work is not a ranking flaw but an unlicensed person on site.

        A criterion that defines ``_gate_<code>`` therefore eliminates through
        that method instead of through the threshold on its aggregate score -
        the same naming convention as scoring, so a connector adds a gating
        criterion the way it adds any other.
        """
        method = getattr(self, '%s%s' % (self._GATE_PREFIX, code), None)
        if method is not None:
            method(ctx, line)
            return True
        return False

    @api.model
    def has_gate(self, code):
        return hasattr(self, '%s%s' % (self._GATE_PREFIX, code))

    # -- shipped criteria ----------------------------------------------------

    @api.model
    def _prefetch_availability(self, ctx):
        """Free hours for the whole pool, in one pass over the calendars."""
        availability = self.env['aic.hrm.match.availability']
        employees = self.env['hr.employee'].browse(ctx.scoped_ids)
        window_start, window_end = ctx.window
        breakdown = availability.get_breakdown_batch(
            employees, window_start, window_end)
        ctx.data['availability_breakdown'] = breakdown
        ctx.data['availability'] = {
            employee_id: row['free_hours']
            for employee_id, row in breakdown.items()
        }
        ctx.data['availability_capacity'] = {
            employee_id: row['capacity_hours']
            for employee_id, row in breakdown.items()
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
    def _gate_availability(self, ctx, line):
        """No free hours is not a low score, it is being unavailable.

        Honours the criterion's mode, unlike the gates below: how much time
        somebody has is this criterion's own measurement, so a policy that sets
        it to rank only is entitled to say that a busy person should merely
        sort lower. What the seat itself declares - a mandatory skill, a
        required licence - is not the criterion's to soften.
        """
        mode = line.mode_override or (
            line.criterion_id.mode if line.criterion_id else 'soft')
        if mode not in ('hard', 'both'):
            return
        free_hours = ctx.data.get('availability', {})
        needed = ctx.needed_hours
        if needed <= 0.0:
            return
        tolerance = line.policy_id.partial_tolerance
        if ctx.slot.allow_partial_availability:
            tolerance = max(tolerance, 1.0)
        floor = needed * (1.0 - tolerance)
        for employee_id in ctx.scoped_ids:
            free = free_hours.get(employee_id, 0.0)
            if free < floor:
                ctx.reject(
                    employee_id, 'availability', 'no_capacity',
                    _('%(free).1f h free of %(needed).1f h needed.',
                      free=free, needed=needed))

    # -- skills --------------------------------------------------------------

    @api.model
    def _prefetch_skill_match(self, ctx):
        """Everybody's level in the skills this seat named, in one read.

        Only the named skills: an employee with forty skill lines contributes
        the two the seat asked about, and the rest never leave the database.
        """
        lines = ctx.slot.skill_line_ids
        ctx.data['skill_requirements'] = [
            {
                'skill_id': line.skill_id.id,
                'skill_name': line.skill_id.display_name,
                'minimum': line.min_level_progress,
                'requirement': line.requirement,
                'weight': line.weight,
                'stretch_allowed': line.stretch_allowed,
            }
            for line in lines
        ]
        if not lines:
            ctx.data['skill_levels'] = {}
            return

        held = self.env['hr.employee.skill'].search([
            ('employee_id', 'in', ctx.scoped_ids),
            ('skill_id', 'in', lines.skill_id.ids),
        ])
        compat = self.env['aic.hrm.match.skill.compat']
        levels = {}
        for record in held:
            # A skill somebody holds is theirs whether or not a validity window
            # was ever filled in; only certifications are date-checked, and
            # they are checked by their own gate. Date-checking every line here
            # would exclude a ten-year developer whose record was entered this
            # morning, because Odoo 19 defaults the start date to today.
            key = (record.employee_id.id, record.skill_id.id)
            progress = record.skill_level_id.level_progress
            factor = 1.0 if record.verify_state == 'verified' else \
                (ctx.policy_lines[:1].policy_id.unverified_factor or 1.0)
            levels[key] = max(levels.get(key, 0.0), progress * factor)
        ctx.data['skill_levels'] = levels
        ctx.data['skill_compat'] = compat

    @api.model
    def _score_skill_match(self, ctx):
        """How much of what the seat asked for each person covers.

        A shortfall costs score in proportion rather than removing anybody: the
        difference between "one level down" and "cannot do this" is the
        difference between a shortlist somebody can staff from and one that
        only ever offers the exact match, which in practice means offering the
        same three people forever.
        """
        requirements = ctx.data.get('skill_requirements', [])
        if not requirements:
            # The seat named no skills, so this criterion has no question to
            # answer. Missing, not zero: scoring everybody zero would flatten
            # the ranking while still consuming the weight.
            return {employee_id: None for employee_id in ctx.scoped_ids}

        levels = ctx.data.get('skill_levels', {})
        # Expressed as a share of what the seat asked for rather than as a
        # number of points. Level scales are the customer's to define - three
        # bands or seven, nought to five or nought to a hundred - and a fixed
        # twenty-five point tolerance means "one band down still counts" on one
        # scale and "everybody scores zero" on another.
        tolerance_share = ctx.param(
            'skill_match', 'gap_tolerance_share', 0.5) or 0.5
        scores = {}
        for employee_id in ctx.scoped_ids:
            total_weight, earned = 0.0, 0.0
            for requirement in requirements:
                weight = requirement['weight'] or 1.0
                total_weight += weight
                have = levels.get((employee_id, requirement['skill_id']), 0.0)
                gap = have - requirement['minimum']
                tolerance = (requirement['minimum'] or 1.0) * tolerance_share
                line_score = 1.0 if gap >= 0 else max(0.0, 1.0 + gap / tolerance)
                earned += weight * line_score
                ctx.add_evidence(
                    employee_id, 'skill_match',
                    '%s: %.0f of %.0f required'
                    % (requirement['skill_name'], have,
                       requirement['minimum']))
            scores[employee_id] = (earned / total_weight) if total_weight else None
        return scores

    @api.model
    def _gate_skill_match(self, ctx, line):
        """A skill the seat called mandatory is the seat's own statement.

        Deliberately not conditioned on the criterion's mode: a policy that
        weights skills lightly is saying they matter less to the ranking, not
        that a job needing a welder can be filled by somebody who cannot weld.
        The one way past is a line the seat explicitly opened to stretching.
        """
        requirements = ctx.data.get('skill_requirements', [])
        mandatory = [r for r in requirements if r['requirement'] == 'mandatory']
        if not mandatory:
            return
        levels = ctx.data.get('skill_levels', {})
        for employee_id in ctx.scoped_ids:
            for requirement in mandatory:
                have = levels.get((employee_id, requirement['skill_id']), 0.0)
                if have >= requirement['minimum']:
                    continue
                if requirement['stretch_allowed']:
                    ctx.stretch_ids.add(employee_id)
                    continue
                ctx.reject(
                    employee_id, 'skill_match', 'missing_mandatory_skill',
                    _('%(skill)s at %(have).0f, below the %(need).0f this '
                      'seat requires.',
                      skill=requirement['skill_name'], have=have,
                      need=requirement['minimum']))

    # -- certifications ------------------------------------------------------

    @api.model
    def _prefetch_certification(self, ctx):
        """Who holds each required credential, and for how long.

        Read as records rather than as a pre-computed flag on purpose. A field
        a nightly cron refreshes would let a job starting tomorrow be staffed
        from yesterday's picture of who is licensed, and the screen would look
        identical either way.
        """
        required = ctx.slot.required_certification_skill_ids
        ctx.data['certification_required'] = [
            {'skill_id': skill.id, 'skill_name': skill.display_name}
            for skill in required
        ]
        if not required:
            ctx.data['certification_valid'] = set()
            return

        compat = self.env['aic.hrm.match.skill.compat']
        window_start, window_end = ctx.window
        held = self.env['hr.employee.skill'].search([
            ('employee_id', 'in', ctx.scoped_ids),
            ('skill_id', 'in', required.ids),
            ('verify_state', '=', 'verified'),
        ])
        ctx.data['certification_valid'] = {
            (record.employee_id.id, record.skill_id.id)
            for record in held
            if compat.certification_covers_window(
                record, window_start, window_end)
        }

    @api.model
    def _score_certification(self, ctx):
        """The share of required credentials somebody actually holds.

        Scored as well as gated so the breakdown says what was checked. The
        gate is what decides; this number is what makes the decision readable.
        """
        required = ctx.data.get('certification_required', [])
        if not required:
            return {employee_id: None for employee_id in ctx.scoped_ids}
        valid = ctx.data.get('certification_valid', set())
        scores = {}
        for employee_id in ctx.scoped_ids:
            held = [r for r in required
                    if (employee_id, r['skill_id']) in valid]
            scores[employee_id] = len(held) / len(required)
            for requirement in required:
                covered = (employee_id, requirement['skill_id']) in valid
                ctx.add_evidence(
                    employee_id, 'certification',
                    '%s: %s' % (requirement['skill_name'],
                                'valid for the window' if covered
                                else 'not valid for the window'))
        return scores

    @api.model
    def _gate_certification(self, ctx, line):
        """Holding every required credential, for the whole window.

        Both ends of the validity are checked, not just the expiry. Comparing
        only the end date passes a licence that begins after the job has
        already started, and comparing it against today passes one that runs
        out on the Wednesday.
        """
        required = ctx.data.get('certification_required', [])
        if not required:
            return
        valid = ctx.data.get('certification_valid', set())
        for employee_id in ctx.scoped_ids:
            missing = [r['skill_name'] for r in required
                       if (employee_id, r['skill_id']) not in valid]
            if missing:
                ctx.reject(
                    employee_id, 'certification', 'certification_expired',
                    _('No verified %(skills)s covering the whole window.',
                      skills=', '.join(missing)))

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
