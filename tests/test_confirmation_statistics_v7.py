from __future__ import annotations

from pathlib import Path

import pytest

from inversereserve.studies.confirmation_statistics_v7 import (
    confirmation_comparisons,
    exact_paired_greater,
    holm_rejections,
)

ROOT = Path(__file__).resolve().parents[1]


def test_exact_paired_greater_matches_small_binomial_tails() -> None:
    assert exact_paired_greater(0, 0) == 1.0
    assert exact_paired_greater(6, 0) == pytest.approx(1 / 64)
    assert exact_paired_greater(5, 0) == pytest.approx(1 / 32)
    assert exact_paired_greater(4, 2) == pytest.approx(22 / 64)


def test_holm_rejections_are_step_down_and_adjusted() -> None:
    result = holm_rejections({"raw": 0.01, "no_cert": 0.04}, alpha=0.05)
    assert result["raw"]["rejected"] is True
    assert result["raw"]["holm_threshold"] == pytest.approx(0.025)
    assert result["raw"]["holm_adjusted_p"] == pytest.approx(0.02)
    assert result["no_cert"]["rejected"] is True
    assert result["no_cert"]["holm_threshold"] == pytest.approx(0.05)
    assert result["no_cert"]["holm_adjusted_p"] == pytest.approx(0.04)


def test_confirmation_comparisons_preserve_complete_paired_grid() -> None:
    rows = []
    for family in ("a", "b"):
        for seed in range(1, 7):
            for method in ("full", "raw", "no_cert"):
                rows.append(
                    {
                        "method": method,
                        "task": family,
                        "seed": seed,
                        "success": method == "full" or (method == "no_cert" and seed > 3),
                        "infrastructure_failure": False,
                    }
                )
    result = confirmation_comparisons(
        rows, full_method="full", baselines=("raw", "no_cert"), bootstrap_samples=100, bootstrap_seed=7
    )
    assert result["comparisons"]["raw"]["paired_episodes"] == 12
    assert result["comparisons"]["raw"]["discordant_full_success_baseline_failure"] == 12
    assert result["comparisons"]["no_cert"]["discordant_full_success_baseline_failure"] == 6
    assert result["comparisons"]["raw"]["holm"]["rejected"] is True
    assert result["comparisons"]["no_cert"]["holm"]["rejected"] is True
