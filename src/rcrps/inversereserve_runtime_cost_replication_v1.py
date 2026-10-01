"""Prospective runtime-cost replication for frozen InverseReserve policies.

The execution semantics and outcome analysis are loaded into an isolated copy
of the sealed strong-control design.  This prevents the fresh seed/protocol
constants below from mutating the predecessor module in a shared test process.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
_BASE_PATH = Path(__file__).with_name(
    "inversereserve_strong_control_successor_v1.py"
)
_BASE_SPEC = importlib.util.spec_from_file_location(
    "rcrps._runtime_cost_replication_strong_control_base",
    _BASE_PATH,
)
assert _BASE_SPEC is not None and _BASE_SPEC.loader is not None
_base = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_base)

_LATENCY_PATH = ROOT / "scripts/analyze_inversereserve_strong_control_latency_v1.py"
_LATENCY_SPEC = importlib.util.spec_from_file_location(
    "_runtime_cost_replication_latency_analysis",
    _LATENCY_PATH,
)
assert _LATENCY_SPEC is not None and _LATENCY_SPEC.loader is not None
_latency = importlib.util.module_from_spec(_LATENCY_SPEC)
_LATENCY_SPEC.loader.exec_module(_latency)


CANDIDATE = "InverseReserve-runtime-cost-replication-v1"
STATUS = "reviewer_driven_runtime_cost_frozen_before_any_36301_through_36320_reset"
SEEDS = tuple(range(36301, 36321))
BOOTSTRAP_SAMPLES = 100_000
BOOTSTRAP_SEED = 270_733
PREREGISTRATION = {
    "path": (
        "paper/aaai27/notes/"
        "2026-07-23_inversereserve_runtime_cost_replication_v1_preregistration.md"
    ),
    "sha256": (
        "96a88ed66c886fa9c37735df9aeb196f8ab9e08fcefb4120ebb35953df4d6f6c"
    ),
}
PURPOSE = {
    "claim_status": "prospective_reviewer_driven_runtime_cost_replication",
    "confirmation_status": "not_independent_method_confirmation",
    "method_status": "unchanged frozen InverseReserve policies",
    "question": (
        "whether persistent stack-wide admission and one-top cleanup differ "
        "in full-grid system cost on disjoint fresh seeds"
    ),
    "selection_disclosure": (
        "system-cost endpoint selected after three blank-context PDF-only reviews"
    ),
    "outcome_based_exclusion_allowed": False,
}
PRIMARY_ANALYSIS = {
    **_base.PRIMARY_ANALYSIS,
    "registered_system_cost": {
        "comparison": [_base.FULL_METHOD, _base.TOP_CONTROL],
        "population": "all_360_matched_task_horizon_seed_cells",
        "endpoint": "paired_wall_seconds_difference",
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "secondary_subset": "one_top_cleanup_attempts_positive",
        "report_regardless_of_direction": True,
    },
}
VALIDITY_GATES = {
    **_base.VALIDITY_GATES,
    "runtime_cost_records_complete": True,
    "runtime_primary_pairs_complete": True,
}
DECISION_RULE = {
    "on_pass": (
        "report the complete prospective runtime-cost comparison regardless "
        "of effect direction"
    ),
    "on_failure": (
        "seal every opened row, report failed validity gates, and make no "
        "positive runtime-cost claim"
    ),
}
RUNTIME_DEPLOYMENT = {
    **_base.RUNTIME_DEPLOYMENT,
    "cuda_visible_devices": "0",
}


# Configure only the isolated predecessor module loaded above.
_base.CANDIDATE = CANDIDATE
_base.STATUS = STATUS
_base.SEEDS = SEEDS
_base.BOOTSTRAP_SAMPLES = 50_000
_base.BOOTSTRAP_SEED = BOOTSTRAP_SEED
_base.PREREGISTRATION = PREREGISTRATION
_base.PURPOSE = PURPOSE
_base.PRIMARY_ANALYSIS = PRIMARY_ANALYSIS
_base.VALIDITY_GATES = VALIDITY_GATES
_base.DECISION_RULE = DECISION_RULE
_base.RUNTIME_DEPLOYMENT = RUNTIME_DEPLOYMENT

ACTION_BUDGETS = _base.ACTION_BUDGETS
ARMS = _base.ARMS
COMPLETE_CONTROL = _base.COMPLETE_CONTROL
CONTROLS = _base.CONTROLS
DRIVERS = _base.DRIVERS
FULL_METHOD = _base.FULL_METHOD
TOP_CONTROL = _base.TOP_CONTROL
BUDGET_LEVELS = _base.BUDGET_LEVELS
TASK_FAMILIES = _base.TASK_FAMILIES

task_records = _base.task_records
expected_episodes = _base.expected_episodes
build_protocol = _base.build_protocol
validate_protocol = _base.validate_protocol
episode_manifest = _base.episode_manifest
arm_order_counts = _base.arm_order_counts
summarize_rows = _base.summarize_rows


def analyze_rows(
    rows: Iterable[dict[str, Any]],
    protocol: dict[str, Any],
    *,
    all_claims_complete: bool,
) -> dict[str, Any]:
    """Run the sealed outcome analysis plus the preregistered cost analysis."""

    rows = tuple(rows)
    output = _base.analyze_rows(
        rows,
        protocol,
        all_claims_complete=all_claims_complete,
    )
    runtime_cost = _latency.analyze_rows(
        list(rows),
        bootstrap_samples=BOOTSTRAP_SAMPLES,
        bootstrap_seed=BOOTSTRAP_SEED,
    )
    runtime_cost["analysis_status"] = (
        "preregistered_reviewer_driven_system_cost_replication"
    )
    runtime_cost["interpretation_boundary"] = (
        "The all-cell wall-time comparison is the preregistered primary system "
        "endpoint; it is not an additional method-efficacy endpoint."
    )
    output["runtime_cost"] = runtime_cost
    output["checks"]["runtime_cost_records_complete"] = (
        runtime_cost["episode_count"] == expected_episodes()
        and runtime_cost["matched_cell_count"]
        == len(SEEDS) * len(TASK_FAMILIES) * len(BUDGET_LEVELS)
    )
    output["checks"]["runtime_primary_pairs_complete"] = (
        runtime_cost["stack_vs_top_all_cells"]["matched_cells"]
        == len(SEEDS) * len(TASK_FAMILIES) * len(BUDGET_LEVELS)
    )
    output["passed"] = all(output["checks"].values())
    return output


__all__ = [
    "ACTION_BUDGETS",
    "ARMS",
    "BOOTSTRAP_SAMPLES",
    "BOOTSTRAP_SEED",
    "CANDIDATE",
    "COMPLETE_CONTROL",
    "CONTROLS",
    "DECISION_RULE",
    "DRIVERS",
    "FULL_METHOD",
    "PRIMARY_ANALYSIS",
    "PREREGISTRATION",
    "PURPOSE",
    "RUNTIME_DEPLOYMENT",
    "SEEDS",
    "STATUS",
    "TOP_CONTROL",
    "VALIDITY_GATES",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "episode_manifest",
    "expected_episodes",
    "summarize_rows",
    "task_records",
    "validate_protocol",
]
