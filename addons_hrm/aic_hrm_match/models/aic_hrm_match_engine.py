# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Turning a staffing request into a defensible shortlist.

The order of the phases is the design. Freeze the moment, resolve the policy,
build the pool, load everything once, eliminate, score, normalise, aggregate,
rank, persist. Two properties fall out of it and neither survives a rearranged
version:

**Scoring cannot query.** Everything is loaded in one prefetch pass over the
whole pool, so the scoring phase is arithmetic over dictionaries. A criterion
that reaches for something it did not prefetch gets nothing - a visible bug -
rather than issuing a query per candidate.

**Nobody is dropped silently.** Elimination records a candidate with the gate
that removed them. A shortlist that quietly omits people is worse than none,
because it looks complete.

An abstract model so a customer can replace it, but the contract holds: a
replacement still writes runs, candidates and score lines. "Produce an
explainable ranking" is the deal, not "do as you like".
"""
import hashlib
import json
import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from . import utils
from .match_context import MatchContext

_logger = logging.getLogger(__name__)


class AicHrmMatchEngine(models.AbstractModel):
    _name = 'aic.hrm.match.engine'
    _description = 'Staffing Ranking Engine'

    # -- entry point ---------------------------------------------------------

    @api.model
    def run_match(self, request, slot=None, policy=None):
        """Rank the pool for one slot and return the run."""
        started = time.monotonic()
        slot = slot or request.slot_ids[:1]
        if not slot:
            raise UserError(_(
                "%(name)s has no slot to fill. Nothing to staff is not an "
                "empty shortlist, it is a question that cannot be answered.",
                name=request.display_name))

        policy = policy or self._resolve_policy(request)
        as_of = fields.Datetime.now()

        ctx = MatchContext(
            self.env, request, slot, policy.line_ids.filtered('enabled'),
            self._build_pool(request, policy).ids, as_of=as_of)

        self._prefetch(ctx)
        # Resolved once, here, because both the gate and the normalisation
        # ask what the seat needs and deriving it twice is how the two end
        # up disagreeing about the same seat.
        ctx.needed_hours = self._needed_hours(ctx)
        self._apply_hard_constraints(ctx)
        raw = self._score(ctx)
        normalized = self._normalize(ctx, raw)
        # After normalising, not before: a threshold is expressed on the [0, 1]
        # scale, and the raw value it comes from is in whatever unit the
        # criterion measures.
        self._apply_score_gates(ctx, normalized)
        totals = self._aggregate(ctx, normalized)
        ordered = self._rank(ctx, totals)

        run = self._persist(request, slot, policy, ctx, normalized,
                            totals, ordered, as_of)
        run.sudo().write({
            'state': 'computed',
            'duration_ms': int((time.monotonic() - started) * 1000),
        })
        return run

    # -- phases --------------------------------------------------------------

    @api.model
    def _resolve_policy(self, request):
        """Pick the active policy that claims this request.

        Refuses rather than inventing a default. Falling back to built-in
        weights would rank people under rules nobody chose, and the screen
        would show a confident number either way.
        """
        Policy = self.env['aic.hrm.match.policy']
        candidates = Policy.search([
            ('state', '=', 'active'),
            '|', ('company_id', '=', False),
            ('company_id', '=', request.request_company_id.id),
        ], order='sequence, id')
        for policy in candidates:
            if policy.is_default:
                continue
            domain = json.loads((policy.applies_domain or '[]').replace("'", '"')) \
                if policy.applies_domain not in (False, '', '[]') else []
            if not domain or request.filtered_domain(domain):
                return policy
        default = candidates.filtered('is_default')
        if default:
            return default[0]
        if candidates:
            return candidates[0]
        raise UserError(_(
            "No active scoring policy applies to %(name)s. Ranking without "
            "one would judge people under rules nobody chose.",
            name=request.display_name))

    @api.model
    def _build_pool(self, request, policy):
        """Everybody who could conceivably be considered.

        Through the ORM on purpose: this is the one place record rules get to
        filter, and every raw SQL statement downstream is parameterised by the
        result rather than building its own pool.
        """
        companies = (request.company_ids
                     if policy.allow_cross_company and request.company_ids
                     else request.request_company_id)
        return self.env['hr.employee'].search([
            ('company_id', 'in', companies.ids),
        ])

    @api.model
    def _prefetch(self, ctx):
        """Every query the run needs, once, for the whole pool."""
        scorer = self.env['aic.hrm.match.scorer']
        for line in ctx.policy_lines:
            scorer.prefetch(line.criterion_code, ctx)

    @api.model
    def _apply_hard_constraints(self, ctx):
        """Eliminate, with the reason attached to each person removed."""
        profiles = self.env['aic.hrm.match.profile']._ensure_profiles(
            self.env['hr.employee'].browse(ctx.scoped_ids))
        by_employee = {p.employee_id.id: p for p in profiles}
        slot_start = ctx.slot.date_start

        for employee_id in ctx.scoped_ids:
            profile = by_employee.get(employee_id)
            if not profile:
                continue
            if not profile.staffable:
                ctx.reject(employee_id, 'profile', 'not_staffable',
                               _('Not available for project staffing.'))
            elif profile.match_opt_out:
                ctx.reject(employee_id, 'profile', 'opted_out',
                               profile.opt_out_reason or
                               _('Opted out of staffing.'))
            elif (profile.available_from and slot_start
                    and str(profile.available_from) > str(slot_start)[:10]):
                ctx.reject(
                    employee_id, 'profile', 'available_later',
                    _('Not available until %(date)s.',
                      date=profile.available_from))

        self._apply_criterion_gates(ctx)

    @api.model
    def _eliminating_lines(self, ctx):
        """The policy lines configured to remove people rather than rank them.

        The mode lives on the criterion as a catalogue default and on the line
        as this policy's decision, and the line wins: a stricter round says so
        on its own line instead of editing an entry every other policy shares.
        """
        lines = []
        for line in ctx.policy_lines:
            mode = line.mode_override or (
                line.criterion_id.mode if line.criterion_id else 'soft')
            if mode in ('hard', 'both'):
                lines.append(line)
        return lines

    @api.model
    def _apply_criterion_gates(self, ctx):
        """Gates that answer from the data rather than from a score.

        Every enabled criterion is offered the chance, not only the ones a
        policy marked as eliminating: what the seat itself declares - a
        mandatory skill, a required licence - is not the policy's to soften by
        weighting it lightly. A gate that only cares about the criterion's own
        measurement, availability being the shipped example, checks the mode
        itself.

        Criteria with no gate of their own eliminate through the threshold on
        their normalised score instead, once there is a score to compare.
        """
        scorer = self.env['aic.hrm.match.scorer']
        for line in ctx.policy_lines:
            scorer.gate(line.criterion_code, ctx, line)

    @api.model
    def _apply_score_gates(self, ctx, normalized):
        """Eliminate on the normalised score, for the criteria that ask to.

        Without this a criterion set to eliminate would rank and remove nobody.
        The screen would show the gate configured, the run would show everyone
        passing it, and the discrepancy is invisible unless somebody counts -
        which is the definition of a gate that fails open.
        """
        scorer = self.env['aic.hrm.match.scorer']
        for line in self._eliminating_lines(ctx):
            code = line.criterion_code
            if scorer.has_gate(code):
                # Already decided, on the facts rather than on a score. Running
                # the threshold as well would eliminate twice and attribute the
                # exclusion to whichever ran last.
                continue
            threshold = line.threshold_override or (
                line.criterion_id.threshold if line.criterion_id else 0.0)
            if threshold <= 0.0:
                continue
            scores = normalized.get(code, {})
            for employee_id in ctx.scoped_ids:
                score = scores.get(employee_id)
                # None is missing data, and missing data is not a low score.
                # Eliminating on it would remove somebody for a field nobody
                # filled in - the same mistake as scoring them zero, made
                # permanent.
                if score is None or score >= threshold:
                    continue
                ctx.reject(
                    employee_id, code, 'criterion_threshold',
                    _('%(name)s scored %(score).2f, below the %(threshold).2f '
                      'this policy requires.',
                      name=line.criterion_name or code,
                      score=score, threshold=threshold))

    @api.model
    def _needed_hours(self, ctx):
        capacity = ctx.data.get('availability_capacity', {})
        if ctx.slot.required_hours:
            return ctx.slot.required_hours
        return ctx.slot.fte_ratio * max(capacity.values(), default=0.0)

    @api.model
    def _score(self, ctx):
        """``{code: {employee_id: raw}}``. No queries happen here."""
        scorer = self.env['aic.hrm.match.scorer']
        return {
            line.criterion_code: scorer.score(line.criterion_code, ctx)
            for line in ctx.policy_lines
        }

    @api.model
    def _normalize(self, ctx, raw):
        """Map every raw value into [0, 1] where higher is better."""
        normalized = {}
        for line in ctx.policy_lines:
            code = line.criterion_code
            criterion = line.criterion_id
            values = raw.get(code, {})
            kind = criterion.normalization if criterion else 'none'
            direction = (criterion.direction if criterion else 'higher')
            saturation = criterion.saturation_value if criterion else 0.0
            if code == 'availability' and not saturation:
                # The slot's own requirement is the natural full mark, and
                # taking it from the slot keeps the scorer returning a raw
                # number rather than a ratio it would then be divided again.
                saturation = self._needed_hours(ctx) or 1.0

            known = [(employee_id, value)
                     for employee_id, value in values.items()
                     if value is not None]
            if kind == 'rank':
                # The one normalisation that cannot be done a value at a time:
                # a percentile only exists relative to the others, and ties
                # have to share a midrank so the score does not depend on the
                # order Postgres returned the rows in.
                positions = utils.rank_normalize(
                    [value for _employee_id, value in known],
                    higher_is_better=(direction == 'higher'))
                scores = dict(zip([employee_id for employee_id, _v in known],
                                  positions))
            else:
                stats = self._pool_stats([value for _e, value in known])
                scores = {
                    employee_id: self._normalize_one(
                        value, kind, direction, saturation, stats)
                    for employee_id, value in known
                }
            for employee_id, value in values.items():
                if value is None:
                    scores[employee_id] = None
            normalized[code] = scores
        return normalized

    @api.model
    def _pool_stats(self, pool):
        if not pool:
            return {'pool': (0.0, 0.0), 'stats': (0.0, 0.0)}
        mean = sum(pool) / len(pool)
        variance = sum((v - mean) ** 2 for v in pool) / len(pool)
        return {'pool': (min(pool), max(pool)),
                'stats': (mean, variance ** 0.5)}

    @api.model
    def _normalize_one(self, value, kind, direction, saturation, stats):
        higher = direction == 'higher'
        try:
            return utils.normalize(
                value, kind=kind, higher_is_better=higher,
                saturation=saturation or None, pool=stats['pool'],
                pool_stats=stats['stats'])
        except ValueError:
            # A misconfigured criterion must not take the whole run down; it
            # contributes nothing and the candidate's confidence flag shows it.
            _logger.warning('Criterion normalisation failed for value %r', value)
            return None

    @api.model
    def _aggregate(self, ctx, normalized):
        """Weighted average over the criteria that had something to say."""
        policy = ctx.policy_lines[:1].policy_id
        totals = {}
        for employee_id in ctx.scoped_ids:
            pairs, used_weight, total_weight = [], 0.0, 0.0
            for line in ctx.policy_lines:
                weight = line.weight
                total_weight += weight
                score = normalized.get(line.criterion_code, {}).get(employee_id)
                if score is None:
                    continue
                pairs.append((score, weight))
                used_weight += weight
            raw_score = utils.weighted_average(pairs)
            coverage = (used_weight / total_weight * 100.0) if total_weight else 0.0
            totals[employee_id] = {
                'raw_score': raw_score,
                'total_score': utils.clamp(raw_score),
                'low_confidence': coverage < (policy.min_effective_weight_pct
                                              or 0.0),
            }
        return totals

    @api.model
    def _rank(self, ctx, totals):
        """Order the eligible, breaking ties without a hidden bias.

        Sorting equal scores by employee id looks harmless and means the lowest
        id wins every tie forever - a bias that compounds for years and appears
        in no report.
        """
        reference = ctx.request['reference']
        epoch = ctx.request['rotation_epoch']
        eligible = ctx.eligible_ids
        return sorted(
            eligible,
            key=lambda employee_id: (
                -totals[employee_id]['total_score'],
                utils.tiebreak_salt(reference, epoch, employee_id),
            ))

    # -- persistence ---------------------------------------------------------

    @api.model
    def _persist(self, request, slot, policy, ctx, normalized, totals,
                 ordered, as_of):
        snapshot = self._build_snapshot(request, slot, policy, ctx, as_of)
        run = self.env['aic.hrm.match.run'].create({
            'request_id': request.id,
            'slot_id': slot.id,
            'policy_id': policy.id,
            'policy_version': policy.version,
            'as_of': as_of,
            'parameter_snapshot': json.dumps(snapshot, default=str,
                                             sort_keys=True),
            'input_hash': hashlib.sha256(
                json.dumps(snapshot, default=str, sort_keys=True).encode()
            ).hexdigest(),
        })

        ranks = {employee_id: index + 1
                 for index, employee_id in enumerate(ordered)}
        detailed = set(ordered[:policy.top_n]) if policy.persist_mode == \
            'ranked_only' else set(ctx.scoped_ids)

        candidate_values = []
        for employee_id in ctx.scoped_ids:
            eligible = employee_id not in ctx.rejections
            reasons = ctx.rejections.get(employee_id, [])
            totals_row = totals.get(employee_id, {})
            candidate_values.append({
                'run_id': run.id,
                'slot_id': slot.id,
                'identity_ref': '%s-%s' % (run.reference, employee_id),
                'employee_id': employee_id,
                'eligible': eligible,
                'is_stretch': employee_id in ctx.stretch_ids,
                'rank': ranks.get(employee_id, 0),
                'raw_score': totals_row.get('raw_score', 0.0),
                'total_score': totals_row.get('total_score', 0.0),
                'low_confidence': totals_row.get('low_confidence', False),
                'rejection_code': reasons[0]['rejection_code'] if reasons else False,
                'rejection_detail': '\n'.join(r['detail'] for r in reasons),
                'free_hours': ctx.data.get('availability', {}).get(
                    employee_id, 0.0),
                'capacity_hours': ctx.data.get(
                    'availability_capacity', {}).get(employee_id, 0.0),
            })
        candidates = self.env['aic.hrm.match.candidate'].with_context(
            tracking_disable=True, mail_create_nolog=True).create(
                candidate_values)
        by_employee = {c.employee_id.id: c for c in candidates}

        self._persist_score_lines(ctx, normalized, by_employee, detailed)
        run.sudo().write({
            'candidate_count': len(candidates),
            'eligible_count': len(ctx.eligible_ids),
            'rejected_count': len(ctx.rejections),
        })
        return run

    @api.model
    def _persist_score_lines(self, ctx, normalized, by_employee, detailed):
        """Write the breakdown.

        Everyone who was excluded keeps the line that excluded them, whatever
        the persistence mode says: dropping presentation detail is a storage
        decision, dropping the reason somebody was removed is not.
        """
        line_values, evidence_by_key = [], {}
        for policy_line in ctx.policy_lines:
            code = policy_line.criterion_code
            criterion = policy_line.criterion_id
            for employee_id, candidate in by_employee.items():
                knocked = any(r['criterion_code'] == code
                              for r in ctx.rejections.get(employee_id, []))
                if employee_id not in detailed and not knocked:
                    continue
                score = normalized.get(code, {}).get(employee_id)
                missing = score is None
                weighted = 0.0 if missing else score * policy_line.weight
                line_values.append({
                    'candidate_id': candidate.id,
                    'criterion_id': criterion.id if criterion else False,
                    'criterion_code': code,
                    'criterion_name': policy_line.criterion_name,
                    'criterion_provider': policy_line.criterion_provider,
                    'criterion_sensitive': bool(
                        criterion and criterion.is_sensitive),
                    'normalized_score': 0.0 if missing else score,
                    'weight': policy_line.weight,
                    'weighted_score': weighted,
                    'is_missing': missing,
                    'is_knockout': knocked,
                    'passed': not knocked,
                })
                evidence_by_key[(candidate.id, code)] = ctx.evidence.get(
                    (employee_id, code), [])

        lines = self.env['aic.hrm.match.score.line'].create(line_values)
        evidence_values = []
        for line in lines:
            for index, entry in enumerate(
                    evidence_by_key.get((line.candidate_id.id,
                                         line.criterion_code), [])):
                evidence_values.append({
                    'score_line_id': line.id,
                    'sequence': index * 10,
                    'label': entry['label'],
                    'res_model': entry.get('res_model'),
                    'res_id': entry.get('res_id'),
                })
        if evidence_values:
            self.env['aic.hrm.match.evidence'].create(evidence_values)

    @api.model
    def _build_snapshot(self, request, slot, policy, ctx, as_of):
        """What this run was configured with, resolved.

        Written so the ranking can be explained after the policy has moved on -
        which is the whole reason versions exist.
        """
        return {
            'as_of': as_of,
            'request': ctx.request,
            'slot': {'id': slot.id, 'name': slot.name,
                     'required_hours': slot.required_hours,
                     'fte_ratio': slot.fte_ratio},
            'policy': {'code': policy.code, 'version': policy.version,
                       'aggregation': policy.aggregation,
                       'tiebreak_version': policy.tiebreak_version},
            'weights': [
                {'code': line.criterion_code, 'weight': line.weight,
                 'provider': line.criterion_provider}
                for line in ctx.policy_lines
            ],
            'pool_size': len(ctx.scoped_ids),
            'pool_ids': sorted(ctx.scoped_ids),
        }
