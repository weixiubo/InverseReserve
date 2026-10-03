"""Outcome-independent study design and episode population; analysis remains in the parent study module."""

from __future__ import annotations

from collections import Counter
from typing import Any

from inversereserve.controllers.confirmation_agents_v15 import FullPactConfirmationDriverV15
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-cross-family-stress-v1"
STATUS = "sealed_before_any_cross_family_episode_reset"
FULL_METHOD = "stack_wide_reserve_v15"
LOCAL_ABLATION = "proposal_local_reserve_v15"
ABSTAIN_BASELINE = "always_abstain"
ARMS = (FULL_METHOD, LOCAL_ABLATION, ABSTAIN_BASELINE)
SEEDS = tuple(range(29301, 29321))
TASK_BUDGETS = {
    "use-autocomplete-nodelay": (2, 3, 4),
    "login-user-popup": (3, 4, 5),
    "book-flight-nodelay": (5, 7, 9, 11),
}
TASK_FAMILIES = {
    "use-autocomplete-nodelay": "autocomplete",
    "login-user-popup": "login_interrupt",
    "book-flight-nodelay": "flight_composite",
}
COMMON_BUDGETS = {"maximum_planner_calls": 3, "maximum_wall_seconds": 60.0}
GENERATION = {"enable_thinking": False, "do_sample": False, "max_new_tokens": 64}
PRIMARY_OUTCOME = {
    "name": "activity_constrained_success_or_recovered_stop",
    "success_case": "official task success after at least one GUI action and one typed transaction",
    "non_success_case": "at least one GUI action, typed transaction, and attempted restoration; zero active obligations, no runtime halt, and every restoration passes",
    "infrastructure_failure_is_unsafe": True,
    "inferential_unit": "seed cluster across every frozen task-budget cell",
    "estimand": "finite sealed three-family task-seed-budget grid",
}
CONFIRMATION_GATES = {
    "complete_exact_grid": True,
    "zero_infrastructure_failures": True,
    "planner_is_exercised": True,
    "stack_wide_reserve_binds_live": True,
    "stack_wide_restorations_all_pass": True,
    "proposal_local_makes_unsafe_admissions": True,
    "proposal_local_strands_obligations": True,
    "full_activity_endpoint_rate_exceeds_local": True,
    "minimum_coactivated_effect_families": 2,
    "minimum_planner_mediated_paired_wins": 2,
    "minimum_seed_cluster_net_wins": 10,
    "maximum_sequence_adjusted_sign_pvalue": 0.05,
    "full_has_task_successes": True,
    "full_task_success_descriptive_guardrail_cells": 20,
    "minimum_task_families_with_full_success_floor": 2,
    "minimum_full_task_successes_per_family": 10,
    "always_abstain_is_empirically_degenerate": True,
    "all_rows_respect_hard_budgets": True,
}
DECISION_RULE = {
    "on_pass": "report a planner-enabled cross-task-family causal reserve result together with task-success, activity, and always-abstain comparisons",
    "on_failure": "seal every outcome, do not use this population as positive evidence, and open no further reserve stress population for this submission",
}
SEQUENCE_FAMILY_SIZE = 4


class _CrossFamilyReserveDriverV15(FullPactConfirmationDriverV15):
    """PACT-v15 with an explicit, auditable reserve mode."""

    stack_wide = True

    def inverse_reserve(self, candidate: Any, decision: str) -> tuple[bool, int]:
        active_reserve = sum(
            (inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active)
        )
        proposal_reserve = 0
        if decision == "transact":
            contract = self.inventory().contract_by_bid.get(candidate.bid)
            if contract is None:
                return (False, active_reserve)
            proposal_reserve = inverse_action_cost_v8(contract)
        stack_wide_reserve = active_reserve + proposal_reserve
        applied_reserve = stack_wide_reserve if self.stack_wide else proposal_reserve
        remaining_after_action = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        allowed = remaining_after_action >= applied_reserve
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "cross_family_reservation_v1",
                "reservation_rule": "stack_wide" if self.stack_wide else "proposal_local",
                "decision": decision,
                "bid": candidate.bid,
                "registered_active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "stack_wide_required_inverse_cost": stack_wide_reserve,
                "applied_inverse_reserve": applied_reserve,
                "remaining_after_action": remaining_after_action,
                "allowed": allowed,
            }
        )
        return (allowed, applied_reserve)


class StackWideCrossFamilyDriverV15(_CrossFamilyReserveDriverV15):
    method_id = FULL_METHOD
    stack_wide = True


class ProposalLocalCrossFamilyDriverV15(_CrossFamilyReserveDriverV15):
    method_id = LOCAL_ABLATION
    stack_wide = False


class AlwaysAbstainDriverV15(FullPactConfirmationDriverV15):
    method_id = ABSTAIN_BASELINE

    def run_policy(self) -> None:
        self.method_failure = "predeclared always-abstain baseline"


