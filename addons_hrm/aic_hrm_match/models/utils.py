# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Scoring mathematics. Deliberately free of any Odoo import.

Every criterion the engine runs passes through this module, and the engine
scores two thousand candidates without touching the database, so these have to
be plain functions over plain numbers: testable in milliseconds, callable
inside a tight loop, and impossible to accidentally make issue a query.

Two rules run through all of it:

* **Everything lands in [0, 1], higher is better.** A criterion measured in
  hours and a criterion measured in project counts have to be addable after
  weighting, and a criterion that escapes the range silently steals weight from
  every other one.
* **Missing or degenerate input returns the neutral answer, never the punishing
  one.** A criterion that cannot separate two people must not decide between
  them; scoring an unknown as zero turns a gap in the HR data into a permanent
  disadvantage for the person it is missing for.
"""
import hashlib
import math

EPSILON = 1e-9

# Steepness of the logistic used for z-score normalisation. 1.5 puts roughly
# two standard deviations inside the (0.05, 0.95) band, which keeps an outlier
# from flattening everyone else into an indistinguishable middle.
_LOGISTIC_K = 1.5

NORMALIZATIONS = ('none', 'ratio', 'log', 'minmax', 'zscore', 'rank')


def clamp(value, low=0.0, high=1.0):
    """Confine a value to a closed range."""
    return low if value < low else high if value > high else value


def weighted_average(pairs):
    """Weighted mean of ``(value, weight)`` pairs.

    Non-positive weights are dropped rather than subtracted: a disabled or
    neutralised criterion contributes nothing, and a negative weight in the
    data is a configuration mistake that must not quietly invert a score.
    Returns 0.0 when nothing carries weight, because a candidate scored on no
    criteria at all is a state the ranking has to survive.
    """
    total = 0.0
    weight_sum = 0.0
    for value, weight in pairs:
        if weight is None or weight <= 0.0:
            continue
        total += value * weight
        weight_sum += weight
    return total / weight_sum if weight_sum > EPSILON else 0.0


def normalize(value, kind='none', higher_is_better=True, saturation=None,
              pool=None, pool_stats=None):
    """Map a raw criterion value into [0, 1] where higher is better.

    ``saturation`` is the raw value that counts as a full score (ratio, log).
    ``pool`` is the ``(min, max)`` of the eligible pool (minmax).
    ``pool_stats`` is the ``(mean, stdev)`` of the eligible pool (zscore).

    Pool-relative kinds are available but pool-independent ones are preferred:
    a score that means the same thing across two runs is the precondition for
    comparing them, and the run snapshot records which kind produced it.
    """
    if kind not in NORMALIZATIONS:
        raise ValueError('unknown normalization %r' % (kind,))

    if kind == 'none':
        score = clamp(value)
    elif kind == 'ratio':
        score = _ratio(value, saturation, higher_is_better)
        return clamp(score)
    elif kind == 'log':
        score = _logarithmic(value, saturation)
    elif kind == 'minmax':
        score = _minmax(value, pool)
    elif kind == 'zscore':
        score = _zscore(value, pool_stats)
    else:                                     # rank
        raise ValueError(
            'rank normalisation needs the whole pool; call rank_normalize')

    score = clamp(score)
    return score if higher_is_better else 1.0 - score


def _require_saturation(saturation, kind):
    if not saturation or saturation <= 0.0:
        raise ValueError(
            '%s normalisation needs a positive saturation value; %r given'
            % (kind, saturation))
    return saturation


def _ratio(value, saturation, higher_is_better):
    """Proportion of a target, in whichever direction the target points.

    Handled here rather than through the generic invert-at-the-end path
    because "lower is better" for a ratio means *target over value*, not
    *one minus the fraction*: at twice the ceiling the score is a half, not a
    negative number.
    """
    saturation = _require_saturation(saturation, 'ratio')
    if higher_is_better:
        return value / saturation
    if value <= 0.0:
        # Zero cost, zero conflicting hours: nothing to be under budget of.
        return 1.0
    return saturation / value


def _logarithmic(value, saturation):
    """Diminishing returns towards a saturation point.

    The default for counted things - engagements with a customer, similar
    projects delivered. The fifth repeat says much less than the first, and
    unlike a pool-relative kind the answer does not move when the pool does.
    """
    saturation = _require_saturation(saturation, 'log')
    return math.log1p(max(value, 0.0)) / math.log1p(saturation)


def _minmax(value, pool):
    """Position inside the pool's observed range.

    A pool with no spread returns the neutral 0.5 for everyone. Returning 1.0
    would hand this criterion its full weight on the strength of an observation
    that separates nobody.
    """
    if not pool:
        raise ValueError('minmax normalisation needs a (min, max) pool')
    low, high = pool
    if high - low <= EPSILON:
        return 0.5
    return (value - low) / (high - low)


def _zscore(value, pool_stats):
    """Logistic of the standard score. Tolerates outliers better than minmax,
    where one extreme value compresses everybody else into the middle."""
    if not pool_stats:
        raise ValueError('zscore normalisation needs (mean, stdev)')
    mean, stdev = pool_stats
    if stdev is None or stdev <= EPSILON:
        return 0.5
    return 1.0 / (1.0 + math.exp(-_LOGISTIC_K * (value - mean) / stdev))


def rank_normalize(values, higher_is_better=True):
    """Percentile position of each value, ties sharing a midrank.

    Immune to outliers and to the unit being measured; it throws away how far
    apart the values are, so it suits criteria where the ordering is
    trustworthy and the magnitude is not.

    Ties take the average of the positions they span. Breaking them by list
    order would make the score depend on the order rows came back from
    Postgres, which is unstable between runs and biased in a way nobody sees.
    """
    count = len(values)
    if count == 0:
        return []
    if count == 1:
        return [0.5]
    order = sorted(range(count), key=lambda index: values[index])
    midranks = [0.0] * count
    position = 0
    while position < count:
        end = position
        while end + 1 < count and abs(values[order[end + 1]]
                                      - values[order[position]]) <= EPSILON:
            end += 1
        shared = (position + end) / 2.0
        for index in range(position, end + 1):
            midranks[order[index]] = shared
        position = end + 1
    scores = [(rank + 0.5) / count for rank in midranks]
    return scores if higher_is_better else [1.0 - score for score in scores]


def half_life_decay(age_days, half_life_days=730.0, grace_days=365.0,
                    floor=0.6):
    """Weight of something that happened ``age_days`` ago.

    Full weight inside the grace period, then halving every ``half_life_days``,
    never below ``floor``. The floor matters: a skill used four years ago is
    worth less than one used last month, but it is not worth nothing, and a
    decay that reaches zero would quietly turn a soft criterion into a gate.

    An unknown age returns full weight. Not knowing when someone last used a
    skill is a gap in the record, not evidence that they have forgotten it.
    """
    if age_days is None:
        return 1.0
    beyond = age_days - grace_days
    if beyond <= 0.0:
        return 1.0
    if half_life_days <= EPSILON:
        return floor
    decayed = math.exp(-math.log(2.0) * beyond / half_life_days)
    return max(floor, decayed)


def inverse_document_frequency(holders, population):
    """How much a capability distinguishes the person who has it.

    Everyone can build a web page; three people know the billing mainframe.
    Without this, a request tagged with both is dominated by the common tag
    simply because more people match it.
    """
    if population <= 0:
        return 0.0
    return math.log1p(population / (1.0 + max(holders, 0)))


def ancestor_credit(distance, gamma=0.5):
    """Credit for a related-but-not-identical capability.

    Exact match scores 1.0; each step up or down the taxonomy multiplies by
    ``gamma``. Somebody who has done React has done Frontend, and pretending
    otherwise makes the tag tree decorative.

    ``None`` means unrelated, which earns nothing.
    """
    if distance is None:
        return 0.0
    return gamma ** max(int(distance), 0)


def tiebreak_salt(request_reference, rotation_epoch, employee_id):
    """A stable pseudo-random number in [0, 1) for breaking exact ties.

    Sorting equal scores by ``employee_id`` looks harmless and means the
    lowest id wins every tie forever - a systematic bias that accumulates for
    years and that nobody would ever see in a report.

    Keyed on the request reference so a rerun of the same request produces the
    same order, and on a rotation epoch that only advances when a decision is
    made, so genuinely new staffing rounds rotate while reranks stay stable.
    """
    key = '%s:%s:%s' % (request_reference, rotation_epoch, employee_id)
    digest = hashlib.md5(key.encode('utf-8')).hexdigest()[:12]
    return int(digest, 16) / float(1 << 48)
