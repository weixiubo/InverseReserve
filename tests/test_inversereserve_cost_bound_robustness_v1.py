from __future__ import annotations

from inversereserve.studies.inversereserve_cost_bound_robustness_v1 import analyze_cost_bound_robustness_v1


def test_complete_cost_bound_sensitivity_domain_passes() -> None:
    result = analyze_cost_bound_robustness_v1()
    counts = result["counts"]

    assert result["passed"] is True
    assert counts["all_states"] == 4_836
    assert counts["exact_admissions"] == 1_320
    assert counts["exact_rejections"] == 3_516
    assert counts["underestimate_eligible_states"] > 0
    assert counts["underestimate_unsafe_admissions"] > 0
    assert counts["buffered_unsafe_admissions"] == 0
    assert counts["buffered_exact_decision_mismatches"] == 0
    assert counts["overestimate_unsafe_admissions"] == 0
    assert counts["overestimate_additional_rejections"] > 0


def test_examples_expose_exact_one_call_boundary() -> None:
    result = analyze_cost_bound_robustness_v1()

    assert result["unsafe_examples"]
    assert all(
        row["declared_demand"] + 1 == row["true_demand"]
        and row["remaining_after_forward"] == row["declared_demand"]
        for row in result["unsafe_examples"]
    )
    assert result["overreject_examples"]
    assert all(
        row["declared_demand"] == row["true_demand"] + 1
        and row["remaining_after_forward"] == row["true_demand"]
        for row in result["overreject_examples"]
    )