DRIVERS = {
    FULL_METHOD: StackWideCrossFamilyDriverV15,
    LOCAL_ABLATION: ProposalLocalCrossFamilyDriverV15,
    ABSTAIN_BASELINE: AlwaysAbstainDriverV15,
}


def task_records() -> list[dict[str, Any]]:
    return [
        {"task_id": task, "family_group": TASK_FAMILIES[task], "gui_action_budgets": list(budgets)}
        for task, budgets in TASK_BUDGETS.items()
    ]


def expected_episodes() -> int:
    cells = sum((len(budgets) for budgets in TASK_BUDGETS.values()))
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
        "arms": list(ARMS),
        "isolated_method_difference": "stack-wide active-plus-proposal inverse reserve versus proposal-only inverse reserve; always-abstain is descriptive",
        "tasks": task_records(),
        "fresh_seeds": list(SEEDS),
        "common_budgets": dict(COMMON_BUDGETS),
        "generation": dict(GENERATION),
        "expected_episodes": expected_episodes(),
        "primary_outcome": dict(PRIMARY_OUTCOME),
        "confirmation_gates": dict(CONFIRMATION_GATES),
        "decision_rule": dict(DECISION_RULE),
        "repositories": dict(repositories),
        "source_sha256": dict(sorted(source_sha256.items())),
        "preregistration": {"path": preregistration_path, "sha256": preregistration_sha256},
        "outcome_based_exclusion_allowed": False,
        "partial_reexecution_allowed": False,
        "episode_replay_allowed": False,
        "outputs": {
            "run_root": "runs/inversereserve_cross_family_stress_v1",
            "result": "validation/inversereserve_cross_family_stress_v1_result.json",
        },
    }
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected cross-family protocol identity",
    )
    require(
        not (tuple(protocol.get("arms", ())) != ARMS or set(DRIVERS) != set(ARMS)),
        "cross-family arms changed",
    )
    require(not protocol.get("tasks") != task_records(), "cross-family task-budget grid changed")
    require(not tuple(protocol.get("fresh_seeds", ())) != SEEDS, "cross-family seeds changed")
    require(not protocol.get("common_budgets") != COMMON_BUDGETS, "cross-family common budgets changed")
    require(not protocol.get("generation") != GENERATION, "cross-family generation settings changed")
    require(
        not protocol.get("expected_episodes") != expected_episodes(), "cross-family episode count changed"
    )
    require(not protocol.get("primary_outcome") != PRIMARY_OUTCOME, "cross-family primary outcome changed")
    require(
        not protocol.get("confirmation_gates") != CONFIRMATION_GATES,
        "cross-family confirmation gates changed",
    )
    require(not protocol.get("decision_rule") != DECISION_RULE, "cross-family decision rule changed")
    require(
        not protocol.get("sequence_family_size") != SEQUENCE_FAMILY_SIZE,
        "cross-family sequence adjustment changed",
    )
    require(isinstance(protocol.get("predecessor"), dict), "cross-family predecessor binding is absent")
    require(isinstance(protocol.get("repositories"), dict), "cross-family repository pins are absent")
    require(isinstance(protocol.get("source_sha256"), dict), "cross-family source bindings are absent")
    require(isinstance(protocol.get("preregistration"), dict), "cross-family preregistration is absent")
    for key in ("outcome_based_exclusion_allowed", "partial_reexecution_allowed", "episode_replay_allowed"):
        if protocol.get(key) is not False:
            raise ValueError(f"cross-family {key} changed")


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    rows: list[dict[str, Any]] = []
    for seed_index, seed in enumerate(SEEDS):
        for task_index, (task, budgets) in enumerate(TASK_BUDGETS.items()):
            for budget_index, budget in enumerate(budgets):
                rotation = (seed_index + task_index + budget_index) % len(ARMS)
                order = ARMS[rotation:] + ARMS[:rotation]
                for arm_position, method in enumerate(order):
                    rows.append(
                        {
                            "episode_index": len(rows),
                            "seed_index": seed_index,
                            "task_index": task_index,
                            "budget_index": budget_index,
                            "arm_position": arm_position,
                            "task": task,
                            "family_group": TASK_FAMILIES[task],
                            "seed": seed,
                            "maximum_gui_actions": budget,
                            "method": method,
                            "episode_id": f"{task}__seed{seed}__budget{budget}__{method}",
                        }
                    )
    if len(rows) != int(protocol["expected_episodes"]):
        raise ValueError("cross-family manifest is incomplete")
    if len({row["episode_id"] for row in rows}) != len(rows):
        raise ValueError("cross-family manifest contains duplicate episodes")
    return rows


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    counts = {arm: Counter() for arm in ARMS}
    for row in episode_manifest(protocol):
        counts[row["method"]][int(row["arm_position"])] += 1
    return {arm: dict(sorted(values.items())) for arm, values in counts.items()}
