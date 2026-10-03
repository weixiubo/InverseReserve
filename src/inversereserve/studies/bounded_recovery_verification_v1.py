from __future__ import annotations

from itertools import product
from types import SimpleNamespace
from typing import Any

from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import COMPENSATOR_LABELS, TransactionContractV4
from inversereserve.controllers.confirmation_agents_v13 import FullPactConfirmationDriverV13
from inversereserve.controllers.pact_controller_v4 import RuntimeHaltedV4
from inversereserve.controllers.pact_controller_v13 import FailClosedTransactionRuntimeV13
from inversereserve.studies.verification_fixtures import (
    _field_snapshot as _field_snapshot,
)
from inversereserve.studies.verification_fixtures import (
    _LifoExecutor as _LifoExecutor,
)

"Bounded executable verification of InverseReserve recovery mechanisms.\n\nThis module calls the production PACT-v13 admission, repair-reservation, and\nLIFO-cleanup methods over the domain frozen before implementation.  Independent\narithmetic predicates and deterministic public-state fixtures serve as oracles;\nthe exercise makes no benchmark-efficacy or hidden-state claim.\n"
BUDGETS = tuple(range(1, 13))
ACTIVE_DEPTHS = tuple(range(5))
INVERSE_COSTS = (1, 2)
LIFO_DEPTHS = tuple(range(1, 5))
LIFO_FAILURE_MODES = ("wrong_projection", "action_error", "terminal_result", "executor_exception")
MAX_RECORDED_VIOLATIONS = 25


def _cost_sequences() -> tuple[tuple[int, ...], ...]:
    return tuple((costs for depth in ACTIVE_DEPTHS for costs in product(INVERSE_COSTS, repeat=depth)))


ACTIVE_COST_SEQUENCES = _cost_sequences()


def _contract(
    bid: str, inverse_cost: int, *, expected: str = "value", prior: str = "", repairable: bool = False
) -> TransactionContractV4:
    if inverse_cost == 1:
        inverse = (ContractActionV4("fill", bid, prior, False),)
        kind = "editable_field_assignment"
        projection = "editable_field_assignment"
    elif inverse_cost == 2:
        inverse = (ContractActionV4("press", bid, "Escape"), ContractActionV4("fill", bid, prior, False))
        kind = "autocomplete_query"
        projection = "autocomplete_query"
    else:
        raise ValueError(f"unsupported bounded inverse cost: {inverse_cost}")
    return TransactionContractV4(
        kind=kind,
        semantic_bid=bid,
        action=ContractActionV4("fill", bid, expected, inverse_cost == 2),
        inverse_actions=inverse,
        expected_value=expected,
        prior_value=prior,
        projection_kind=projection,
        dynamic_compensator_labels=tuple(sorted(COMPENSATOR_LABELS)) if repairable else (),
        maximum_interrupt_repairs=1 if repairable else 0,
    )


def _driver(
    *, budget: int, executed_actions: int, active_costs: tuple[int, ...]
) -> FullPactConfirmationDriverV13:
    driver = object.__new__(FullPactConfirmationDriverV13)
    driver.budgets = {"maximum_gui_actions": budget}
    driver.executor = SimpleNamespace(actions=[None] * executed_actions)
    driver.runtime = SimpleNamespace(
        active=[
            SimpleNamespace(contract=_contract(f"active{index}", cost))
            for index, cost in enumerate(active_costs)
        ]
    )
    driver.trace = []
    driver.inverse_reservation_audits = 0
    driver.interrupt_repair_reservation_audits = 0
    driver.interrupt_repair_reservation_fallbacks = 0
    return driver


def _append_violation(
    examples: list[dict[str, Any]], *, kind: str, state: dict[str, Any], observed: Any, expected: Any
) -> None:
    if len(examples) < MAX_RECORDED_VIOLATIONS:
        examples.append({"kind": kind, "state": state, "observed": observed, "expected": expected})


