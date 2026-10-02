# Behavior corrections during structural refactoring

## Repeated pool coordinates in ordinary preview search

The original generate_query_order can repeatedly schedule an index whose rounded
coordinate was already queried through another pool entry or a refinement. Its
execute function skips the duplicate without recording that pool index, so the
posterior can choose it forever after useful candidates are exhausted.

LocalSearch records such skipped indices in excluded_pool and omits them from
future posterior candidates. It does not invent a negative observation or spend
another query. A bounded scheduler regression test verifies termination and that
each unique coordinate is observed once. Twenty normal-input comparisons use the
original frozen implementation; duplicate-case termination is an intentional fix
and is not reported as identical to the nonterminating original. Historical
scientific code and evidence are unchanged.
