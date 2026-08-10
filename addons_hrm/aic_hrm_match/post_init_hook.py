# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""Demo data post-installation hook — idempotent."""


def post_init_hook(env):
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
