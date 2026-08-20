# -*- coding: utf-8 -*-
# Part of AIC HRM Pro. See LICENSE file for full copyright and licensing details.
"""UAT fixture engine.

A fixture is a NAMED piece of test data - ``<entity>.<state>.<lifecycle>.<shape>``
- that can be built, addressed by id, and taken away again. The suite's unit
tests build their data inside ``setUpClass`` and a transaction rollback erases
it; nobody can open a browser and look at a scorecard that is deliberately
80% weighted, because no such record survives a test run.

Three properties are load-bearing:

* **Reproducible.** Applying a fixture twice returns the same instance instead
  of a second copy, so a UAT run that dies half way can simply be restarted.
* **Removable.** Every record a setup creates is written to a ledger, and
  cleanup unlinks the ledger in reverse. The ledger is what makes cleanup
  provable rather than hopeful - a setup cannot forget a record it created
  because it never creates one outside ``_track``.
* **Relative in time.** Dates are offsets from today, never literals. A
  fixture called ``kr.stale.D-30`` has to still be stale next quarter.
"""
import json
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# System parameter that has to be on before any fixture may run. The group
# check alone is not enough: an HR administrator on a production database is a
# legitimate, common role, and this RPC creates business data.
UAT_MODE_PARAM = 'aic_hrm.uat_mode'


