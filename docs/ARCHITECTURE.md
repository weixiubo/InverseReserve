# Architecture and supported research scope

`api.run_episode` is the stable boundary: an Environment protocol, public initial
observation, Planner callback, Budgets value and named method. It performs no
resource discovery or filesystem writes. `settings`, `execution`, `artifacts` and
`cli` resolve inputs, run an explicit backend and publish immutable results.

| Owner | Responsibility |
|---|---|
| core | transaction/effect ledgers, sequence state and capacity arithmetic |
| contracts | grounding, typed actions, postconditions and goal binding |
| controllers | admission, forward execution, compensating repair, LIFO restoration and commit |
| observations | immutable semantic types, browser observation parsing, screenshot/OCR evidence and candidate scope |
| preview | quotient/local-search requests, query accounting, axis discovery and rank-two refinement |
| models | prompt records, bounded structured parsing and local planner interface |
| adapters/webarena | explicit public surface/navigation evidence and scoped browser adapters |
| studies/designs | outcome-independent populations, protocol declarations and episode grids |
| studies | retained analysis and claim gates for individually identified research studies |

Primary matched scope: `full`, `raw`, `typed` resolve to the final confirmation
controller/controls (internally v13). The original final protocol is six families,
20 seeds, three arms and Qwen3.5-9B. Current CLI runs do not recreate a sealed final
protocol or issue primary-evidence claims.

Capacity scope: `stack-reserve`, `single-active`, `top-cleanup` share the v20
compiler/runtime; goal-equivalent task-reserve scope uses the two v22 policies.
Their experimental questions and budget/protocol gates differ from the final
matched study. The API records the actual internal controller identity. Necessary
predecessor modules remain because these concrete controllers and research tests
depend on them, not as alternative user-facing launch commands.

Search state is explicit in `preview.types`; coordinate attempts are accounted for
once even if a supplied candidate pool contains duplicate coordinates. Controller
phases separate public evidence, envelope admission, reserve accounting, execution,
freshness/effect certification and recovery. State records are passed explicitly.
WebArena form reveal uses FormRevealContext; mutation certificates share payload
checks and effect finalization while retaining their distinct failure semantics.

See MODULE_LAYOUT.json and RESPONSIBILITY_BOUNDARIES.json for ownership mappings.
STRUCTURE_EXCEPTIONS.json records individually reviewed declaration tables; ordinary
runtime functions still follow the 120-line/15-complexity target. Frozen code is
kept outside the maintained package source and is verified by original hashes.