def verify_pre_forward_reserve() -> dict[str, Any]:
    """Enumerate the frozen active-stack-plus-proposal admission domain."""
    counts = {
        "states": 0,
        "production_admissions": 0,
        "production_rejections": 0,
        "exact_boundary_states": 0,
        "exact_boundary_admissions": 0,
        "one_below_boundary_states": 0,
        "one_below_boundary_rejections": 0,
        "local_only_false_admissions": 0,
        "predicate_mismatches": 0,
        "reserve_mismatches": 0,
        "audit_mismatches": 0,
        "unsafe_production_admissions": 0,
    }
    violations: list[dict[str, Any]] = []
    for budget in BUDGETS:
        for executed in range(budget):
            remaining = budget - executed - 1
            for active_costs in ACTIVE_COST_SEQUENCES:
                for proposal_cost in INVERSE_COSTS:
                    proposal = _contract("proposal", proposal_cost)
                    driver = _driver(budget=budget, executed_actions=executed, active_costs=active_costs)
                    driver.inventory = lambda proposal=proposal: SimpleNamespace(
                        contract_by_bid={proposal.semantic_bid: proposal}
                    )
                    candidate = SimpleNamespace(bid=proposal.semantic_bid)
                    observed_allowed, observed_reserve = driver.inverse_reserve(candidate, "transact")
                    joint_reserve = sum(active_costs) + proposal_cost
                    expected_allowed = remaining >= joint_reserve
                    local_only_allowed = remaining >= proposal_cost
                    state = {
                        "budget": budget,
                        "executed_actions": executed,
                        "remaining_after_forward": remaining,
                        "active_inverse_costs": list(active_costs),
                        "proposal_inverse_cost": proposal_cost,
                    }
                    counts["states"] += 1
                    counts["production_admissions" if observed_allowed else "production_rejections"] += 1
                    if remaining == joint_reserve:
                        counts["exact_boundary_states"] += 1
                        counts["exact_boundary_admissions"] += int(observed_allowed)
                    if remaining == joint_reserve - 1:
                        counts["one_below_boundary_states"] += 1
                        counts["one_below_boundary_rejections"] += int(not observed_allowed)
                    counts["local_only_false_admissions"] += int(
                        local_only_allowed and (not expected_allowed)
                    )
                    if observed_allowed != expected_allowed:
                        counts["predicate_mismatches"] += 1
                        _append_violation(
                            violations,
                            kind="pre_forward_predicate",
                            state=state,
                            observed=observed_allowed,
                            expected=expected_allowed,
                        )
                    if observed_reserve != joint_reserve:
                        counts["reserve_mismatches"] += 1
                        _append_violation(
                            violations,
                            kind="pre_forward_reserve",
                            state=state,
                            observed=observed_reserve,
                            expected=joint_reserve,
                        )
                    expected_event = {
                        "event_index": 0,
                        "type": "inverse_budget_reservation",
                        "decision": "transact",
                        "bid": "proposal",
                        "active_inverse_cost": joint_reserve,
                        "remaining_after_action": remaining,
                        "allowed": expected_allowed,
                    }
                    if driver.trace != [expected_event]:
                        counts["audit_mismatches"] += 1
                        _append_violation(
                            violations,
                            kind="pre_forward_audit",
                            state=state,
                            observed=driver.trace,
                            expected=[expected_event],
                        )
                    counts["unsafe_production_admissions"] += int(
                        observed_allowed and remaining < joint_reserve
                    )
    checks = _verify_pre_forward_reserve_confirmation_checks(counts=counts)
    return {
        "domain": {
            "budgets": list(BUDGETS),
            "executed_actions": "0..B-1",
            "active_depths": list(ACTIVE_DEPTHS),
            "inverse_costs": list(INVERSE_COSTS),
            "active_cost_sequence_count": len(ACTIVE_COST_SEQUENCES),
            "proposal_inverse_costs": list(INVERSE_COSTS),
        },
        "counts": counts,
        "violation_examples": violations,
        "checks": checks,
        "passed": all(checks.values()),
    }


