# Odoo 18 backport notes

The 19.0 tree is the single source of truth. `python tools/backport_18.py`
produces `build/18.0/` — the Odoo 18 build — by applying the verified API
deltas below. Run it (plus the 18 smoke) after every phase, and whenever a new
19-only API sneaks in.

## Verified deltas (probed against both source trees, 2026-08-02)

| # | Odoo 19 | Odoo 18 | Transform |
|---|---------|---------|-----------|
| 1 | manifest `'version': '19.0.x.y.z'` | `'18.0.x.y.z'` | string replace |
| 2 | `models.Constraint(...)` class attrs | `_sql_constraints` list | regex rewrite |
| 3 | `res.groups.privilege` record + `privilege_id` | `category_id` on the group | drop record, swap field |
| 4 | `res.users.group_ids` | `groups_id` | fixture string replace |
| 5 | `res.groups.sequence` field | absent | strip from group records |
| 6 | `res.groups.user_ids` | `users` | field-name swap |
| 7 | `@web_tour/tour_utils` | `@web_tour/tour_service/tour_utils` | JS import swap |

## Confirmed IDENTICAL in both versions (no transform)

`_has_cycle()`, `_check_recursion`, `<chatter/>`, `<list>` views,
`invisible="expr"` syntax, `aggregator=` on fields, `_read_group` tuple API,
`Many2oneReference`, `mail.thread`/activity mixins, search-view group syntax.

## Smoke command

```powershell
python tools\backport_18.py
python C:\AIConnect\Odoo18_runtime\odoo-bin -d AIC_HRM_Pro_18 `
  --db_host=127.0.0.1 --db_port=5433 --db_user=odoo --db_password=odoo `
  --addons-path="C:\AIConnect\Odoo18_runtime\addons,C:\AIConnect\AIC_HRM_Pro\build\18.0" `
  -i aic_hrm_base,aic_okr_kpi --test-enable --test-tags aic_hrm_base,aic_okr_kpi `
  --stop-after-init --log-level warn
```

Status 2026-08-02: full CP1+CP2 test suite green on BOTH 19 (native) and 18
(transformed build), exit 0.

## Release flow (5B)

Branch `18.0` of the repo is populated from `build/18.0/` at phase ends
(after CP7, after CP9); Apps Store gets both channels.
