# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from . import models
from . import wizard


def post_init_hook(env):
    """Grant access to models only some Odoo series ship.

    Odoo 18 keeps a Skills History row beside every skill line and writes one
    whenever a line changes; Odoo 19 dropped the model. A row in
    ir.model.access.csv naming it would abort the install on 19, so the grant
    is made here, where the registry can be asked whether the model exists.
    """
    env['aic.hrm.match.skill.compat'].ensure_optional_access()
