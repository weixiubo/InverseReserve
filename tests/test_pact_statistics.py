from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.pact_statistics import (  # noqa: E402
    paired_binary_comparison,
    restoration_summary,
    wilson_interval,
    zero_event_upper_bound,
)


def paired_rows() -> list[dict]:
    full = {
        ("family_a", 1): True,
        ("family_a", 2): True,
        ("family_a", 3): False,
        ("family_a", 4): True,
        ("family_b", 1): True,
        ("family_b", 2): False,
        ("family_b", 3): True,
        ("family_b", 4): True,
    }
    base = {
        ("family_a", 1): False,
        ("family_a", 2): True,
        ("family_a", 3): False,
        ("family_a", 4): False,
        ("family_b", 1): False,
        ("family_b", 2): True,
        ("family_b", 3): False,
        ("family_b", 4): True,
    }
    rows = []
    for method, values in (("full_pact", full), ("raw_open_loop", base)):
        rows.extend(
            {
                "method": method,
                "task": family,
                "seed": seed,
                "success": success,
            }
            for (family, seed), success in values.items()
        )
    return rows


def test_paired_binary_comparison_recomputes_complete_grid_and_discordance() -> None:
    result = paired_binary_comparison(
        paired_rows(),
        full_method="full_pact",
        baseline="raw_open_loop",
        bootstrap_samples=500,
        bootstrap_seed=17,
    )
    assert result["families"] == ["family_a", "family_b"]
    assert result["seeds"] == [1, 2, 3, 4]
    assert result["paired_episodes"] == 8
    assert result["observed_family_differences"] == {
        "family_a": 0.5,
        "family_b": 0.25,
    }
    assert result["observed_macro_success_difference"] == 0.375
    assert result["observed_task_weighted_success_difference"] == 0.375
    assert result["discordant_full_success_baseline_failure"] == 4
    assert result["discordant_full_failure_baseline_success"] == 1
    assert result["net_paired_successes"] == 3
    assert result["exact_mcnemar_two_sided_p"] == 0.375
    assert result["bootstrap_unit"] == "seed cluster shared across families"
    assert len(result["bootstrap_95_percent_ci"]) == 2


def test_seed_cluster_bootstrap_is_deterministic_and_input_order_invariant() -> None:
    rows = paired_rows()
    shuffled = list(rows)
    random.Random(91).shuffle(shuffled)
    left = paired_binary_comparison(
        rows,
        full_method="full_pact",
        baseline="raw_open_loop",
        bootstrap_samples=100,
        bootstrap_seed=29,
    )
    right = paired_binary_comparison(
        shuffled,
        full_method="full_pact",
        baseline="raw_open_loop",
        bootstrap_samples=100,
        bootstrap_seed=29,
    )
    assert left == right


def test_paired_grid_rejects_duplicates_missing_cells_and_unbalanced_seeds() -> None:
    rows = paired_rows()
    with pytest.raises(ValueError, match="duplicate paired cell"):
        paired_binary_comparison(
            [*rows, rows[0]],
            full_method="full_pact",
            baseline="raw_open_loop",
            bootstrap_samples=10,
        )
    with pytest.raises(ValueError, match="episode sets differ"):
        paired_binary_comparison(
            rows[:-1],
            full_method="full_pact",
            baseline="raw_open_loop",
            bootstrap_samples=10,
        )
    unbalanced = [
        row
        for row in rows
        if not (row["task"] == "family_b" and row["seed"] == 4)
    ]
    with pytest.raises(ValueError, match="share one complete seed set"):
        paired_binary_comparison(
            unbalanced,
            full_method="full_pact",
            baseline="raw_open_loop",
            bootstrap_samples=10,
        )


def test_paired_grid_rejects_nonboolean_or_infrastructure_outcomes() -> None:
    nonboolean = paired_rows()
    nonboolean[0] = {**nonboolean[0], "success": "false"}
    with pytest.raises(ValueError, match="must be Boolean"):
        paired_binary_comparison(
            nonboolean,
            full_method="full_pact",
            baseline="raw_open_loop",
            bootstrap_samples=10,
        )
    infrastructure = paired_rows()
    infrastructure[0] = {**infrastructure[0], "infrastructure_failure": True}
    with pytest.raises(ValueError, match="infrastructure failure"):
        paired_binary_comparison(
            infrastructure,
            full_method="full_pact",
            baseline="raw_open_loop",
            bootstrap_samples=10,
        )


def test_wilson_interval_and_zero_event_bound_have_known_values() -> None:
    low, high = wilson_interval(8, 10)
    assert low == pytest.approx(0.4901624715)
    assert high == pytest.approx(0.9433178485)
    assert zero_event_upper_bound(100) == pytest.approx(0.0295130496)
    assert zero_event_upper_bound(1000) < zero_event_upper_bound(100)


@pytest.mark.parametrize(
    "call",
    [
        lambda: wilson_interval(1, 0),
        lambda: wilson_interval(2, 1),
        lambda: wilson_interval(0, 1, confidence=1.0),
        lambda: zero_event_upper_bound(0),
        lambda: zero_event_upper_bound(1, confidence=0.0),
    ],
)
def test_interval_functions_reject_invalid_inputs(call) -> None:
    with pytest.raises(ValueError):
        call()


def test_restoration_summary_reports_transaction_and_episode_levels() -> None:
    summary = restoration_summary(
        [
            {"restoration_attempts": 2, "restoration_passes": 2},
            {"restoration_attempts": 3, "restoration_passes": 2},
            {"restoration_attempts": 0, "restoration_passes": 0},
        ]
    )
    assert summary["episodes"] == 3
    assert summary["restoration_attempts"] == 5
    assert summary["restoration_passes"] == 4
    assert summary["restoration_rate"] == 0.8
    assert summary["episodes_with_any_restoration_failure"] == 1
    assert summary["episode_failure_rate"] == 1 / 3
    assert summary["restoration_wilson_interval"] is not None


def test_restoration_summary_handles_no_attempts_without_fake_uncertainty() -> None:
    summary = restoration_summary(
        [{"restoration_attempts": 0, "restoration_passes": 0}]
    )
    assert summary["restoration_rate"] is None
    assert summary["restoration_wilson_interval"] is None
    assert summary["episodes_with_any_restoration_failure"] == 0
    with pytest.raises(ValueError, match="cannot exceed attempts"):
        restoration_summary(
            [{"restoration_attempts": 1, "restoration_passes": 2}]
        )
    with pytest.raises(ValueError, match="nonnegative"):
        restoration_summary(
            [{"restoration_attempts": -1, "restoration_passes": -1}]
        )
