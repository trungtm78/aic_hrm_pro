# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class AicHrmImportTerm(models.Model):
    """Spreadsheet vocabulary -> system values, shipped and extended as DATA.

    Keeping the mapping in records (not source code) lets customers add
    their own spreadsheet wording in any language, and keeps non-English
    strings out of the codebase (language-gate rule).
    """
    _name = 'aic.hrm.import.term'
    _description = 'Import Term Mapping'
    _order = 'term_type, source_term'

    term_type = fields.Selection([
        ('direction', 'KPI direction'),
        ('aggregation', 'Aggregation method'),
        ('priority', 'Priority'),
    ], required=True)
    source_term = fields.Char(
        required=True, help="Spreadsheet wording, matched case-insensitively.")
    value = fields.Char(required=True, help="Technical value it maps to.")

    _term_uniq = models.Constraint(
        'unique (term_type, source_term)',
        'This spreadsheet term is already mapped.',
    )

    @api.model
    def get_map(self, term_type):
        return {
            term.source_term.strip().lower(): term.value
            for term in self.search([('term_type', '=', term_type)])
        }
