"""Outcome-independent study design and episode population; analysis remains in the parent study module."""

from __future__ import annotations

from collections import Counter
from typing import Any

from inversereserve.controllers.capacity_reserve_drivers_v18 import STACK_WIDE_V18, StackWideCapacityDriverV18
from inversereserve.controllers.single_obligation_capacity_driver_v1 import (
    SINGLE_ACTIVE_OBLIGATION_V1,
    SingleActiveObligationDriverV1,
)
from inversereserve.studies import inversereserve_budget_frontier_holdout_v2 as frontier
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-model-family-replication-v1"
STATUS = "sealed_before_any_model_family_seed_reset"
FULL_METHOD = STACK_WIDE_V18
SAFE_BASELINE = SINGLE_ACTIVE_OBLIGATION_V1
ARMS = (FULL_METHOD, SAFE_BASELINE)
DRIVERS = {FULL_METHOD: StackWideCapacityDriverV18, SAFE_BASELINE: SingleActiveObligationDriverV1}
SEEDS = tuple(range(34001, 34021))
BUDGET_LEVELS = tuple(frontier.BUDGET_LEVELS)
TASK_BUDGETS = {task: dict(levels) for task, levels in frontier.TASK_BUDGETS.items()}
TASK_FAMILIES = dict(frontier.TASK_FAMILIES)
COMMON_BUDGETS = dict(frontier.COMMON_BUDGETS)
GENERATION = dict(frontier.GENERATION)
RUNTIME_DEPLOYMENT = {
    "model_weights_and_dtype_unchanged": True,
    "visible_cuda_devices": 1,
    "cuda_visible_devices": "0",
    "device_map": "auto",
    "model_loader": "AutoModelForCausalLM",
    "torch": "2.7.1+cu126",
    "transformers": "5.9.0",
}
PLANNER_MODEL = {
    "model_id": "HuggingFaceTB/SmolLM3-3B",
    "model_revision": "a07cc9a04f16550a088caea529712d1d335b0ac1",
    "model_type": "smollm3",
    "architecture": "SmolLM3ForCausalLM",
    "dtype": "bfloat16",
    "snapshot_files_sha256": {
        "chat_template.jinja": "3e0e275a527f249670056e0078e474eadbdd007c134b4fdfae5a7b3089702814",
        "config.json": "c72b1031274ff4626e434d0019e88e95a767460135db9ee492eb80652b786af1",
        "generation_config.json": "3458d62b3f9654f4bbe285223b0f4e5a1e67cae61c92bb6aeaadf04468bf9e01",
        "model-00001-of-00002.safetensors": "e5eed4113a925264c33e3cdf76cd9f547c06a207ef2270914a7274a2bf685ffd",
        "model-00002-of-00002.safetensors": "6c3ad90646457295723e4da5ee8afac47006e20407b122df5174693dd8d68a43",
        "model.safetensors.index.json": "e3a7254c086c4a78f95ad5864f435d165ffed1ed8998326ce5107b4423c15b76",
        "special_tokens_map.json": "12403efb970f069ba62ddf3b66166a27254be4a198166b61ad1ee604bd3a4515",
        "tokenizer.json": "7b6a500b662a34eb3f0374db856ba4ad7de4c81040571d78dc0d357238930005",
        "tokenizer_config.json": "59a64b39f05ee0acf7479bbccf99a44d9e481c1a4a494eb03838ae3c35eb29be",
    },
}
SEQUENCE_FAMILY_SIZE = 13
OUTCOME_DEFINITIONS = {
    "official_task_success": "environment-provided binary task success",
    "physical_stranding": "task failure with at least one active typed obligation at episode stop",
    "verified_restoration": "at least one ordinary or interrupt-clearance restoration attempt, all attempts verified, and no active typed obligation at episode stop",
    "runtime_halt": "runtime_halted is true in the sealed episode metrics",
    "single_obligation_policy": "the comparator may execute serial multi-step work but rejects a new transact proposal whenever one typed obligation remains active",
    "closed_success": "official task success with an empty active stack",
    "reporting_rule": "use closed success as the primary utility endpoint; report official success, failed-stop stranding, runtime halt, restoration, work, and successful-stop active obligations separately",
}
PRIMARY_COMPARISON = {
    "name": "model_family_stack_wide_against_one_active_safe_control",
    "safety": "failed-stop physical stranding and runtime halt, separately",
    "utility": "official binary task success with an empty active stack",
    "effort": "typed transactions and GUI actions",
    "inferential_unit": "fresh-seed cluster across all twelve task-budget cells",
    "comparison": "stack-wide InverseReserve versus an identical stack-wide runtime that allows at most one unresolved transaction",
    "multiplicity": "one-sided exact seed-cluster sign test with a thirteen-look Bonferroni upper bound covering the retained adaptive sequence",
}
CONFIRMATION_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "all_rows_respect_hard_budgets": True,
    "stack_has_zero_physical_stranding": True,
    "stack_has_zero_runtime_halts": True,
    "stack_restorations_all_pass": True,
    "single_obligation_has_zero_physical_stranding": True,
    "single_obligation_has_zero_runtime_halts": True,
    "single_obligation_restorations_all_pass": True,
    "single_obligation_policy_holds": True,
    "single_obligation_policy_binds_live": True,
    "single_obligation_successes_close_all_obligations": True,
    "minimum_single_obligation_closed_successes": 40,
    "minimum_single_obligation_success_families": 2,
    "minimum_stack_closed_success_advantage_over_single_obligation": 20,
    "maximum_thirteenth_look_adjusted_sign_pvalue": 0.05,
}
DECISION_RULE = {
    "on_pass": "report the complete SmolLM3-3B replication as different-family evidence for the utility comparison against the one-active safe control",
    "on_failure": "seal all rows, report the failed gates without exclusions, and make no positive model-family replication claim",
}
SELECTION_DISCLOSURE = {
    "selected_after_six_blank_context_reviews": True,
    "planner_selected_to_test_model_family_transfer": True,
    "same_task_budget_grid_as_qwen35_9b_comparison": True,
    "qwen35_9b_result_was_known_before_selection": True,
    "qwen35_2b_result_was_known_before_selection": True,
    "replication_is_not_independent_method_confirmation": True,
    "fresh_seeds_selected_before_any_reset": True,
    "old_episode_reuse_allowed": False,
}


