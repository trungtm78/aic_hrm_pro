# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizard
from .post_init_hook import build_demo_history


def post_init_hook(env):
    """Everything that has to happen after the tables exist.

    One hook, declared in the manifest as the bare name ``post_init_hook``.
    Odoo 19 resolves a dotted ``module.function`` path there; Odoo 18 does not,
    and fails the install with an AttributeError naming the whole string. The
    bare name works on both, which is what a dual-series module needs.

    Two jobs, in order:
    """
    # Access to models only one series ships. Odoo 18 keeps a Skills History
    # row beside every skill line; Odoo 19 dropped the model. A row in
    # ir.model.access.csv naming it aborts the install on the other series, so
    # the grant is made here, where the registry can be asked what exists.
    env['aic.hrm.match.skill.compat'].ensure_optional_access()

    # Demo history, gated on a record only the demo file creates. This runs on
    # every install including --without-demo, so the presence of demo records -
    # not a flag, not a context key - is the only trustworthy signal that
    # fabricating employees is wanted.
    build_demo_history(env)
