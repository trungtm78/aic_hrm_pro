# -*- coding: utf-8 -*-
"""Drive the UAT fixture catalogue over JSON-RPC.

The same entry point the browser tests use, on purpose. If a person seeds the
database one way and the automated run seeds it another, the two are testing
different products and only one of them is the one that ships.

    python tools/seed_uat.py --catalog
    python tools/seed_uat.py --all
    python tools/seed_uat.py cycle.locked.D0 assignment.underweight.D0
    python tools/seed_uat.py --reset

Standard library only: no dependency to install before a test run can start.
"""
import argparse
import json
import sys
import urllib.request

DEFAULT_URL = 'http://127.0.0.1:8075'
DEFAULT_DB = 'AIC_HRM_UAT'
UAT_MODE_PARAM = 'aic_hrm.uat_mode'


class OdooRpcError(RuntimeError):
    pass


class Client:
    """Minimal JSON-RPC client against /jsonrpc."""

    def __init__(self, url, db, login, password):
        self.url = url.rstrip('/')
        self.db = db
        self.login = login
        self.password = password
        self.uid = self._call('common', 'login', [db, login, password])
        if not self.uid:
            raise OdooRpcError(
                'Login refused for %s on %s. The UAT server is locked to one '
                'database by dbfilter; check it is running on %s.'
                % (login, db, self.url))

    def _call(self, service, method, args):
        payload = {
            'jsonrpc': '2.0', 'method': 'call',
            'params': {'service': service, 'method': method, 'args': args},
            'id': 1,
        }
        request = urllib.request.Request(
            self.url + '/jsonrpc',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=600) as response:
            body = json.loads(response.read().decode('utf-8'))
        if 'error' in body:
            message = body['error'].get('data', {}).get(
                'message', json.dumps(body['error']))
            raise OdooRpcError(message)
        return body['result']

    def execute(self, model, method, *args, **kwargs):
        return self._call('object', 'execute_kw', [
            self.db, self.uid, self.password, model, method,
            list(args), kwargs])


def enable_uat_mode(client):
    """Second lock, opened deliberately and reported out loud."""
    client.execute('ir.config_parameter', 'set_param',
                   UAT_MODE_PARAM, '1')
    print('uat_mode: on  (%s)' % UAT_MODE_PARAM)


def print_catalog(client):
    rows = client.execute('aic.hrm.uat.fixture', 'catalog')
    width = max(len(row['id']) for row in rows)
    print('%-*s  %-8s  %s' % (width, 'FIXTURE', 'APPLIED', 'SHAPE'))
    for row in rows:
        print('%-*s  %-8s  %s' % (
            width, row['id'], 'yes' if row['applied'] else '-',
            row.get('shape', '')))
        print('%-*s  %s' % (width + 10, '', row['doc']))
    print('\n%s fixtures, %s applied'
          % (len(rows), sum(1 for row in rows if row['applied'])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixtures', nargs='*', help='fixture ids to apply')
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default='admin')
    parser.add_argument('--all', action='store_true',
                        help='apply every fixture in the catalogue')
    parser.add_argument('--reset', action='store_true',
                        help='remove every applied fixture first')
    parser.add_argument('--catalog', action='store_true',
                        help='list the catalogue and exit')
    parser.add_argument('--json', action='store_true',
                        help='print outputs as JSON (for the E2E harness)')
    args = parser.parse_args(argv)

    client = Client(args.url, args.db, args.user, args.password)
    enable_uat_mode(client)

    if args.catalog:
        print_catalog(client)
        return 0

    if args.reset:
        removed = client.execute('aic.hrm.uat.fixture', 'reset_all')
        print('reset: %s fixtures, %s records removed'
              % (len(removed['fixtures']), removed['records_removed']))

    if args.all:
        outputs = client.execute('aic.hrm.uat.fixture', 'apply_all')
    elif args.fixtures:
        outputs = client.execute('aic.hrm.uat.fixture', 'apply_fixtures',
                                 args.fixtures)
    else:
        if not args.reset:
            parser.error('name at least one fixture, or pass --all/--reset')
        return 0

    if args.json:
        print(json.dumps(outputs, indent=2, sort_keys=True))
    else:
        for fid in sorted(outputs):
            print('applied: %s' % fid)
        print('\n%s fixtures in place' % len(outputs))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except OdooRpcError as error:
        print('RPC error: %s' % error, file=sys.stderr)
        sys.exit(2)
