"""Paired statistics for frozen PACT controller comparisons.

The functions operate on complete `(family, seed, method)` grids.  Bootstrap
draws resample seeds as clusters shared across families, preserving dependence
between task families generated from the same seed.  No method name or result
schema from the historical RPS experiments is hard-coded here.
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from statistics import NormalDist
from typing import Any, Iterable

from .external_statistics import exact_mcnemar


def _mean(values: Iterable[float]) -> float:
    rows = tuple(values)
    if not rows:
        raise ValueError("mean requires at least one value")
    return sum(rows) / len(rows)


def _percentile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("percentile requires values")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def wilson_interval(
    successes: int,
    trials: int,
    *,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Two-sided Wilson score interval for a binomial proportion."""

    successes = int(successes)
    trials = int(trials)
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0 <= successes <= trials:
        raise ValueError("successes must lie between zero and trials")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between zero and one")
    alpha = 1.0 - confidence
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (proportion + z * z / (2.0 * trials)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1.0 - proportion) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return max(0.0, center - radius), min(1.0, center + radius)


def zero_event_upper_bound(
    trials: int,
    *,
    confidence: float = 0.95,
) -> float:
    """One-sided exact Clopper-Pearson upper bound after zero events."""

    trials = int(trials)
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must lie strictly between zero and one")
    alpha = 1.0 - confidence
    return 1.0 - alpha ** (1.0 / trials)


def _paired_grid(
    rows: Iterable[dict[str, Any]],
    *,
    full_method: str,
    baseline: str,
) -> tuple[
    dict[str, dict[tuple[str, int], bool]],
    dict[str, tuple[int, ...]],
]:
    if not full_method or not baseline or full_method == baseline:
        raise ValueError("comparison requires two distinct nonempty method names")
    grouped: dict[str, dict[tuple[str, int], bool]] = {
        full_method: {},
        baseline: {},
    }
    observed_methods = set()
    for row in rows:
        method = str(row["method"])
        if method not in grouped:
            continue
        observed_methods.add(method)
        family = str(row["task"])
        if not family.strip():
            raise ValueError("paired task family cannot be empty")
        if row.get("infrastructure_failure"):
            raise ValueError(f"unresolved infrastructure failure for {method}")
        if not isinstance(row["success"], bool):
            raise ValueError("paired success values must be Boolean")
        key = (family, int(row["seed"]))
        if key in grouped[method]:
            raise ValueError(f"duplicate paired cell for {method}: {key}")
        grouped[method][key] = bool(row["success"])
    if observed_methods != {full_method, baseline}:
        raise ValueError("paired comparison methods are incomplete")
    full_keys = set(grouped[full_method])
    if not full_keys or full_keys != set(grouped[baseline]):
        raise ValueError("paired comparison episode sets differ or are empty")

    seeds_by_family: dict[str, list[int]] = defaultdict(list)
    for family, seed in sorted(full_keys):
        seeds_by_family[family].append(seed)
    normalized = {
        family: tuple(sorted(seeds))
        for family, seeds in sorted(seeds_by_family.items())
    }
    reference = next(iter(normalized.values()))
    if any(seeds != reference for seeds in normalized.values()):
        raise ValueError("paired family grid must share one complete seed set")
    return grouped, normalized


def paired_binary_comparison(
    rows: Iterable[dict[str, Any]],
    *,
    full_method: str,
    baseline: str,
    bootstrap_samples: int = 10_000,
    bootstrap_seed: int = 270_727,
) -> dict[str, Any]:
    """Compare success on a complete paired grid with seed-cluster bootstrap."""

    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")
    grouped, seeds_by_family = _paired_grid(
        rows,
        full_method=full_method,
        baseline=baseline,
    )
    families = tuple(seeds_by_family)
    seeds = next(iter(seeds_by_family.values()))

    def difference(family: str, seed: int) -> float:
        key = (family, seed)
        return float(grouped[full_method][key]) - float(grouped[baseline][key])

    family_differences = {
        family: _mean(difference(family, seed) for seed in seeds)
        for family in families
    }
    task_weighted_difference = _mean(
        difference(family, seed) for family in families for seed in seeds
    )
    macro_difference = _mean(family_differences.values())

    positive = negative = 0
    for family in families:
        for seed in seeds:
            full = grouped[full_method][(family, seed)]
            base = grouped[baseline][(family, seed)]
            positive += int(full and not base)
            negative += int(base and not full)

    rng = random.Random(int(bootstrap_seed))
    bootstrap = []
    for _ in range(int(bootstrap_samples)):
        sampled_seeds = tuple(seeds[rng.randrange(len(seeds))] for _ in seeds)
        bootstrap.append(
            _mean(
                _mean(difference(family, seed) for seed in sampled_seeds)
                for family in families
            )
        )

    return {
        "full_method": full_method,
        "baseline": baseline,
        "families": list(families),
        "seeds": list(seeds),
        "paired_episodes": len(families) * len(seeds),
        "observed_task_weighted_success_difference": task_weighted_difference,
        "observed_macro_success_difference": macro_difference,
        "observed_family_differences": family_differences,
        "discordant_full_success_baseline_failure": positive,
        "discordant_full_failure_baseline_success": negative,
        "net_paired_successes": positive - negative,
        "exact_mcnemar_two_sided_p": exact_mcnemar(positive, negative),
        "bootstrap_unit": "seed cluster shared across families",
        "bootstrap_samples": int(bootstrap_samples),
        "bootstrap_seed": int(bootstrap_seed),
        "bootstrap_mean": _mean(bootstrap),
        "bootstrap_95_percent_ci": [
            _percentile(bootstrap, 0.025),
            _percentile(bootstrap, 0.975),
        ],
    }


def restoration_summary(
    rows: Iterable[dict[str, Any]],
    *,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Report restoration both per transaction and as any episode failure."""

    rows = tuple(rows)
    if not rows:
        raise ValueError("restoration summary requires episodes")
    normalized = []
    for row in rows:
        attempts = int(row["restoration_attempts"])
        passes = int(row["restoration_passes"])
        if attempts < 0 or passes < 0 or passes > attempts:
            raise ValueError(
                "restoration counts must be nonnegative and passes cannot exceed attempts"
            )
        normalized.append((attempts, passes))
    attempts = sum(row[0] for row in normalized)
    passes = sum(row[1] for row in normalized)
    failed_episodes = sum(
        passes < attempts for attempts, passes in normalized
    )
    interval = (
        wilson_interval(passes, attempts, confidence=confidence)
        if attempts
        else None
    )
    return {
        "episodes": len(rows),
        "restoration_attempts": attempts,
        "restoration_passes": passes,
        "restoration_rate": passes / attempts if attempts else None,
        "restoration_wilson_interval": list(interval) if interval else None,
        "episodes_with_any_restoration_failure": failed_episodes,
        "episode_failure_rate": failed_episodes / len(rows),
        "confidence": confidence,
    }
