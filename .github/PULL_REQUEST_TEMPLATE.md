I want to merge this change because...

<!-- Please mention all relevant issue numbers. -->

# Impact

- [ ] New migrations
- [ ] New/Updated API fields or mutations
- [ ] Deprecated API fields or mutations
- [ ] Removed API types, fields, or mutations

- [ ] Link to documentation:

# Pull Request Checklist

<!-- Please keep this section. It will make the maintainer's life easier. -->

- [ ] Privileged queries and mutations are either absent or guarded by proper permission checks
- [ ] Database queries are optimized and the number of queries is constant
- [ ] Database migrations are either absent or optimized for zero downtime
- [ ] The changes are covered by test cases
- [ ] All new fields/inputs/mutations have proper labels added (`ADDED_IN_X`, `PREVIEW_FEATURE`, etc.)
- [ ] All migrations have proper dependencies
- [ ] All indexes are added concurrently in migrations
- [ ] All RunSql and RunPython migrations have revert option defined
