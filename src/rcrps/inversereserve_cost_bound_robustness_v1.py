"""Bounded sensitivity of InverseReserve to one-call cost-bound errors.

The analysis reuses the complete preregistered pre-forward domain from the
source-bound recovery verification.  It opens no benchmark environment and
calls no model, browser, reward, or evaluator.
"""

from __future__ import annotations

from typing import Any

from .bounded_recovery_verification_v1 import (
    ACTIVE_COST_SEQUENCES,
    BUDGETS,
    INVERSE_COSTS,
)


def _first_cost_two_underestimate(costs: tuple[int, ...]) -> tuple[int, ...] | None:
    """Reduce exactly the first cost-2 component by one call."""

    try:
        index = costs.index(2)
    except ValueError:
        return None
    declared = list(costs)
    declared[index] = 1
    return tuple(declared)


def _first_component_overestimate(costs: tuple[int, ...]) -> tuple[int, ...]:
    """Increase exactly the first registered component by one call."""

    if not costs:
        raise ValueError("the proposal guarantees a nonempty cost vector")
    declared = list(costs)
    declared[0] += 1
    return tuple(declared)


def analyze_cost_bound_robustness_v1() -> dict[str, Any]:
    """Enumerate exact, underestimated, buffered, and overestimated gates."""

    counts = {
        "all_states": 0,
        "exact_admissions": 0,
        "exact_rejections": 0,
        "underestimate_eligible_states": 0,
        "underestimate_admissions": 0,
        "underestimate_unsafe_admissions": 0,
        "buffered_admissions": 0,
        "buffered_unsafe_admissions": 0,
        "buffered_exact_decision_mismatches": 0,
        "overestimate_eligible_states": 0,
        "overestimate_admissions": 0,
        "overestimate_unsafe_admissions": 0,
        "overestimate_additional_rejections": 0,
    }
    unsafe_examples: list[dict[str, Any]] = []
    overreject_examples: list[dict[str, Any]] = []

    for budget in BUDGETS:
        for executed in range(budget):
            remaining = budget - executed - 1
            for active_costs in ACTIVE_COST_SEQUENCES:
                for proposal_cost in INVERSE_COSTS:
                    component_costs = (*active_costs, proposal_cost)
                    true_demand = sum(component_costs)
                    exact_allowed = remaining >= true_demand
                    counts["all_states"] += 1
                    counts[
                        "exact_admissions" if exact_allowed else "exact_rejections"
                    ] += 1

                    underestimated = _first_cost_two_underestimate(component_costs)
                    if underestimated is not None:
                        counts["underestimate_eligible_states"] += 1
                        declared_demand = sum(underestimated)
                        under_allowed = remaining >= declared_demand
                        buffered_allowed = remaining >= declared_demand + 1
                        under_unsafe = under_allowed and not exact_allowed
                        buffered_unsafe = buffered_allowed and not exact_allowed
                        counts["underestimate_admissions"] += int(under_allowed)
                        counts["underestimate_unsafe_admissions"] += int(
                            under_unsafe
                        )
                        counts["buffered_admissions"] += int(buffered_allowed)
                        counts["buffered_unsafe_admissions"] += int(buffered_unsafe)
                        counts["buffered_exact_decision_mismatches"] += int(
                            buffered_allowed != exact_allowed
                        )
                        if under_unsafe and len(unsafe_examples) < 5:
                            unsafe_examples.append(
                                {
                                    "budget": budget,
                                    "executed_actions": executed,
                                    "remaining_after_forward": remaining,
                                    "active_inverse_costs": list(active_costs),
                                    "proposal_inverse_cost": proposal_cost,
                                    "true_demand": true_demand,
                                    "declared_demand": declared_demand,
                                    "buffered_demand": declared_demand + 1,
                                }
                            )

                    overestimated = _first_component_overestimate(component_costs)
                    counts["overestimate_eligible_states"] += 1
                    over_demand = sum(overestimated)
                    over_allowed = remaining >= over_demand
                    over_unsafe = over_allowed and not exact_allowed
                    over_reject = exact_allowed and not over_allowed
                    counts["overestimate_admissions"] += int(over_allowed)
                    counts["overestimate_unsafe_admissions"] += int(over_unsafe)
                    counts["overestimate_additional_rejections"] += int(over_reject)
                    if over_reject and len(overreject_examples) < 5:
                        overreject_examples.append(
                            {
                                "budget": budget,
                                "executed_actions": executed,
                                "remaining_after_forward": remaining,
                                "active_inverse_costs": list(active_costs),
                                "proposal_inverse_cost": proposal_cost,
                                "true_demand": true_demand,
                                "declared_demand": over_demand,
                            }
                        )

    checks = {
        "complete_pre_forward_domain": counts["all_states"] == 4_836,
        "exact_decision_partition": (
            counts["exact_admissions"] + counts["exact_rejections"]
            == counts["all_states"]
        ),
        "underestimation_is_exercised": (
            counts["underestimate_eligible_states"] > 0
            and counts["underestimate_unsafe_admissions"] > 0
        ),
        "one_call_allowance_eliminates_unsafe_admissions": (
            counts["buffered_unsafe_admissions"] == 0
        ),
        "one_call_allowance_matches_exact_gate": (
            counts["buffered_exact_decision_mismatches"] == 0
        ),
        "overestimation_is_safe": counts["overestimate_unsafe_admissions"] == 0,
        "overestimation_rejects_feasible_states": (
            counts["overestimate_additional_rejections"] > 0
        ),
    }
    return {
        "scope": (
            "zero-reset bounded cost-bound sensitivity; not benchmark efficacy "
            "or an estimate of real-world contract error rates"
        ),
        "domain": {
            "budgets": list(BUDGETS),
            "executed_actions": "0..B-1",
            "active_depths": [0, 1, 2, 3, 4],
            "registered_component_costs": list(INVERSE_COSTS),
            "component_order": "active LIFO order followed by proposal",
        },
        "perturbations": {
            "underestimate": (
                "reduce the first cost-2 registered component by one call"
            ),
            "certified_allowance": "add one call to the underestimated aggregate",
            "overestimate": "add one call to the first registered component",
        },
        "counts": counts,
        "unsafe_examples": unsafe_examples,
        "overreject_examples": overreject_examples,
        "checks": checks,
        "passed": all(checks.values()),
    }


__all__ = ["analyze_cost_bound_robustness_v1"]