def task_records() -> list[dict[str, Any]]:
    return [
        {"task_id": task, "family_group": TASK_FAMILIES[task], "budget_levels": dict(levels)}
        for task, levels in TASK_BUDGETS.items()
    ]


def expected_episodes() -> int:
    cells = sum((len(levels) for levels in TASK_BUDGETS.values()))
    return len(ARMS) * len(SEEDS) * cells


def build_protocol(
    *,
    scientific_source_commit: str,
    source_sha256: dict[str, str],
    preregistration_path: str,
    preregistration_sha256: str,
    predecessor: dict[str, Any],
    repositories: dict[str, str],
    created_utc: str,
) -> dict[str, Any]:
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "scientific_source_commit": scientific_source_commit,
        "predecessor": predecessor,
        "sequence_family_size": SEQUENCE_FAMILY_SIZE,
        "adaptive_history_disclosed": True,
        "arms": list(ARMS),
        "isolated_policy_difference": "both arms use the same stack-wide inverse reserve; the comparator alone rejects a second simultaneous active transaction",
        "tasks": task_records(),
        "fresh_seeds": list(SEEDS),
        "budget_levels": list(BUDGET_LEVELS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "runtime_deployment": dict(RUNTIME_DEPLOYMENT),
        "planner_model": {
            **PLANNER_MODEL,
            "snapshot_files_sha256": dict(PLANNER_MODEL["snapshot_files_sha256"]),
        },
        "expected_episodes": expected_episodes(),
        "outcome_definitions": dict(OUTCOME_DEFINITIONS),
        "primary_comparison": dict(PRIMARY_COMPARISON),
        "confirmation_gates": dict(CONFIRMATION_GATES),
        "decision_rule": dict(DECISION_RULE),
        "selection_disclosure": dict(SELECTION_DISCLOSURE),
        "repositories": dict(repositories),
        "source_sha256": dict(sorted(source_sha256.items())),
        "preregistration": {"path": preregistration_path, "sha256": preregistration_sha256},
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "episode_replay_allowed": False,
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected model-family replication identity",
    )
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "model-family replication arms changed",
    )
    require(not protocol.get("tasks") != task_records(), "model-family task grid changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "model-family replication seeds changed")
    require(
        not tuple(protocol.get("budget_levels", ())) != BUDGET_LEVELS, "model-family budget levels changed"
    )
    require(not protocol.get("common_budgets") != COMMON_BUDGETS, "model-family common budgets changed")
    require(not protocol.get("generation") != GENERATION, "model-family generation changed")
    require(not protocol.get("runtime_deployment") != RUNTIME_DEPLOYMENT, "model-family deployment changed")
    require(not protocol.get("planner_model") != PLANNER_MODEL, "model-family model identity changed")
    require(
        not protocol.get("expected_episodes") != expected_episodes(), "model-family episode count changed"
    )
    require(not protocol.get("outcome_definitions") != OUTCOME_DEFINITIONS, "model-family outcomes changed")
    require(
        not protocol.get("primary_comparison") != PRIMARY_COMPARISON,
        "model-family primary comparison changed",
    )
    require(not protocol.get("confirmation_gates") != CONFIRMATION_GATES, "model-family gates changed")
    require(not protocol.get("decision_rule") != DECISION_RULE, "model-family decision rule changed")
    require(
        not protocol.get("selection_disclosure") != SELECTION_DISCLOSURE,
        "model-family selection disclosure changed",
    )
    require(
        not protocol.get("sequence_family_size") != SEQUENCE_FAMILY_SIZE,
        "model-family multiplicity family changed",
    )
    require(
        not protocol.get("adaptive_history_disclosed") is not True,
        "model-family adaptive history disclosure changed",
    )
    for key in ("predecessor", "repositories", "source_sha256", "preregistration"):
        if not isinstance(protocol.get(key), dict):
            raise ValueError(f"model-family {key} binding is absent")
    for key in ("outcome_based_exclusion_allowed", "partial_reexecution_allowed", "episode_replay_allowed"):
        if protocol.get(key) is not False:
            raise ValueError(f"model-family {key} changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, (task, levels) in enumerate(TASK_BUDGETS.items()):
            for level_index, (level, budget) in enumerate(levels.items()):
                rotation = (seed_index + task_index + level_index) % len(ARMS)
                order = ARMS[rotation:] + ARMS[:rotation]
                for arm_position, method in enumerate(order):
                    rows.append(
                        {
                            "episode_index": len(rows),
                            "seed_index": seed_index,
                            "task_index": task_index,
                            "budget_level_index": level_index,
                            "arm_position": arm_position,
                            "task": task,
                            "family_group": TASK_FAMILIES[task],
                            "budget_level": level,
                            "seed": seed,
                            "maximum_gui_actions": budget,
                            "method": method,
                            "episode_id": f"{task}__seed{seed}__{level}{budget}__{method}",
                        }
                    )
    if len(rows) != expected_episodes():
        raise ValueError("model-family manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("model-family manifest is duplicated")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}