class AicHrmUatFixture(models.Model):
    """One applied fixture instance."""
    _name = 'aic.hrm.uat.fixture'
    _description = 'UAT Fixture Instance'
    _order = 'applied_on desc, id desc'
    _rec_name = 'fixture_id'

    fixture_id = fields.Char(required=True, index=True)
    applied_on = fields.Datetime(default=fields.Datetime.now, readonly=True)
    outputs_json = fields.Text(readonly=True)
    record_ids = fields.One2many('aic.hrm.uat.fixture.record', 'instance_id')
    record_count = fields.Integer(compute='_compute_record_count')

    _fixture_uniq = models.Constraint(
        'unique (fixture_id)',
        'This fixture is already applied; clean it up before re-applying.',
    )

    @api.depends('record_ids')
    def _compute_record_count(self):
        for instance in self:
            instance.record_count = len(instance.record_ids)

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------
    @api.model
    def _catalog(self):
        """``fixture_id`` -> spec. Every ``fixtures_*.py`` file extends this.

        Spec keys: ``doc``, ``entity``, ``state``, ``lifecycle``, ``shape``,
        ``depends`` (fixture ids), ``setup`` (method name), ``outputs``
        (names the setup promises to return).
        """
        return {}

    @api.model
    def catalog(self):
        """RPC-friendly catalog listing, applied flag included."""
        self._check_enabled()
        applied = set(self.search([]).mapped('fixture_id'))
        return [
            dict(spec, id=fid, applied=fid in applied)
            for fid, spec in sorted(self._catalog().items())
        ]

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    @api.model
    def _check_enabled(self):
        if not self.env.su and not self.env.user.has_group(
                'aic_hrm_base.group_hrm_admin'):
            raise AccessError(_(
                "UAT fixtures may only be driven by an HR administrator."))
        enabled = self.env['ir.config_parameter'].sudo().get_param(
            UAT_MODE_PARAM)
        if enabled not in ('1', 'True', 'true'):
            raise UserError(_(
                "UAT mode is off on this database. Set the system parameter "
                "%(param)s to 1 to allow fixtures to write data.",
                param=UAT_MODE_PARAM))

    # ------------------------------------------------------------------
    # Date helpers - fixtures never hard-code a date
    # ------------------------------------------------------------------
    @api.model
    def _today(self):
        return fields.Date.context_today(self)

    @api.model
    def _day(self, offset=0):
        return self._today() + relativedelta(days=offset)

    @api.model
    def _month(self, offset=0):
        return self._today() + relativedelta(months=offset)

    # ------------------------------------------------------------------
    # Apply / cleanup
    # ------------------------------------------------------------------
    def _track(self, records):
        """Record what a setup created so cleanup can undo exactly that.

        Order matters and is preserved: cleanup walks the ledger backwards.
        Track the PARENT of a record the product refuses to unlink - an
        applied calibration line is immutable for everyone, superuser
        included, but its session owns it with ``ondelete='cascade'``, so
        deleting the session removes the line in SQL without ever calling its
        ``unlink``.
        """
        self.ensure_one()
        Line = self.env['aic.hrm.uat.fixture.record'].sudo()
        start = len(self.record_ids)
        Line.create([
            {'instance_id': self.id, 'sequence': start + index,
             'res_model': record._name, 'res_id': record.id}
            for index, record in enumerate(records)
        ])
        return records

    @api.model
    def _dependency_order(self, fixture_ids):
        """Depth-first expansion of ``depends``, parents before children."""
        catalog = self._catalog()
        ordered = []

        def visit(fid, trail):
            if fid in ordered:
                return
            if fid in trail:
                raise UserError(_(
                    "Fixture dependency cycle: %(trail)s",
                    trail=' -> '.join(list(trail) + [fid])))
            spec = catalog.get(fid)
            if not spec:
                raise UserError(_("Unknown fixture %(fid)s.", fid=fid))
            for parent in spec.get('depends', ()):
                visit(parent, trail | {fid})
            if fid not in ordered:
                ordered.append(fid)

        for fid in fixture_ids:
            visit(fid, frozenset())
        return ordered

    @api.model
    def apply_fixtures(self, fixture_ids):
        """Build the named fixtures, and everything they depend on.

        Returns ``{fixture_id: outputs}`` for every fixture in the closure, so
        a caller that asked for one thing still learns the ids of the org
        chart underneath it.
        """
        self._check_enabled()
        catalog = self._catalog()
        results = {}
        for fid in self._dependency_order(fixture_ids):
            existing = self.search([('fixture_id', '=', fid)], limit=1)
            if existing:
                results[fid] = existing.outputs
                continue
            spec = catalog[fid]
            instance = self.create({'fixture_id': fid})
            outputs = getattr(instance, spec['setup'])(results) or {}
            missing = set(spec.get('outputs', ())) - set(outputs)
            if missing:
                raise UserError(_(
                    "Fixture %(fid)s promised outputs it did not return: "
                    "%(missing)s",
                    fid=fid, missing=', '.join(sorted(missing))))
            instance.outputs_json = json.dumps(outputs)
            results[fid] = outputs
            _logger.info("UAT fixture applied: %s (%s records)",
                         fid, len(instance.record_ids))
        return results

    @property
    def outputs(self):
        self.ensure_one()
        return json.loads(self.outputs_json or '{}')

    @api.model
    def _dependents_of(self, fixture_ids):
        """Fixtures that would be left dangling by removing these."""
        catalog = self._catalog()
        wanted, grown = set(fixture_ids), True
        while grown:
            grown = False
            for fid, spec in catalog.items():
                if fid in wanted:
                    continue
                if wanted & set(spec.get('depends', ())):
                    wanted.add(fid)
                    grown = True
        return wanted

    @api.model
    def cleanup_fixtures(self, fixture_ids):
        """Remove the fixtures and anything built on top of them.

        Cascading is not a convenience: cleaning ``org.base.D0`` while a
        scorecard still points at one of its employees would leave a database
        that no fixture id describes.
        """
        self._check_enabled()
        targets = self._dependents_of(fixture_ids)
        instances = self.search([('fixture_id', 'in', list(targets))])
        self._unlock_cycles(instances)
        removed = 0
        # Newest instance first, and inside it the newest record first.
        for instance in instances.sorted(lambda i: i.applied_on, reverse=True):
            for line in instance.record_ids.sorted('sequence', reverse=True):
                record = self.env[line.res_model].browse(line.res_id).exists()
                if record:
                    record.sudo().unlink()
                    removed += 1
            instance.sudo().unlink()
        return {'fixtures': sorted(targets), 'records_removed': removed}

    @api.model
    def _unlock_cycles(self, instances):
        """Return every cycle these fixtures built to draft before teardown.

        The product is right to refuse: a closed cycle may not be edited and
        only a draft cycle may be deleted, because a performance record people
        were paid against must not quietly change. That rule is about the
        business, not about a test database - so the reversal lives here, in
        the UAT module, in one named place, and it uses `_write` so it cannot
        be mistaken for the supported path. Nothing outside teardown calls it.
        """
        lines = self.env['aic.hrm.uat.fixture.record'].sudo().search([
            ('instance_id', 'in', instances.ids),
            ('res_model', '=', 'aic.hrm.cycle'),
        ])
        cycles = self.env['aic.hrm.cycle'].sudo().browse(
            lines.mapped('res_id')).exists()
        stuck = cycles.filtered(lambda c: c.state != 'draft')
        if stuck:
            # Flush first, then invalidate: `_write` goes straight to SQL,
            # so a pending in-memory value from the setup that opened the
            # cycle would be flushed back over it a moment later, and the
            # teardown would fail with the state it had just cleared.
            self.env.flush_all()
            stuck._write({'state': 'draft'})
            stuck.invalidate_recordset(['state'])
            _logger.info("UAT teardown returned %s cycle(s) to draft: %s",
                         len(stuck), ', '.join(stuck.mapped('code')))

    @api.model
    def reset_all(self):
        """Take the database back to a bare install of the suite."""
        self._check_enabled()
        return self.cleanup_fixtures(self.search([]).mapped('fixture_id'))

    @api.model
    def apply_all(self):
        self._check_enabled()
        return self.apply_fixtures(list(self._catalog()))

    def action_cleanup(self):
        return self.cleanup_fixtures(self.mapped('fixture_id'))


class AicHrmUatFixtureRecord(models.Model):
    """Ledger line: one record a fixture created, and the order it came in."""
    _name = 'aic.hrm.uat.fixture.record'
    _description = 'UAT Fixture Ledger Line'
    _order = 'instance_id, sequence'

    instance_id = fields.Many2one(
        'aic.hrm.uat.fixture', required=True, index=True, ondelete='cascade')
    sequence = fields.Integer(required=True)
    res_model = fields.Char(required=True)
    res_id = fields.Integer(required=True)
