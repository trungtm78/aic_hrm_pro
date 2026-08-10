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
import math

import pytz

from odoo import _, api, fields, models

from . import utils

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

    # -- experience ----------------------------------------------------------

    @api.model
    def _prefetch_experience(self, ctx):
        """One read of the ledger for the whole pool, shared by three criteria.

        Project similarity, customer affinity and continuity all ask questions
        of the same rows. Reading them once and letting the three scorers
        interpret them is the difference between one query and three, and the
        ledger is the largest table in the module.
        """
        if 'experience_rows' in ctx.data:
            return
        experience = self.env['aic.hrm.match.experience'].search([
            ('employee_id', 'in', ctx.scoped_ids),
            ('company_id', 'in', ctx.allowed_company_ids),
        ])
        as_of = fields.Date.to_date(str(ctx.as_of)[:10])
        rows = {}
        for record in experience:
            end = record.date_end or record.date_start
            age = ((as_of - fields.Date.to_date(str(end)[:10])).days
                   if end else None)
            rows.setdefault(record.employee_id.id, []).append({
                'tag_ids': record.tag_ids.ids,
                'commercial_partner_id': record.commercial_partner_id.id,
                'project_id': record.project_id.id,
                'hours': record.hours,
                'outcome_score': record.outcome_score,
                'age_days': age,
            })
        ctx.data['experience_rows'] = rows

        # How many people have touched each tag, for the IDF weighting. Counted
        # over the pool that was actually scored, so "rare" means rare here
        # rather than rare in some other company's data.
        holders = {}
        for employee_id, entries in rows.items():
            seen = set()
            for entry in entries:
                seen.update(entry['tag_ids'])
            for tag_id in seen:
                holders[tag_id] = holders.get(tag_id, 0) + 1
        ctx.data['experience_tag_holders'] = holders

    @api.model
    def _prefetch_project_similarity(self, ctx):
        self._prefetch_experience(ctx)
        # The tag tree expanded once per run into {tag_id: distance}. Comparing
        # parent_path prefixes inside the scoring loop is |demand| x |history|
        # string comparisons per candidate, which is what turns a three-second
        # ranking into a minute.
        demand = self.env['aic.hrm.match.request'].browse(
            ctx.request['id']).tag_ids
        ctx.data['demand_tags'] = demand.ids
        ctx.data['demand_related'] = {
            tag.id: tag.expand_related() for tag in demand
        }

    @api.model
    def _score_project_similarity(self, ctx):
        """How much of what this work needs the person has actually done.

        Coverage of the demand, not overlap of the two sets. Jaccard would
        divide by everything the person has ever touched, so somebody who has
        worked across thirty domains scores worse than a specialist for being
        broad - the opposite of what a staffing question is asking.
        """
        demand_tags = ctx.data.get('demand_tags', [])
        if not demand_tags:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        related = ctx.data.get('demand_related', {})
        holders = ctx.data.get('experience_tag_holders', {})
        rows = ctx.data.get('experience_rows', {})
        population = max(len(ctx.scoped_ids), 1)
        half_life = ctx.param('project_similarity', 'half_life_days', 540.0)
        gamma = ctx.param('project_similarity', 'ancestor_gamma', 0.5)
        saturation_hours = ctx.param(
            'project_similarity', 'saturation_hours', 160.0) or 160.0

        weights = {
            tag_id: utils.inverse_document_frequency(
                holders.get(tag_id, 0), population)
            for tag_id in demand_tags
        }
        total_weight = sum(weights.values())
        scores = {}
        for employee_id in ctx.scoped_ids:
            entries = rows.get(employee_id, [])
            if not entries or total_weight <= 0.0:
                scores[employee_id] = 0.0
                continue
            earned, matched = 0.0, []
            for tag_id in demand_tags:
                reachable = related.get(tag_id, {})
                best = 0.0
                for entry in entries:
                    for held in entry['tag_ids']:
                        distance = reachable.get(held)
                        if distance is None:
                            continue
                        volume = (math.log1p(max(entry['hours'], 0.0))
                                  / math.log1p(saturation_hours))
                        credit = (utils.ancestor_credit(distance, gamma)
                                  * utils.half_life_decay(
                                      entry['age_days'], half_life)
                                  * (0.5 + 0.5 * min(volume, 1.0)))
                        if credit > best:
                            best = credit
                if best > 0.0:
                    matched.append(tag_id)
                earned += weights[tag_id] * min(best, 1.0)
            scores[employee_id] = earned / total_weight
            ctx.add_evidence(
                employee_id, 'project_similarity',
                '%d of %d required domains covered'
                % (len(matched), len(demand_tags)))
        return scores

    @api.model
    def _prefetch_customer_affinity(self, ctx):
        self._prefetch_experience(ctx)

    @api.model
    def _score_customer_affinity(self, ctx):
        """Time already spent with this customer, weighted by how recent it is.

        Measured at the commercial partner, so working for two subsidiaries of
        the same group counts as knowing the group - which is what the customer
        experiences when the same face turns up.

        Where a delivery outcome is recorded it weights the touch; where it is
        not, the component is dropped rather than defaulted. Inventing an
        average outcome for work nobody rated is exactly the fabrication this
        design refuses everywhere else.
        """
        partner_id = ctx.request.get('commercial_partner_id')
        if not partner_id:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        rows = ctx.data.get('experience_rows', {})
        half_life = ctx.param('customer_affinity', 'half_life_days', 730.0)
        saturation = (ctx.param('customer_affinity', 'saturation_touch', 3.0)
                      or 3.0)
        scores = {}
        for employee_id in ctx.scoped_ids:
            touch, engagements, rated = 0.0, 0, 0
            for entry in rows.get(employee_id, []):
                if entry['commercial_partner_id'] != partner_id:
                    continue
                engagements += 1
                weight = utils.half_life_decay(entry['age_days'], half_life)
                outcome = entry['outcome_score']
                if outcome:
                    rated += 1
                    weight *= 0.6 + 0.4 * utils.clamp(outcome)
                touch += weight
            scores[employee_id] = utils.clamp(
                math.log1p(touch) / math.log1p(saturation))
            if engagements:
                ctx.add_evidence(
                    employee_id, 'customer_affinity',
                    '%d past engagement(s) with this customer, %d rated'
                    % (engagements, rated))
        return scores

    @api.model
    def _prefetch_continuity(self, ctx):
        self._prefetch_experience(ctx)

    @api.model
    def _score_continuity(self, ctx):
        """Whether this person has worked on this exact project before.

        Deliberately separate from customer affinity. Knowing the customer is
        knowing who to call; knowing the codebase is not having to be told
        where anything is, and on a two-week job the second is worth more.
        """
        project_id = ctx.request.get('project_id')
        if not project_id:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        rows = ctx.data.get('experience_rows', {})
        half_life = ctx.param('continuity', 'half_life_days', 365.0)
        scores = {}
        for employee_id in ctx.scoped_ids:
            best, spells = 0.0, 0
            for entry in rows.get(employee_id, []):
                if entry['project_id'] != project_id:
                    continue
                spells += 1
                best = max(best, utils.half_life_decay(
                    entry['age_days'], half_life, floor=0.0))
            scores[employee_id] = best
            if spells:
                ctx.add_evidence(
                    employee_id, 'continuity',
                    'worked on this project %d time(s) before' % spells)
        return scores

    # -- load, seniority and cost --------------------------------------------

    @api.model
    def _prefetch_profiles(self, ctx):
        if 'profiles' in ctx.data:
            return
        profiles = self.env['aic.hrm.match.profile']._ensure_profiles(
            self.env['hr.employee'].browse(ctx.scoped_ids))
        ctx.data['profiles'] = {p.employee_id.id: p for p in profiles}

    @api.model
    def _prefetch_workload_balance(self, ctx):
        self._prefetch_availability(ctx)
        self._prefetch_profiles(ctx)

    @api.model
    def _score_workload_balance(self, ctx):
        """How far below their own target this person currently is.

        Against their target rather than against each other: not everybody is
        meant to be at a hundred percent, and ranking on raw idleness sends
        work to whoever the company has decided should have slack - the lead
        whose reviews are also their job.
        """
        breakdown = ctx.data.get('availability_breakdown', {})
        profiles = ctx.data.get('profiles', {})
        scores = {}
        for employee_id in ctx.scoped_ids:
            row = breakdown.get(employee_id)
            if not row or row['capacity_hours'] <= 0.0:
                scores[employee_id] = None
                continue
            booked_share = 100.0 * (
                row['capacity_hours'] - row['free_hours']
            ) / row['capacity_hours']
            profile = profiles.get(employee_id)
            target = (profile.utilization_target if profile else 0.0) or 100.0
            scores[employee_id] = utils.clamp((target - booked_share) / target)
            ctx.add_evidence(
                employee_id, 'workload_balance',
                '%.0f%% booked against a %.0f%% target'
                % (booked_share, target))
        return scores

    @api.model
    def _prefetch_seniority_fit(self, ctx):
        self._prefetch_profiles(ctx)

    @api.model
    def _score_seniority_fit(self, ctx):
        """Meeting the seat's level, without paying for exceeding it.

        Being over-qualified scores the same as being right, not better: a seat
        that wanted a mid-level engineer is not better filled by a principal,
        it is more expensively filled, and the cost criterion is where that
        belongs.
        """
        required = ctx.slot.seniority_id
        if not required:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        profiles = ctx.data.get('profiles', {})
        tolerance = (ctx.param('seniority_fit', 'levels_below_tolerated', 2.0)
                     or 2.0)
        scores = {}
        for employee_id in ctx.scoped_ids:
            profile = profiles.get(employee_id)
            seniority = profile.seniority_id if profile else None
            if not seniority:
                scores[employee_id] = None
                continue
            gap = seniority.rank - required.rank
            scores[employee_id] = (
                1.0 if gap >= 0 else utils.clamp(1.0 + gap / tolerance))
            ctx.add_evidence(
                employee_id, 'seniority_fit',
                '%s against %s required'
                % (seniority.display_name, required.display_name))
        return scores

    @api.model
    def _prefetch_cost_fit(self, ctx):
        self._prefetch_profiles(ctx)

    @api.model
    def _score_cost_fit(self, ctx):
        """Hourly cost against the seat's ceiling, in the seat's currency.

        Converted through the company's own rates at the run's frozen moment,
        so a ranking reopened next month is read against the rates it was
        actually decided under.
        """
        slot = ctx.slot
        ceiling = slot.max_hourly_cost
        if not ceiling:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        profiles = ctx.data.get('profiles', {})
        target_currency = slot.currency_id or self.env.company.currency_id
        rate_date = fields.Date.to_date(str(ctx.as_of)[:10])
        scores = {}
        for employee_id in ctx.scoped_ids:
            profile = profiles.get(employee_id)
            cost = profile.sudo().cost_hourly if profile else 0.0
            if not cost:
                # No rate on file is missing data, not free labour. Scoring it
                # as zero cost would put everybody with an incomplete profile
                # at the top of a cost-weighted ranking.
                scores[employee_id] = None
                continue
            source = profile.sudo().currency_id or target_currency
            if source != target_currency:
                cost = source._convert(
                    cost, target_currency,
                    profile.resource_company_id or self.env.company, rate_date)
            scores[employee_id] = utils.clamp(ceiling / cost)
            ctx.add_evidence(
                employee_id, 'cost_fit',
                '%.2f against a ceiling of %.2f %s'
                % (cost, ceiling, target_currency.name))
        return scores

    # -- logistics -----------------------------------------------------------

    @api.model
    def _prefetch_location_fit(self, ctx):
        self._prefetch_profiles(ctx)

    @api.model
    def _score_location_fit(self, ctx):
        """Being where the work is, or being able to get there.

        A seat that allows remote asks nothing of anybody, so the criterion
        reports missing rather than giving everyone the same mark - a criterion
        that cannot separate people should not be consuming weight.
        """
        request = self.env['aic.hrm.match.request'].browse(ctx.request['id'])
        wanted = request.work_location_ids
        if request.remote_allowed or not wanted:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        profiles = ctx.data.get('profiles', {})
        travel_credit = ctx.param('location_fit', 'travel_credit', 0.6) or 0.6
        scores = {}
        for employee_id in ctx.scoped_ids:
            profile = profiles.get(employee_id)
            if not profile:
                scores[employee_id] = None
                continue
            if profile.work_location_id in wanted:
                scores[employee_id] = 1.0
                ctx.add_evidence(
                    employee_id, 'location_fit',
                    'based at %s' % profile.work_location_id.display_name)
            elif profile.willing_to_travel:
                scores[employee_id] = travel_credit
                ctx.add_evidence(employee_id, 'location_fit',
                                 'elsewhere, but willing to travel')
            else:
                scores[employee_id] = 0.0
                ctx.add_evidence(employee_id, 'location_fit',
                                 'not at any of the required locations')
        return scores

    @api.model
    def _prefetch_timezone_overlap(self, ctx):
        self._prefetch_profiles(ctx)

    @api.model
    def _score_timezone_overlap(self, ctx):
        """Working hours a day this person shares with the work.

        Approximated from the offset between the two zones rather than from
        each calendar, which is enough to rank and cheap enough to do for two
        thousand people. The seat's minimum overlap is then a threshold on this
        score rather than a second calculation.
        """
        request = self.env['aic.hrm.match.request'].browse(ctx.request['id'])
        if not request.tz:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        profiles = ctx.data.get('profiles', {})
        working_day = (ctx.param('timezone_overlap', 'working_day_hours', 8.0)
                       or 8.0)
        reference = fields.Datetime.to_datetime(str(ctx.as_of))
        request_offset = self._utc_offset_hours(request.tz, reference)
        scores = {}
        for employee_id in ctx.scoped_ids:
            profile = profiles.get(employee_id)
            zone = (profile.tz if profile else None) or self.env.user.tz
            if not zone:
                scores[employee_id] = None
                continue
            difference = abs(
                self._utc_offset_hours(zone, reference) - request_offset)
            overlap = max(0.0, working_day - difference)
            scores[employee_id] = utils.clamp(overlap / working_day)
            ctx.add_evidence(employee_id, 'timezone_overlap',
                             '%.1f h of overlap a day' % overlap)
        return scores

    @api.model
    def _utc_offset_hours(self, zone_name, moment):
        """Offset in hours, resolved at the run's own moment.

        A ranking taken in July and reopened in December must read the offset
        that applied in July, or half of Europe moves an hour in the retelling.
        """
        try:
            zone = pytz.timezone(zone_name)
        except pytz.UnknownTimeZoneError:
            return 0.0
        offset = zone.utcoffset(moment.replace(tzinfo=None))
        return offset.total_seconds() / 3600.0 if offset else 0.0

    # -- development ---------------------------------------------------------

    @api.model
    def _prefetch_aspiration(self, ctx):
        self._prefetch_profiles(ctx)

    @api.model
    def _score_aspiration(self, ctx):
        """Whether this is work the person said they wanted.

        Off by default, and worth shipping anyway. A ranking built only on what
        somebody has already done keeps them on it until they leave to get away
        from it, and the people that happens to are rarely the ones anybody was
        watching.
        """
        request = self.env['aic.hrm.match.request'].browse(ctx.request['id'])
        wanted_tags = set(request.tag_ids.ids)
        wanted_skills = set(ctx.slot.skill_line_ids.skill_id.ids)
        asked_for = len(wanted_tags) + len(wanted_skills)
        if not asked_for:
            return {employee_id: None for employee_id in ctx.scoped_ids}

        profiles = ctx.data.get('profiles', {})
        scores = {}
        for employee_id in ctx.scoped_ids:
            profile = profiles.get(employee_id)
            if not profile:
                scores[employee_id] = None
                continue
            hits = len(wanted_tags & set(profile.aspiration_tag_ids.ids)) + \
                len(wanted_skills & set(profile.aspiration_skill_ids.ids))
            scores[employee_id] = utils.clamp(hits / asked_for)
            if hits:
                ctx.add_evidence(
                    employee_id, 'aspiration',
                    'asked for %d of the %d things this work involves'
                    % (hits, asked_for))
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
