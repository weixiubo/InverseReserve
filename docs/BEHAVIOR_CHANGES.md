# Search behavior changes

## Duplicate coordinates

Local preview search records skipped duplicate indices in `excluded_pool`
and excludes them from subsequent posterior selection. This ensures
termination after the distinct candidate coordinates have been exhausted.
Skipping a duplicate neither records a negative observation nor consumes
another query.

The original scheduler could repeatedly select an index whose rounded
coordinate had already been evaluated through another entry or refinement.
A bounded regression test covers that case and verifies one observation per
unique coordinate. Twenty ordinary-input comparisons preserve the original
search behavior. The original scientific source remains identified separately
for evidence reproduction.
