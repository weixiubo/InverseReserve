"""Fresh complete-catalog confirmation of PACT-v22 task-aware reserves."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from inversereserve.contracts.pact_goal_scope_v22 import GOAL_EQUIVALENT_PROMOTION_EVENT_V22
from inversereserve.controllers.capacity_reserve_drivers_v22 import (
    TASK_RESERVE_SINGLE_ACTIVE_V22,
    TASK_RESERVE_TOP_CLEANUP_V22,
    TaskReserveSingleActiveDriverV22,
    TaskReserveTopCleanupDriverV22,
)
from inversereserve.studies import inversereserve_task_reserve_catalog_v1 as v1
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-task-reserve-complete-catalog-v2"
STATUS = "frozen_before_any_37501_through_37520_reset_with_pact_v22_and_binding_budget_five"
FULL_METHOD = TASK_RESERVE_TOP_CLEANUP_V22
SAFE_BASELINE = TASK_RESERVE_SINGLE_ACTIVE_V22
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: TaskReserveTopCleanupDriverV22, SAFE_BASELINE: TaskReserveSingleActiveDriverV22}
SEEDS = tuple(range(37501, 37521))
MAXIMUM_GUI_ACTIONS = 5
COMMON_BUDGETS = dict(v1.COMMON_BUDGETS)
GENERATION = {
    "provider": "local_huggingface",
    "model": "Qwen/Qwen3.5-9B",
    "snapshot_manifest_sha256": "cc7e227dba021e290dc47b04192090d45f56baf3d3c190e727141d01b2235e2c",
    "enable_thinking": False,
    "do_sample": False,
    "max_new_tokens": 64,
    "response_contract": "json_decision_and_bid",
    "one_generation_per_unique_public_prompt": True,
}
RUNTIME_DEPLOYMENT = {
    "provider": "local_huggingface",
    "cuda_visible_devices": "0",
    "visible_cuda_devices": 1,
    "dtype": "bfloat16",
    "device_map": "auto",
    "gpu_max_memory": "19GiB",
    "cpu_max_memory": "24GiB",
    "local_files_only": True,
    "api_key_required": False,
    "planner_cache": "create-once SQLite keyed by model and public messages",
}
PLANNER_MODEL = {
    "model_id": "Qwen/Qwen3.5-9B",
    "model_type": "multimodal_instruction_model_used_as_text_action_chooser",
    "snapshot_manifest": {
        "path": "validation/c415_qwen35_9b_capacity_protocol.json",
        "sha256": "cc7e227dba021e290dc47b04192090d45f56baf3d3c190e727141d01b2235e2c",
    },
    "dtype": "bfloat16",
    "snapshot_files_sha256": {
        ".gitattributes": "f5448ec7bb0a52de6c6fdba5ba48fe01bf216d546515a4ef9d5053e252b55359",
        "LICENSE": "50cbab8a892c5f2993b8c7351a99182507472def3b1374558308605d99b86b32",
        "README.md": "c5f5a8c2dddab69cfbf05279235aa5fddb137939a06539c4c7637aa900fef6d0",
        "chat_template.jinja": "a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715",
        "config.json": "d0883072e01861ed0b2d47be3c16c36a8e81c224c7ffaa310c6558fb3f932b05",
        "configuration.json": "2d4464e2ead06bc9bc718c781309ad1e7baded626d66e8dcdc8b469ba185faf0",
        "merges.txt": "a9d356d7bdf1ef4949e3e748e95b8e10ad9d4e2e838eddc38a0a7b6b94d1db8d",
        "model.safetensors-00001-of-00004.safetensors": "db6f444b43d318c92f360a13a25561a6a65b10c0631b8ed305a426dbaa6c380e",
        "model.safetensors-00002-of-00004.safetensors": "31c7d7e2dd5d207840b31cc59083c8f4c4718959149e0358c0364052bb9a0330",
        "model.safetensors-00003-of-00004.safetensors": "7ec36ba3a4176a44c3c0876ad80c56a2f70c84bf008d82e9501df642f17dadec",
        "model.safetensors-00004-of-00004.safetensors": "b62b0c4cd7e44edee103ee8f4fe225f246d5e768e07bfd5f25b63a8aa1fdd0c6",
        "model.safetensors.index.json": "26d3539b516be613f39563617cb9d33b3f83d401298125be392c80cefb8f7fe5",
        "preprocessor_config.json": "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516",
        "tokenizer.json": "5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42",
        "tokenizer_config.json": "316230d6a809701f4db5ea8f8fc862bc3a6f3229c937c174e674ff3ca0a64ac8",
        "video_preprocessor_config.json": "7768af27c1fafa9cc9011c1dc20067e03f8915e03b63504550e11d5066986d13",
        "vocab.json": "ce99b4cb2983d118806ce0a8b777a35b093e2000a503ebde25853284c9dfa003",
    },
}
BOOTSTRAP_SAMPLES = v1.BOOTSTRAP_SAMPLES
BOOTSTRAP_SEED = 270737
ALPHA = 0.05
PREREGISTRATION = {
    "path": "paper/aaai27/notes/2026-07-28_inversereserve_task_reserve_catalog_v2_preregistration.md",
    "sha256": "c68ae476cc7298c8d6712bd7ec0e0299227e7b9de4a45db780e3ce0ebaf6f849",
}
COVERAGE_SURVEY = dict(v1.COVERAGE_SURVEY)
DEVELOPMENT_RECORD = {
    "path": "validation/inversereserve_task_reserve_catalog_v2_development.json",
    "sha256": "0b669693d0464307261b52e792cedaddf44ef8e2ff5c75f1d4eb9f73650cd315",
    "status": "complete_outcome_informed_development_old_seed_range_only",
    "paper_evidence_allowed": False,
}
INTERFACE_COMPLETION = {
    **v1.INTERFACE_COMPLETION,
    "rules": [
        *v1.INTERFACE_COMPLETION["rules"],
        "PACT-v22 promotes one deterministic representative only when the public goal explicitly declares a folder-or-file exact-target equivalence class",
    ],
}
CATALOG_TASKS = tuple(v1.CATALOG_TASKS)
ELIGIBLE_TASKS = CATALOG_TASKS
PRIMARY_TASKS = CATALOG_TASKS
NEW_TEMPLATE_EXACT_TASKS = tuple(v1.NEW_TEMPLATE_EXACT_TASKS)
SEEN_TEMPLATE_NEW_EXACT_TASKS = tuple(v1.SEEN_TEMPLATE_NEW_EXACT_TASKS)
PREVIOUSLY_EXERCISED_EXACT_TASKS = tuple(v1.PREVIOUSLY_EXERCISED_EXACT_TASKS)
PURPOSE = {
    "claim_status": "prospective_fresh_seed_binding_budget_task_reserve_confirmation",
    "confirmation_status": "complete_catalog_post_development_confirmation_with_modern_pinned_primary_nine_billion_parameter_planner",
    "selection_status": "complete transaction catalog, B=5, h=1, planner, and seeds 37501--37520 fixed before any reset; no task or outcome exclusion",
    "question": "whether stack-wide solvent nesting improves debt-free task completion over a task-reserve-aware depth-one control",
    "outcome_based_exclusion_allowed": False,
}
OUTCOME_DEFINITIONS = {
    **v1.OUTCOME_DEFINITIONS,
    "planner_task_reserve": "one action retained at every reversible prerequisite for the structured goal contract's future terminal call",
    "goal_equivalent_terminal_promotion_v22": "one deterministic representative of an explicitly declared public folder-or-file exact-target class is compiled as a commit",
}
PRIMARY_ANALYSIS = {
    **v1.PRIMARY_ANALYSIS,
    "name": "paired_complete_catalog_task_reserve_v22_confirmation",
    "full_method": FULL_METHOD,
    "baseline": SAFE_BASELINE,
    "population": "complete transaction-eligible MiniWoB++ catalog",
    "tasks": list(PRIMARY_TASKS),
    "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
    "planner_task_reserve": v1.TASK_RESERVE_V21,
    "bootstrap_seed": BOOTSTRAP_SEED,
    "alpha": ALPHA,
    "minimum_full_closed_successes": 150,
    "minimum_net_paired_closed_successes": 20,
}
VALIDITY_GATES = dict(v1.VALIDITY_GATES)
DECISION_RULE = {
    "on_pass": "report the complete fresh-seed PACT-v22 task-reserve comparison regardless of effect magnitude beyond the frozen gates",
    "on_failure": "seal every opened row and the complete result; make no positive v2 claim and open no replacement population",
}
PLANNER_TASK_RESERVE = dict(v1.PLANNER_TASK_RESERVE)
METHOD_REVISION = {
    "runtime": "PACT-v22-goal-equivalent-target",
    "development_population": "seeds 37401--37420 only",
    "confirmation_population": "seeds 37501--37520",
    "public_rule": GOAL_EQUIVALENT_PROMOTION_EVENT_V22,
    "ordinary_duplicate_targets_fail_closed": True,
}


def _episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = protocol["population"]["task_metadata"]
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, task in enumerate(CATALOG_TASKS):
            rotation = (seed_index + task_index) % len(ARMS)
            order = ARMS[rotation:] + ARMS[:rotation]
            for arm_position, method in enumerate(order):
                rows.append(
                    {
                        "episode_index": len(rows),
                        "seed_index": seed_index,
                        "task_index": task_index,
                        "arm_position": arm_position,
                        "task": task,
                        "family_group": metadata[task]["template_group"],
                        "population_stratum": metadata[task]["template_status"],
                        "primary_population": True,
                        "new_template_population": task in NEW_TEMPLATE_EXACT_TASKS,
                        "budget_level": "binding_b5",
                        "seed": seed,
                        "maximum_gui_actions": MAXIMUM_GUI_ACTIONS,
                        "planner_task_reserve": v1.TASK_RESERVE_V21,
                        "method": method,
                        "episode_id": f"{task}__seed{seed}__b{MAXIMUM_GUI_ACTIONS}__h{v1.TASK_RESERVE_V21}__{method}",
                    }
                )
    if len(rows) != expected_episodes() or len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("task-reserve v2 manifest changed")
    return rows


def expected_episodes() -> int:
    return len(ARMS) * len(SEEDS) * len(CATALOG_TASKS)


def _v1_patch() -> dict[str, Any]:
    return {
        "CANDIDATE": CANDIDATE,
        "STATUS": STATUS,
        "FULL_METHOD": FULL_METHOD,
        "SAFE_BASELINE": SAFE_BASELINE,
        "ARMS": ARMS,
        "DRIVERS": DRIVERS,
        "SEEDS": SEEDS,
        "MAXIMUM_GUI_ACTIONS": MAXIMUM_GUI_ACTIONS,
        "COMMON_BUDGETS": COMMON_BUDGETS,
        "GENERATION": GENERATION,
        "RUNTIME_DEPLOYMENT": RUNTIME_DEPLOYMENT,
        "PLANNER_MODEL": PLANNER_MODEL,
        "BOOTSTRAP_SAMPLES": BOOTSTRAP_SAMPLES,
        "BOOTSTRAP_SEED": BOOTSTRAP_SEED,
        "ALPHA": ALPHA,
        "PREREGISTRATION": PREREGISTRATION,
        "COVERAGE_SURVEY": COVERAGE_SURVEY,
        "DEVELOPMENT_RECORD": DEVELOPMENT_RECORD,
        "INTERFACE_COMPLETION": INTERFACE_COMPLETION,
        "CATALOG_TASKS": CATALOG_TASKS,
        "ELIGIBLE_TASKS": ELIGIBLE_TASKS,
        "PRIMARY_TASKS": PRIMARY_TASKS,
        "NEW_TEMPLATE_EXACT_TASKS": NEW_TEMPLATE_EXACT_TASKS,
        "SEEN_TEMPLATE_NEW_EXACT_TASKS": SEEN_TEMPLATE_NEW_EXACT_TASKS,
        "PREVIOUSLY_EXERCISED_EXACT_TASKS": PREVIOUSLY_EXERCISED_EXACT_TASKS,
        "PURPOSE": PURPOSE,
        "OUTCOME_DEFINITIONS": OUTCOME_DEFINITIONS,
        "PRIMARY_ANALYSIS": PRIMARY_ANALYSIS,
        "VALIDITY_GATES": VALIDITY_GATES,
        "DECISION_RULE": DECISION_RULE,
        "PLANNER_TASK_RESERVE": PLANNER_TASK_RESERVE,
        "expected_episodes": expected_episodes,
        "_episode_manifest": _episode_manifest,
    }


@contextmanager
def _configured_v1() -> Iterator[None]:
    patch = _v1_patch()
    previous = {name: getattr(v1, name) for name in patch}
    for name, value in patch.items():
        setattr(v1, name, value)
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(v1, name, value)


def derive_population(survey: dict[str, Any]) -> dict[str, Any]:
    return v1.derive_population(survey)


def validate_population(population: dict[str, Any]) -> None:
    v1.validate_population(population)


def task_records(population: dict[str, Any]) -> list[dict[str, Any]]:
    with _configured_v1():
        return v1.task_records(population)


def build_protocol(**kwargs: Any) -> dict[str, Any]:
    with _configured_v1():
        protocol = v1.build_protocol(**kwargs)
    protocol["method_revision"] = dict(METHOD_REVISION)
    protocol["planner_runtime"] = {
        "model": GENERATION["model"],
        "snapshot_manifest_sha256": GENERATION["snapshot_manifest_sha256"],
        "enable_thinking": GENERATION["enable_thinking"],
        "do_sample": GENERATION["do_sample"],
        "max_new_tokens": GENERATION["max_new_tokens"],
        "response_contract": GENERATION["response_contract"],
        "api_key_required": False,
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    with _configured_v1():
        v1.validate_protocol(protocol)
    require(not protocol.get("method_revision") != METHOD_REVISION, "task-reserve v2 method revision changed")
    require(
        not protocol.get("planner_runtime")
        != {
            "model": GENERATION["model"],
            "snapshot_manifest_sha256": GENERATION["snapshot_manifest_sha256"],
            "enable_thinking": GENERATION["enable_thinking"],
            "do_sample": GENERATION["do_sample"],
            "max_new_tokens": GENERATION["max_new_tokens"],
            "response_contract": GENERATION["response_contract"],
            "api_key_required": False,
        },
        "task-reserve v2 planner runtime changed",
    )
    require(
        not protocol.get("expected_episodes") != expected_episodes(), "task-reserve v2 episode count changed"
    )


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    return _episode_manifest(protocol)


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    with _configured_v1():
        return v1.arm_order_counts(protocol)


def summarize_rows(rows: Any) -> dict[str, Any]:
    with _configured_v1():
        return v1.summarize_rows(rows)


def analyze_rows(rows: Any, protocol: dict[str, Any], *, all_claims_complete: bool) -> dict[str, Any]:
    materialized = tuple(rows)
    with _configured_v1():
        analysis = v1.analyze_rows(materialized, protocol, all_claims_complete=all_claims_complete)
    analysis["goal_equivalent_terminal_promotions_v22"] = sum(
        (
            event.get("promotion_rule") == GOAL_EQUIVALENT_PROMOTION_EVENT_V22
            for row in materialized
            for event in row.get("trace", ())
        )
    )
    return analysis


__all__ = [
    "ALPHA",
    "ARMS",
    "BOOTSTRAP_SAMPLES",
    "BOOTSTRAP_SEED",
    "CANDIDATE",
    "CATALOG_TASKS",
    "COMMON_BUDGETS",
    "COVERAGE_SURVEY",
    "DECISION_RULE",
    "DEVELOPMENT_RECORD",
    "DRIVERS",
    "ELIGIBLE_TASKS",
    "FULL_METHOD",
    "GENERATION",
    "INTERFACE_COMPLETION",
    "MAXIMUM_GUI_ACTIONS",
    "METHOD_REVISION",
    "PLANNER_MODEL",
    "PLANNER_TASK_RESERVE",
    "PRIMARY_ANALYSIS",
    "PRIMARY_TASKS",
    "PREREGISTRATION",
    "PURPOSE",
    "RUNTIME_DEPLOYMENT",
    "SAFE_BASELINE",
    "SEEDS",
    "STATUS",
    "VALIDITY_GATES",
    "analyze_rows",
    "arm_order_counts",
    "build_protocol",
    "derive_population",
    "episode_manifest",
    "expected_episodes",
    "summarize_rows",
    "task_records",
    "validate_population",
    "validate_protocol",
]
