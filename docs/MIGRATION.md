# Non-destructive salary-cycle migration

## What changes

Migration 0003 preserves the existing expense_salary table, IDs, amounts, descriptions, and timestamps. It renames the Django model to SalaryCycle and adds nullable user ownership, is_current, an optional expense cycle relationship, and category. Existing categories are derived deterministically; original descriptions are unchanged.

All old salaries remain unassigned and non-current, and all old expenses remain unassigned. This is deliberate: neither ownership nor cycle membership can be proven from the old schema. The local inspected database had 4 salaries, 11 expenses, and no accounts; inspect the deployed database separately.

Constraints allow unassigned legacy records to survive even if their old amounts were invalid. New owned salaries and assigned expenses must be positive, and only one current cycle per user is allowed.

## Rollout procedure

1. Enter maintenance mode before changing the schema or assigning ownership. Stop the old application so its unrestricted endpoints cannot remain reachable during cutover.
2. Back up the database using the database engine's supported backup mechanism. For SQLite, use its backup API or copy only while all writers are stopped; account for journal/WAL files. For PostgreSQL, use pg_dump and the established backup procedure.
3. Verify restoration into a separate disposable database. Record row counts and monetary totals for reconciliation.
4. Run migrations against that restored copy, not the live database. Confirm all original IDs, values, dates, and record counts remain.
5. Create or identify the correct Django users. Prepare an explicit mapping from salary IDs to owners and from expense IDs to salary cycles. Do not infer this automatically from dates or assign it to the first registered account.
6. Run the mapping command in dry-run mode on the copy; review every assignment and resolve rejected records.
7. After database-change and ownership-mapping approval, apply the additive migration and the reviewed mapping during maintenance mode. Verify counts and totals again before bringing the new backend and frontend online.
8. Retain the original backup according to your retention policy.

No real database migrations or reconciliation are executed by the implementation work. Test migrations use disposable databases. The separate browser-test database is not production data.

## Explicit mapping

Example shape only; replace every ID with reviewed values:

```json
{
  "cycles": [
    {"id": 1, "user_id": 7, "is_current": false},
    {"id": 2, "user_id": 7, "is_current": true}
  ],
  "expenses": [
    {"id": 1, "cycle_id": 1},
    {"id": 2, "cycle_id": 2}
  ]
}
```

Dry-run:

```text
python manage.py reconcile_legacy reviewed-mapping.json
```

Only after review and backup:

```text
python manage.py reconcile_legacy reviewed-mapping.json --apply
```

The dry-run executes validation inside a transaction and rolls all mapping changes back. Apply is atomic too. It rejects missing/duplicate IDs, already-assigned records, non-positive amounts, overspent cycles, invalid owners, multiple current cycles, and a current cycle that is not the newest owned cycle. Expense mappings must refer to salaries included in the mapping.

If real records cannot satisfy the cycle rules, keep them unassigned and resolve them explicitly. Do not fabricate salary, silently drop expenses, change historical amounts, or force an invalid mapping. The command reports how many records remain unassigned.

A partial mapping is allowed if the mapped users/cycles satisfy all invariants. Keep the application in maintenance mode while applying the command, because this operator workflow is not an online financial API.

## Final constraint tightening

Nullable relationships are a transitional accommodation, not permission for APIs to create unowned records. Once every legacy record is reconciled, a later reviewed migration can make user and cycle non-nullable. Do not add that migration until unassigned counts are zero on the target database.

## Rollback

Reversing the new schema after users have created cycle data would lose ownership/category relationships even if salary and expense rows survive. Do not casually migrate backwards. Keep the application in maintenance mode, preserve a backup of the changed database, and use the verified restoration/forward-fix procedure appropriate to the rollout.
