# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Pure scoring math for the AIC HRM Pro suite.

These functions are ORM-free on purpose: every score shown anywhere in the
suite must be reproducible from this module alone, and unit-testable without
a database.
All results are normalized to the 0.0..cap scale (Google OKR convention,
cap defaults to 1.0).
"""


def clamp(value, lo, hi):
    """Clamp ``value`` into the closed interval [lo, hi]."""
    return max(lo, min(hi, value))


def safe_div(numerator, denominator, default=0.0):
    """Division that returns ``default`` instead of raising on zero."""
    if not denominator:
        return default
    return numerator / denominator


def progress_linear(baseline, current, target, higher_is_better=True, cap=1.0):
    """Normalized progress of a key result between baseline and target.

    Returns 0.0 when the configuration is degenerate (target == baseline):
    that situation is blocked upstream by model constraints, and the math
    must stay total (never raise) for batch compute paths.
    """
    if higher_is_better:
        span = target - baseline
        raw = safe_div(current - baseline, span) if span > 0 else 0.0
    else:
        span = baseline - target
        raw = safe_div(baseline - current, span) if span > 0 else 0.0
    return clamp(raw, 0.0, cap)


def achievement(actual, target, direction, cap=1.0):
    """KPI achievement ratio for a period or cycle result.

    direction:
        'higher'  -- actual / target
        'lower'   -- 2 - actual / target (linear penalty; requires target > 0,
                     enforced upstream by model constraints)
        'boolean' -- pass (>= 1) / fail
    """
    if direction == 'boolean':
        raw = 1.0 if actual >= 1 else 0.0
    elif direction == 'lower':
        raw = 2.0 - safe_div(actual, target, default=2.0) if target > 0 else 0.0
    else:
        raw = safe_div(actual, target) if target > 0 else 0.0
    return clamp(raw, 0.0, cap)


def weighted_average(pairs):
    """Weighted mean of ``[(value, weight), ...]``; 0.0 when weights sum to 0."""
    total_weight = sum(weight for _value, weight in pairs)
    if not total_weight:
        return 0.0
    return sum(value * weight for value, weight in pairs) / total_weight