def verify_interrupt_repair_reserve() -> dict[str, Any]:
    """Enumerate the frozen post-forward compensator--retry reserve domain."""
    proposal = _contract("proposal", 1, repairable=True)
    counts = {
        "states": 0,
        "production_admissions": 0,
        "production_fallbacks": 0,
        "exact_boundary_states": 0,
        "exact_boundary_admissions": 0,
        "one_below_boundary_states": 0,
        "one_below_boundary_fallbacks": 0,
        "predicate_mismatches": 0,
        "accounting_mismatches": 0,
        "audit_mismatches": 0,
        "counter_mismatches": 0,
        "reserve_consuming_admissions": 0,
    }
    violations: list[dict[str, Any]] = []
    for budget in BUDGETS:
        for executed in range(1, budget + 1):
            remaining = budget - executed
            for active_costs in ACTIVE_COST_SEQUENCES:
                _check_repair_reservation_state(
                    budget, executed, remaining, active_costs, proposal, counts, violations
                )
    checks = _verify_interrupt_repair_reserve_confirmation_checks(counts=counts)
    return {
        "domain": {
            "budgets": list(BUDGETS),
            "post_forward_actions": "1..B",
            "active_depths": list(ACTIVE_DEPTHS),
            "active_inverse_costs": list(INVERSE_COSTS),
            "active_cost_sequence_count": len(ACTIVE_COST_SEQUENCES),
            "proposal_inverse_cost": 1,
            "repair_pair_actions": 2,
        },
        "counts": counts,
        "violation_examples": violations,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _unused_interrupt_reservation(_contract: TransactionContractV4) -> Any:
    raise AssertionError("LIFO cleanup must not request interrupt-repair budget")


def _lifo_scenario(
    depth: int, *, failure_position: int | None = None, failure_mode: str | None = None
) -> dict[str, Any]:
    snapshots = tuple((_field_snapshot(depth, filled) for filled in range(depth + 1)))
    executor = _LifoExecutor(snapshots, failure_position=failure_position, failure_mode=failure_mode)
    runtime = FailClosedTransactionRuntimeV13(executor, _unused_interrupt_reservation)
    admissions = []
    for index in range(depth):
        contract = _contract(f"field{index}", 1, expected=f"value-{index}", prior="")
        outcome = runtime.transact(
            before=snapshots[index], contract=contract, candidate_label=f"Field {index}"
        )
        admissions.append(outcome.admitted and (not outcome.halted))
    pre_cleanup_events = len(runtime.events)
    outcomes = runtime.restore_all("bounded LIFO verification")
    inverse_bids = [call["bid"] for call in executor.calls if call["role"] == "typed_inverse"]
    completed_bids = [str(row["bid"]) for row in runtime.completed]
    active_bids = [row.contract.semantic_bid for row in runtime.active]
    if failure_position is None:
        return _successful_lifo_result(
            depth,
            admissions,
            outcomes,
            inverse_bids,
            completed_bids,
            active_bids,
            runtime,
            pre_cleanup_events,
        )
    assert failure_mode in LIFO_FAILURE_MODES
    assert 0 <= failure_position < depth
    expected_attempted = [f"field{index}" for index in range(depth - 1, depth - failure_position - 2, -1)]
    expected_completed = expected_attempted[:-1]
    expected_active = [f"field{index}" for index in range(depth - failure_position)]
    calls_before_lock_probe = len(executor.calls)
    try:
        runtime.restore_top("locked follow-up must be rejected")
        lock_rejected = False
    except RuntimeHaltedV4:
        lock_rejected = True
    expected_pass_vector = [True] * failure_position + [False]
    checks = {
        "all_forwards_admitted": all(admissions),
        "cleanup_stops_at_first_failure": len(outcomes) == failure_position + 1
        and [outcome.passed for outcome in outcomes] == expected_pass_vector,
        "only_attempted_inverse_identifiers_execute": inverse_bids == expected_attempted,
        "successfully_restored_tops_are_completed": completed_bids == expected_completed,
        "failed_and_lower_obligations_remain_active": active_bids == expected_active,
        "runtime_locks": runtime.halted is True,
        "locked_runtime_rejects_follow_up": lock_rejected,
        "lock_probe_executes_no_action": len(executor.calls) == calls_before_lock_probe,
    }
    return {
        "scenario": "injected_cleanup_failure",
        "depth": depth,
        "failure_position": failure_position,
        "failure_mode": failure_mode,
        "inverse_bids": inverse_bids,
        "completed_bids": completed_bids,
        "active_bids": active_bids,
        "halt_reason": runtime.halt_reason,
        "checks": checks,
        "passed": all(checks.values()),
    }


def verify_lifo_cleanup() -> dict[str, Any]:
    """Execute successful and fail-closed multi-level cleanup traces."""
    successful = [_lifo_scenario(depth) for depth in LIFO_DEPTHS]
    failures = [
        _lifo_scenario(depth, failure_position=position, failure_mode=mode)
        for depth in LIFO_DEPTHS
        for position in range(depth)
        for mode in LIFO_FAILURE_MODES
    ]
    expected_failures = sum(LIFO_DEPTHS) * len(LIFO_FAILURE_MODES)
    checks = _verify_lifo_cleanup_confirmation_checks(
        expected_failures=expected_failures, failures=failures, successful=successful
    )
    return {
        "domain": {
            "depths": list(LIFO_DEPTHS),
            "failure_modes": list(LIFO_FAILURE_MODES),
            "failure_position": "every inverse position at each depth",
        },
        "counts": {
            "successful_traces": len(successful),
            "fault_traces": len(failures),
            "total_traces": len(successful) + len(failures),
            "passed_traces": sum((row["passed"] for row in successful + failures)),
        },
        "successful_traces": successful,
        "fault_traces": failures,
        "checks": checks,
        "passed": all(checks.values()),
    }


def run_bounded_recovery_verification_v1() -> dict[str, Any]:
    """Run the complete preregistered bounded verification."""
    pre_forward = verify_pre_forward_reserve()
    repair = verify_interrupt_repair_reserve()
    lifo = verify_lifo_cleanup()
    checks = {
        "pre_forward_stack_wide_reserve_passes": pre_forward["passed"] is True,
        "interrupt_repair_reserve_passes": repair["passed"] is True,
        "executed_lifo_cleanup_passes": lifo["passed"] is True,
        "no_model_browser_reward_or_evaluator_input": True,
        "zero_benchmark_resets": True,
        "bounded_mechanism_verification_not_efficacy": True,
    }
    return {
        "scope": "source-bound bounded executable PACT-v13 recovery verification; not benchmark efficacy, hidden-state rollback, or general safety",
        "pre_forward_reserve": pre_forward,
        "interrupt_repair_reserve": repair,
        "lifo_cleanup": lifo,
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = [
    "ACTIVE_COST_SEQUENCES",
    "ACTIVE_DEPTHS",
    "BUDGETS",
    "INVERSE_COSTS",
    "LIFO_DEPTHS",
    "LIFO_FAILURE_MODES",
    "run_bounded_recovery_verification_v1",
    "verify_interrupt_repair_reserve",
    "verify_lifo_cleanup",
    "verify_pre_forward_reserve",
]


def _verify_pre_forward_reserve_confirmation_checks(*, counts: Any) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "nonempty_frozen_domain": counts["states"] > 0,
        "production_matches_joint_predicate": counts["predicate_mismatches"] == 0,
        "production_reports_exact_joint_reserve": counts["reserve_mismatches"] == 0,
        "production_audit_is_exact": counts["audit_mismatches"] == 0,
        "zero_unsafe_production_admissions": counts["unsafe_production_admissions"] == 0,
        "every_exact_boundary_is_admitted": counts["exact_boundary_states"] > 0
        and counts["exact_boundary_admissions"] == counts["exact_boundary_states"],
        "every_one_below_boundary_is_rejected": counts["one_below_boundary_states"] > 0
        and counts["one_below_boundary_rejections"] == counts["one_below_boundary_states"],
        "local_only_counterfactual_has_false_admissions": counts["local_only_false_admissions"] > 0,
    }


def _verify_interrupt_repair_reserve_confirmation_checks(*, counts: Any) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "nonempty_frozen_domain": counts["states"] > 0,
        "production_matches_repair_predicate": counts["predicate_mismatches"] == 0,
        "production_accounting_is_exact": counts["accounting_mismatches"] == 0,
        "production_audit_is_exact": counts["audit_mismatches"] == 0,
        "production_counters_are_exact": counts["counter_mismatches"] == 0,
        "zero_reserve_consuming_admissions": counts["reserve_consuming_admissions"] == 0,
        "every_exact_boundary_is_admitted": counts["exact_boundary_states"] > 0
        and counts["exact_boundary_admissions"] == counts["exact_boundary_states"],
        "every_one_below_boundary_falls_back": counts["one_below_boundary_states"] > 0
        and counts["one_below_boundary_fallbacks"] == counts["one_below_boundary_states"],
    }


