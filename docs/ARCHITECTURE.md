# Architecture and study interfaces

`api.run_episode` accepts an `Environment` protocol, an initial public
observation, a planner callback, budgets and a named method. Application
modules `settings`, `execution`, `artifacts` and `cli` resolve resources,
execute the selected backend and persist results.

| Component | Responsibility |
| --- | --- |
| `core` | Transaction and effect ledgers, sequence state and capacity arithmetic |
| `contracts` | Grounding, typed actions, postconditions and goal binding |
| `controllers` | Admission, forward execution, compensating repair, LIFO restoration and commit |
| `observations` | Semantic types, browser parsing, screenshot/OCR evidence and candidate scope |
| `preview` | Search requests, query accounting, axis discovery and rank-two refinement |
| `models` | Prompt records, bounded structured parsing and local planner interfaces |
| `adapters/webarena` | Public surface/navigation evidence and browser adapters |
| `studies/designs` | Outcome-independent populations, protocols and episode grids |
| `studies` | Analysis and decision criteria for individually identified studies |

## Controller families

`full`, `raw` and `typed` resolve to the matched confirmation controllers
and controls, internally identified as v13. The original confirmation uses
six task families, 20 seeds, three arms and Qwen3.5-9B.

`stack-reserve`, `single-active` and `top-cleanup` share the v20 compiler and
runtime. `task-reserve-single` and `task-reserve-cleanup` use the v22 policies
for goal-equivalent task reservations. These studies retain distinct questions,
budgets and protocol criteria. The API records the selected controller identity.

## State and execution

`preview.types` defines search state. Each coordinate consumes at most one
query even when the candidate pool contains duplicates. Controller phases
separate public evidence, admission, reserve accounting, execution, effect
certification and recovery through explicit state records.

WebArena form reveal uses `FormRevealContext`. Mutation certificates share
payload checks and effect finalization while preserving their distinct failure
semantics. `MODULE_LAYOUT.json` and `RESPONSIBILITY_BOUNDARIES.json` describe
ownership. `STRUCTURE_EXCEPTIONS.json` identifies reviewed declaration tables.
Scientific reproduction uses independently identified original source.
