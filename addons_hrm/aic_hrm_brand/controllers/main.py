# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import request


class AicHrmBrandEntry(http.Controller):
    """Give the product its own front door.

    The address a customer is handed is part of the product's identity,
    so the suite answers on /aic and forwards to the web client. The
    platform route keeps working - this adds an entry point, it does
    not take one away.
    """

    @http.route(['/aic', '/aic/<path:subpath>'], type='http', auth='public',
                website=False)
    def aic_entry(self, subpath=None, **kwargs):
        target = '/odoo' + ('/' + subpath if subpath else '')
        return request.redirect(target, local=True)