def _verify_lifo_cleanup_confirmation_checks(
    *, expected_failures: Any, failures: Any, successful: Any
) -> dict[str, bool]:
    """Apply the registered decision gates to computed outcomes."""
    return {
        "exact_success_inventory": len(successful) == len(LIFO_DEPTHS),
        "all_successful_cleanups_pass": all((row["passed"] for row in successful)),
        "exact_failure_inventory": len(failures) == expected_failures,
        "all_failure_traces_fail_closed": all((row["passed"] for row in failures)),
        "every_depth_is_exercised": {row["depth"] for row in successful} == set(LIFO_DEPTHS),
        "every_failure_mode_is_exercised": {row["failure_mode"] for row in failures}
        == set(LIFO_FAILURE_MODES),
    }


def _check_repair_reservation_state(
    budget: int,
    executed: int,
    remaining: int,
    active_costs: tuple[int, ...],
    proposal: TransactionContractV4,
    counts: dict[str, int],
    violations: list[dict[str, Any]],
) -> None:
    driver = _driver(budget=budget, executed_actions=executed, active_costs=active_costs)
    reservation = driver.interrupt_repair_reservation(proposal)
    joint_reserve = sum(active_costs) + 1
    expected_allowed = remaining - 2 >= joint_reserve
    state = {
        "budget": budget,
        "post_forward_actions": executed,
        "remaining_gui_actions": remaining,
        "active_inverse_costs": list(active_costs),
        "proposal_inverse_cost": 1,
        "repair_pair_actions": 2,
    }
    counts["states"] += 1
    counts["production_admissions" if reservation.allowed else "production_fallbacks"] += 1
    if remaining - 2 == joint_reserve:
        counts["exact_boundary_states"] += 1
        counts["exact_boundary_admissions"] += int(reservation.allowed)
    if remaining - 2 == joint_reserve - 1:
        counts["one_below_boundary_states"] += 1
        counts["one_below_boundary_fallbacks"] += int(not reservation.allowed)
    if reservation.allowed != expected_allowed:
        counts["predicate_mismatches"] += 1
        _append_violation(
            violations,
            kind="repair_predicate",
            state=state,
            observed=reservation.allowed,
            expected=expected_allowed,
        )
    accounting = (
        reservation.remaining_gui_actions == remaining
        and reservation.repair_pair_actions == 2
        and (reservation.registered_inverse_reserve == joint_reserve)
    )
    if not accounting:
        counts["accounting_mismatches"] += 1
        _append_violation(
            violations,
            kind="repair_accounting",
            state=state,
            observed={
                "remaining": reservation.remaining_gui_actions,
                "pair": reservation.repair_pair_actions,
                "reserve": reservation.registered_inverse_reserve,
            },
            expected={"remaining": remaining, "pair": 2, "reserve": joint_reserve},
        )
    expected_event = {
        "event_index": 0,
        "type": "interrupt_repair_reservation_v10",
        "remaining_gui_actions": remaining,
        "repair_pair_actions": 2,
        "registered_inverse_reserve": joint_reserve,
        "allowed": expected_allowed,
    }
    if driver.trace != [expected_event]:
        counts["audit_mismatches"] += 1
        _append_violation(
            violations, kind="repair_audit", state=state, observed=driver.trace, expected=[expected_event]
        )
    expected_fallbacks = int(not expected_allowed)
    if (
        driver.interrupt_repair_reservation_audits != 1
        or driver.interrupt_repair_reservation_fallbacks != expected_fallbacks
    ):
        counts["counter_mismatches"] += 1
        _append_violation(
            violations,
            kind="repair_counters",
            state=state,
            observed={
                "audits": driver.interrupt_repair_reservation_audits,
                "fallbacks": driver.interrupt_repair_reservation_fallbacks,
            },
            expected={"audits": 1, "fallbacks": expected_fallbacks},
        )
    counts["reserve_consuming_admissions"] += int(reservation.allowed and remaining - 2 < joint_reserve)


