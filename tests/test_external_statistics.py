from __future__ import annotations

from pathlib import Path

from inversereserve.observations.preview_transaction import METHOD_ORDER
from inversereserve.studies.external_statistics import (
    BASELINE_METHODS,
    FULL_METHOD,
    evaluate_main_gate,
    exact_mcnemar,
    paired_comparison,
    select_strongest_baseline,
    summarize_all,
)

ROOT = Path(__file__).resolve().parents[1]


def episode(method: str, task: str, seed: int, success: bool) -> dict:
    restoration_attempts = 1 if method == FULL_METHOD else 0
    return {
        "method": method,
        "task": task,
        "seed": seed,
        "success": success,
        "infrastructure_failure": False,
        "wrong_irreversible_or_terminal_commits": 0,
        "unsafe_or_persistent_preview_actions": 0,
        "restoration_attempts": restoration_attempts,
        "restoration_passes": restoration_attempts,
        "target_evidence_discovered": success,
        "budget_usage": {
            "gui_actions": 1,
            "scroll_actions": 0,
            "restoration_cleanup_actions": restoration_attempts,
            "preview_transactions": restoration_attempts,
            "hover_probes": 0,
            "candidate_proposals": 1,
            "risk_forwards": 0,
            "binder_forwards": 0,
            "fullscreen_ocr_calls": 1,
            "crop_ocr_calls": 0,
            "wall_seconds": 1.0,
        },
    }


def synthetic_panel() -> list[dict]:
    rows = []
    for task in ("family_a", "family_b"):
        for seed in range(4):
            for method in METHOD_ORDER:
                if method == FULL_METHOD:
                    success = True
                elif method == "click_restore":
                    success = seed < 2
                elif method == "risk_only":
                    success = seed == 0
                else:
                    success = False
                rows.append(episode(method, task, seed, success))
    return rows


def test_complete_panel_summary_and_strongest_baseline() -> None:
    summaries = summarize_all(synthetic_panel(), METHOD_ORDER)
    assert summaries[FULL_METHOD]["macro_success"] == 1.0
    assert summaries[FULL_METHOD]["verified_restoration_rate"] == 1.0
    assert select_strongest_baseline(summaries) == "click_restore"
    assert set(BASELINE_METHODS) <= set(summaries)


def test_frozen_paired_statistics_and_gate() -> None:
    rows = synthetic_panel()
    summaries = summarize_all(rows, METHOD_ORDER)
    comparison = paired_comparison(
        rows, baseline="click_restore", bootstrap_samples=100, bootstrap_seed=270711
    )
    gate = evaluate_main_gate(summaries, comparison)
    assert comparison["paired_episodes"] == 8
    assert comparison["observed_macro_success_difference"] == 0.5
    assert comparison["bootstrap_95_percent_ci"][0] >= 0.0
    assert comparison["discordant_full_success_baseline_failure"] == 4
    assert comparison["discordant_full_failure_baseline_success"] == 0
    assert comparison["exact_mcnemar_two_sided_p"] == 0.125
    assert gate["passed"]


def test_exact_mcnemar_handles_no_discordance() -> None:
    assert exact_mcnemar(0, 0) == 1.0


def test_main_gate_rejects_one_unsafe_full_preview() -> None:
    rows = synthetic_panel()
    next((row for row in rows if row["method"] == FULL_METHOD))["unsafe_or_persistent_preview_actions"] = 1
    summaries = summarize_all(rows, METHOD_ORDER)
    comparison = paired_comparison(
        rows, baseline="click_restore", bootstrap_samples=10, bootstrap_seed=270711
    )
    gate = evaluate_main_gate(summaries, comparison)
    assert not gate["checks"]["unsafe_or_persistent_preview_actions"]
    assert not gate["passed"]
