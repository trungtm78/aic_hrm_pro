# -*- coding: utf-8 -*-
"""Generate the enterprise-scale lot and measure it against the budget.

    python tools/seed_uat_scale.py                 # 2,000 employees
    python tools/seed_uat_scale.py --employees 500 # a quicker rehearsal

The budgets come from CLAUDE.md and are printed as PASS/OVER next to the
measurement, because "the dashboard felt fine" is not a result.
"""
import argparse
import os
import sys

# Run from anywhere: seed_uat.py lives next to this file and owns the RPC
# client, so both tools speak to the server exactly the same way.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from seed_uat import Client, DEFAULT_DB, DEFAULT_URL, OdooRpcError, \
    enable_uat_mode

# name -> (label, seconds allowed)
BUDGETS = {
    'close_cycle': ('Close a cycle', 60.0),
    'dashboard_group': ('Dashboard grouping query', 3.0),
    'score_rollup': ('Score roll-up over every scorecard', 60.0),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--user', default='admin')
    parser.add_argument('--password', default='admin')
    parser.add_argument('--employees', type=int, default=2000)
    parser.add_argument('--departments', type=int, default=40)
    parser.add_argument('--kpis', type=int, default=40)
    parser.add_argument('--results-sample', type=float, default=0.1)
    args = parser.parse_args(argv)

    client = Client(args.url, args.db, args.user, args.password)
    enable_uat_mode(client)

    print('Seeding %s employees x %s KPIs ...'
          % (args.employees, args.kpis))
    seeded = client.execute(
        'aic.hrm.uat.fixture', 'seed_scale',
        employees=args.employees, departments=args.departments,
        kpis=args.kpis, results_sample=args.results_sample)

    print('\nCounts')
    for name, value in sorted(seeded['counts'].items()):
        print('  %-18s %s' % (name, value))
    print('\nSeeding time (seconds)')
    for name, value in seeded['timings'].items():
        print('  %-18s %s' % (name, value))

    print('\nBudgets')
    measured = client.execute('aic.hrm.uat.fixture', 'measure_budgets',
                              seeded['cycle_id'])
    over = 0
    for name, seconds in sorted(measured.items()):
        label, budget = BUDGETS.get(name, (name, None))
        if budget is None:
            print('  %-34s %6.2fs' % (label, seconds))
            continue
        verdict = 'PASS' if seconds <= budget else 'OVER'
        over += verdict == 'OVER'
        print('  %-34s %6.2fs  budget %5.1fs  %s'
              % (label, seconds, budget, verdict))
    print('\n%s budget(s) exceeded' % over)
    return 1 if over else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except OdooRpcError as error:
        print('RPC error: %s' % error, file=sys.stderr)
        sys.exit(2)
