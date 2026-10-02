"""Preregisterable paired inference helpers for the PACT-v7 confirmation."""

from __future__ import annotations

import math
from typing import Any, Iterable

from inversereserve.studies.pact_statistics import paired_binary_comparison


def exact_paired_greater(positive: int, negative: int) -> float:
    """One-sided exact sign/McNemar p-value for positive > negative."""

    positive = int(positive)
    negative = int(negative)
    if positive < 0 or negative < 0:
        raise ValueError("discordant counts must be nonnegative")
    discordant = positive + negative
    if discordant == 0:
        return 1.0
    return sum(math.comb(discordant, value) for value in range(positive, discordant + 1)) / (2**discordant)


def holm_rejections(p_values: dict[str, float], *, alpha: float = 0.05) -> dict[str, dict[str, Any]]:
    """Return fixed-family Holm step-down decisions and adjusted p-values."""

    if not p_values:
        raise ValueError("Holm correction requires at least one hypothesis")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must lie strictly between zero and one")
    if any(not 0.0 <= float(value) <= 1.0 for value in p_values.values()):
        raise ValueError("p-values must lie in [0, 1]")
    ordered = sorted((float(value), str(name)) for name, value in p_values.items())
    count = len(ordered)
    rejected_so_far = True
    running_adjusted = 0.0
    output: dict[str, dict[str, Any]] = {}
    for index, (p_value, name) in enumerate(ordered):
        multiplier = count - index
        threshold = alpha / multiplier
        rejected = bool(rejected_so_far and p_value <= threshold)
        rejected_so_far = rejected_so_far and rejected
        running_adjusted = max(running_adjusted, min(1.0, p_value * multiplier))
        output[name] = {
            "raw_p": p_value,
            "holm_rank": index + 1,
            "holm_threshold": threshold,
            "holm_adjusted_p": running_adjusted,
            "rejected": rejected,
        }
    return output


def confirmation_comparisons(
    rows: Iterable[dict[str, Any]],
    *,
    full_method: str,
    baselines: tuple[str, ...],
    bootstrap_samples: int,
    bootstrap_seed: int,
    alpha: float = 0.05,
) -> dict[str, Any]:
    rows = tuple(rows)
    comparisons = {}
    p_values = {}
    for baseline in baselines:
        comparison = paired_binary_comparison(
            rows,
            full_method=full_method,
            baseline=baseline,
            bootstrap_samples=bootstrap_samples,
            bootstrap_seed=bootstrap_seed,
        )
        one_sided = exact_paired_greater(
            comparison["discordant_full_success_baseline_failure"],
            comparison["discordant_full_failure_baseline_success"],
        )
        comparison["exact_mcnemar_one_sided_full_greater_p"] = one_sided
        comparisons[baseline] = comparison
        p_values[baseline] = one_sided
    holm = holm_rejections(p_values, alpha=alpha)
    for baseline in baselines:
        comparisons[baseline]["holm"] = holm[baseline]
    return {
        "full_method": full_method,
        "baselines": list(baselines),
        "alpha": alpha,
        "multiplicity": "Holm step-down over the two frozen paired comparisons",
        "comparisons": comparisons,
    }