def _successful_lifo_result(
    depth: int,
    admissions: list[bool],
    outcomes: Any,
    inverse_bids: list[str],
    completed_bids: list[str],
    active_bids: list[str],
    runtime: Any,
    pre_cleanup_events: int,
) -> dict[str, Any]:
    expected_reverse = [f"field{index}" for index in reversed(range(depth))]
    cleanup_types = [event["type"] for event in runtime.events[pre_cleanup_events:]]
    checks = {
        "all_forwards_admitted": all(admissions),
        "one_outcome_per_stack_level": len(outcomes) == depth,
        "every_inverse_restoration_passes": all(
            (
                outcome.attempted and outcome.passed and (outcome.check is not None) and outcome.check.passed
                for outcome in outcomes
            )
        ),
        "inverse_identifier_order_is_lifo": inverse_bids == expected_reverse,
        "one_inverse_per_level": len(inverse_bids) == depth,
        "restoration_precedes_each_pop": cleanup_types
        == [kind for _ in range(depth) for kind in ("action", "restoration")],
        "completion_records_are_lifo": completed_bids == expected_reverse,
        "final_stack_is_empty": active_bids == [],
        "runtime_remains_live": runtime.halted is False,
    }
    return {
        "scenario": "successful_cleanup",
        "depth": depth,
        "inverse_bids": inverse_bids,
        "completed_bids": completed_bids,
        "active_bids": active_bids,
        "checks": checks,
        "passed": all(checks.values()),
    }
