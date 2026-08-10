# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Building the demo staffing history, once.

Called from the module's single post-init hook rather than being
one itself: two hooks with the same name in one module is how the
manifest ends up pointing at a dotted path, which Odoo 18 cannot
resolve.
"""


def build_demo_history(env):
    """Mark demo data as installed.
    
    The hook fires on EVERY install/upgrade (even --without-demo all).
    Use the sentinel record to gate demo data generation: only run if
    the sentinel exists (demo XML was loaded) and hasn't been marked
    generated yet.
    """
    # Check if demo data exists
    sentinel = env.ref('aic_hrm_match.demo_sentinel', raise_if_not_found=False)
    
    if not sentinel or sentinel.generated:
        # Demo not loaded, or already generated — skip
        return
    
    # Mark as generated to prevent re-running
    sentinel.write({'generated': True})
    
    # TODO: CP9 will add actual demo data generation here:
    # - 24 employees across 5 departments
    # - 4 staffing requests
    # - 2 ranking runs (computed)
    # - decisions + allocations
    # Using relative dates from today via relativedelta()
