"""Outcome-independent successor controls for exact-mutation transfer.

The successor first confirms its repaired execution/evaluation boundary on
the already-open development population.  Only that source-bound result may
authorize the still-unopened mechanism holdout.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Iterable

from inversereserve.adapters.webarena.webarena_verified_runtime_v1 import public_site_base_v1
from inversereserve.studies import webarena_exact_mutation_transfer_v1 as legacy
from inversereserve.studies.validation import require

_LEGACY_ANALYZE_TRANSFER_ROWS = legacy.analyze_transfer_rows
_LEGACY_VALIDATE_PROTOCOL_SHAPE = legacy.validate_protocol_shape
SUCCESSOR_AUDIT_RELATIVE = "paper/aaai27/notes/2026-07-13_webarena_pre_holdout_static_audit.md"
PREDECESSOR_PROTOCOL_RELATIVE = "validation/webarena_verified_exact_mutation_development_protocol_v5.json"
PREDECESSOR_RESULT_RELATIVE = "validation/webarena_verified_exact_mutation_development_v1.json"
DEVELOPMENT_RESULT_V2_RELATIVE = "validation/webarena_verified_exact_mutation_development_v2.json"
PACT_V10_EQUIVALENCE_RELATIVE = "validation/c453_pact_v10_trace_equivalence.json"
SUCCESSOR_CHANGES_V2 = {
    "evaluator_origins_derived_from_episode_ports": True,
    "reward_and_evaluator_info_structurally_isolated": True,
    "unresolved_failed_transactions_retained_and_gated": True,
    "evaluator_process_and_components_fail_closed": True,
    "pact_v10_recovery_and_commit_reservation": True,
    "pact_v10_c453_lineage_bound": True,
}
EXPECTED_DEVELOPMENT_GATES_V2 = {
    "minimum_official_successes": 2,
    "require_typed_transaction_when_target_form_reached": True,
    "require_controller_is_pact_v10": True,
    "require_success_implies_effective_certified_commit": True,
    "require_zero_parser_failures": True,
    "require_zero_action_errors": True,
    "require_zero_runtime_halts": True,
    "require_zero_wrong_terminal_commits": True,
    "require_zero_terminal_transactions": True,
    "require_zero_uncertified_commits": True,
    "require_zero_commit_effect_failures": True,
    "require_zero_inverse_reservation_stops": True,
    "require_exact_recovery_plus_commit_reservation": True,
    "require_zero_interrupt_repair_reservation_fallbacks": True,
    "require_repair_reservation_metrics_match_events": True,
    "require_all_attempted_restorations_pass": True,
    "require_zero_unresolved_failed_transactions": True,
    "require_zero_evaluator_nonzero_returncodes": True,
    "require_exact_official_evaluator_components": True,
    "require_zero_official_evaluator_component_errors": True,
}
EXPECTED_HOLDOUT_GATES_V2 = {
    **legacy.EXPECTED_HOLDOUT_GATES,
    "require_zero_unresolved_failed_transactions": True,
    "require_zero_evaluator_nonzero_returncodes": True,
    "require_exact_official_evaluator_components": True,
    "require_zero_official_evaluator_component_errors": True,
    "require_exact_recovery_plus_commit_reservation": True,
    "require_zero_interrupt_repair_reservation_fallbacks": True,
    "require_repair_reservation_metrics_match_events": True,
    "require_controller_is_pact_v10": True,
}
REQUIRED_SOURCE_PATHS_V2 = frozenset(
    {
        *legacy.REQUIRED_SOURCE_PATHS,
        "scripts/webarena_v1_predecessor_import_v2.py",
        "scripts/run_webarena_exact_mutation_v2_resource_gate.sh",
        "scripts/webarena_exact_mutation_transfer_protocol_v2.py",
        "scripts/webarena_exact_mutation_transfer_v2.py",
        "src/inversereserve/studies/webarena_exact_mutation_transfer_v2.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v2.py",
        "src/inversereserve/adapters/webarena/webarena_executor_v2.py",
        "src/inversereserve/controllers/pact_controller_v10.py",
    }
)
SITE_TOKENS = {
    "reddit": "__REDDIT__",
    "gitlab": "__GITLAB__",
    "shopping_admin": "__SHOPPING_ADMIN__",
    "shopping": "__SHOPPING__",
}
OFFICIAL_COMPONENTS = frozenset({"AgentResponseEvaluator", "NetworkEventEvaluator"})


def evaluator_config_v2(_protocol: dict[str, Any]) -> dict[str, Any]:
    """Bind URL normalization to the exact host ports in both populations."""
    by_site: dict[str, str] = {}
    for partition in ("adapter_development", "mechanism_holdout"):
        for episode in legacy.episode_manifest(partition):
            site = str(episode["site"])
            origin = public_site_base_v1(site, int(episode["site_port"]))
            previous = by_site.setdefault(site, origin)
            if previous != origin:
                raise ValueError("one site has inconsistent runtime origins")
    if set(by_site) != set(SITE_TOKENS):
        raise ValueError("evaluator config omits a represented site")
    return {
        "environments": {SITE_TOKENS[site]: {"urls": [origin]} for site, origin in sorted(by_site.items())}
    }


def official_component_audit_v2(result: object) -> dict[str, Any]:
    """Validate the official per-component result without task answers."""
    if not isinstance(result, dict):
        return {
            "identity_exact": False,
            "all_passed": False,
            "top_level_consistent": False,
            "error_count": 1,
            "components": [],
        }
    rows = result.get("evaluators_results")
    if not isinstance(rows, list) or not rows:
        return {
            "identity_exact": False,
            "all_passed": False,
            "top_level_consistent": False,
            "error_count": 1,
            "components": [],
        }
    normalized = []
    names = set()
    structurally_valid = True
    for row in rows:
        if not isinstance(row, dict):
            structurally_valid = False
            continue
        name = row.get("evaluator_name")
        status = row.get("status")
        score = row.get("score")
        if not _official_component_valid(name, status, score):
            structurally_valid = False
            continue
        names.add(name)
        normalized.append({"evaluator_name": name, "status": status, "score": float(score)})
    identity_exact = bool(
        structurally_valid
        and len(normalized) == len(rows)
        and (len(normalized) == len(OFFICIAL_COMPONENTS))
        and (names == OFFICIAL_COMPONENTS)
    )
    all_passed = _all_components_passed(identity_exact, normalized)
    top_status = result.get("status")
    top_score = result.get("score")
    top_structurally_valid = _official_component_audit_v2_top_structurally_valid(
        top_score=top_score, top_status=top_status
    )
    top_success = bool(top_structurally_valid and top_status == "success")
    return {
        "identity_exact": identity_exact,
        "all_passed": all_passed,
        "top_level_consistent": bool(
            identity_exact and top_structurally_valid and (top_success == all_passed)
        ),
        "error_count": sum((row["status"] == "error" for row in normalized)),
        "components": normalized,
    }


def _metric(row: dict[str, Any], name: str) -> int:
    return int(row.get("metrics", {}).get(name, 0))


def recovery_reservation_audit_v2(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Recompute both pre-forward and runtime PACT-v10 reservations."""
    rows = tuple(rows)
    forward_by_episode = _forward_events_by_episode(rows)
    forward_events = [event for events in forward_by_episode.values() for event in events]
    forward_exact = _recovery_reservation_audit_v2_forward_exact(forward_events=forward_events)
    forward_coverage = _forward_coverage_audit(forward_by_episode, rows)
    forward_fallbacks = sum((not bool(event.get("allowed")) for event in forward_events))
    forward_metrics_match = (
        sum((_metric(row, "inverse_reservation_audits") for row in rows)) == len(forward_events)
        and sum((_metric(row, "inverse_reservation_stops") for row in rows)) == forward_fallbacks
    )
    runtime_events = _runtime_repair_events(rows)
    runtime_exact = _runtime_exact_audit(runtime_events)
    event_fallbacks = sum((not bool(event.get("allowed")) for event in runtime_events))
    inverse_groundings = _inverse_groundings_audit(rows)
    metric_audits = sum((_metric(row, "interrupt_repair_reservation_audits") for row in rows))
    metric_fallbacks = sum((_metric(row, "interrupt_repair_reservation_fallbacks") for row in rows))
    metric_inverse = sum((_metric(row, "interrupt_repair_inverse_fallbacks") for row in rows))
    return {
        "forward_events": len(forward_events),
        "runtime_events": len(runtime_events),
        "runtime_fallbacks": event_fallbacks,
        "forward_fallbacks": forward_fallbacks,
        "inverse_groundings": inverse_groundings,
        "forward_exact": forward_exact and forward_coverage and forward_metrics_match,
        "runtime_exact": runtime_exact,
        "metrics_match_events": metric_audits == len(runtime_events)
        and metric_fallbacks == event_fallbacks
        and (metric_inverse == inverse_groundings),
    }


def _method_integrity_checks(rows: tuple[dict[str, Any], ...]) -> dict[str, bool]:
    return {
        "typed_transaction_when_target_form_reached": all(
            (
                row.get("typed_target_form_reached") is not True or _metric(row, "typed_transactions") >= 1
                for row in rows
            )
        ),
        "official_success_implies_effective_certified_commit": all(
            (
                row.get("official_evaluation", {}).get("passed") is not True
                or (
                    row.get("method_commit_effective") is True
                    and _metric(row, "typed_transactions") >= 1
                    and (_metric(row, "certified_commits") == 1)
                    and (_metric(row, "commit_effect_passes") == 1)
                )
                for row in rows
            )
        ),
        "zero_parser_failures": all((_metric(row, "planner_parse_failures") == 0 for row in rows)),
        "zero_action_errors": all((_metric(row, "action_errors") == 0 for row in rows)),
        "zero_runtime_halts": all((not bool(row.get("metrics", {}).get("runtime_halted")) for row in rows)),
        "zero_wrong_terminal_commits": all((_metric(row, "wrong_terminal_commits") == 0 for row in rows)),
        "zero_terminal_transactions": all((_metric(row, "terminal_transactions") == 0 for row in rows)),
        "zero_uncertified_commits": all((_metric(row, "uncertified_commits") == 0 for row in rows)),
        "zero_commit_effect_failures": all((_metric(row, "commit_effect_failures") == 0 for row in rows)),
        "zero_inverse_reservation_stops": all(
            (_metric(row, "inverse_reservation_stops") == 0 for row in rows)
        ),
        "all_attempted_restorations_pass": sum((_metric(row, "restoration_attempts") for row in rows))
        == sum((_metric(row, "restoration_passes") for row in rows)),
    }


def analyze_transfer_rows_v2(
    rows: Iterable[dict[str, Any]], *, partition: str, all_claims_complete: bool
) -> dict[str, Any]:
    """Add feedback, evaluator, and failed-transaction gates to both stages."""
    rows = tuple(rows)
    result = _LEGACY_ANALYZE_TRANSFER_ROWS(rows, partition=partition, all_claims_complete=all_claims_complete)
    unresolved_failed = sum(
        (
            row.get("method_commit_effective") is not True and bool(row.get("active_transactions_at_stop"))
            for row in rows
        )
    )
    nonzero_returncodes = sum((row.get("official_evaluation", {}).get("returncode") != 0 for row in rows))
    component_identity_failures = sum(
        (
            row.get("official_evaluation", {}).get("component_identity_exact") is not True
            or row.get("official_evaluation", {}).get("component_top_level_consistent") is not True
            for row in rows
        )
    )
    component_error_episodes = sum(
        (int(row.get("official_evaluation", {}).get("component_error_count", 1)) > 0 for row in rows)
    )
    recovery_audit = recovery_reservation_audit_v2(rows)
    result["metrics"] = {
        **result["metrics"],
        "unresolved_failed_transactions": unresolved_failed,
        "evaluator_nonzero_returncodes": nonzero_returncodes,
        "evaluator_component_identity_failures": component_identity_failures,
        "evaluator_component_error_episodes": component_error_episodes,
        "interrupt_repair_reservation_audits": sum(
            (_metric(row, "interrupt_repair_reservation_audits") for row in rows)
        ),
        "interrupt_repair_reservation_fallbacks": sum(
            (_metric(row, "interrupt_repair_reservation_fallbacks") for row in rows)
        ),
        "interrupt_repair_inverse_fallbacks": sum(
            (_metric(row, "interrupt_repair_inverse_fallbacks") for row in rows)
        ),
    }
    successor_checks = {
        "zero_unresolved_failed_transactions": unresolved_failed == 0,
        "zero_evaluator_nonzero_returncodes": nonzero_returncodes == 0,
        "exact_official_evaluator_components": component_identity_failures == 0,
        "zero_official_evaluator_component_errors": component_error_episodes == 0,
        "exact_recovery_plus_commit_reservation": recovery_audit["forward_exact"]
        and recovery_audit["runtime_exact"],
        "zero_interrupt_repair_reservation_fallbacks": result["metrics"][
            "interrupt_repair_reservation_fallbacks"
        ]
        == 0,
        "repair_reservation_metrics_match_events": recovery_audit["metrics_match_events"],
        "controller_is_pact_v10": all(
            (
                row.get("method_input", {}).get("controller_arm")
                == "full_pact_v10_webarena_exact_mutation_v2"
                for row in rows
            )
        ),
    }
    if partition == "adapter_development":
        successor_checks = {
            **_method_integrity_checks(rows),
            **successor_checks,
            "minimum_two_of_three_official_successes": result["metrics"]["official_success"]
            >= EXPECTED_DEVELOPMENT_GATES_V2["minimum_official_successes"],
        }
    elif partition != "mechanism_holdout":
        raise ValueError("unknown exact-mutation successor partition")
    result["checks"] = {**result["checks"], **successor_checks}
    result["recovery_reservation_audit"] = recovery_audit
    result["passed"] = all(result["checks"].values())
    return result


def _reference_exact(value: object, *, path: str) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"path", "sha256"}
        and (value.get("path") == path)
        and re.fullmatch("[0-9a-f]{64}", str(value.get("sha256")))
    )


def validate_protocol_shape_v2(protocol: dict[str, Any], *, partition: str) -> None:
    """Preserve V1 design while making the repaired development stage explicit."""
    development = partition == "adapter_development"
    require(not partition not in {"adapter_development", "mechanism_holdout"}, "V2 has an unknown partition")
    expected_candidate = (
        "WebArena-Verified-exact-mutation-development-protocol-v2"
        if development
        else "WebArena-Verified-exact-mutation-holdout-protocol-v2"
    )
    expected_status = (
        "sealed_after_v1_development_before_v2_execution"
        if development
        else "sealed_before_holdout_states_opened"
    )
    require(not protocol.get("candidate") != expected_candidate, "unexpected V2 transfer protocol candidate")
    require(not protocol.get("status") != expected_status, "unexpected V2 transfer protocol status")
    legacy_shape = copy.deepcopy(protocol)
    legacy_shape["candidate"] = (
        "WebArena-Verified-exact-mutation-development-protocol-v1"
        if development
        else "WebArena-Verified-exact-mutation-holdout-protocol-v1"
    )
    legacy_shape["status"] = (
        "sealed_before_development_states_opened" if development else "sealed_before_holdout_states_opened"
    )
    legacy_shape["holdout_gates"] = None if development else copy.deepcopy(legacy.EXPECTED_HOLDOUT_GATES)
    if development:
        legacy_shape["activation"] = None
    else:
        legacy_shape["activation"] = {
            "development_result": protocol.get("activation", {}).get("development_result")
        }
    _LEGACY_VALIDATE_PROTOCOL_SHAPE(legacy_shape, partition=partition)
    require(
        not protocol.get("development_gates") != EXPECTED_DEVELOPMENT_GATES_V2, "V2 development gates changed"
    )
    expected_holdout_gates = None if development else EXPECTED_HOLDOUT_GATES_V2
    require(not protocol.get("holdout_gates") != expected_holdout_gates, "V2 holdout gates changed")
    require(
        not protocol.get("successor_changes") != SUCCESSOR_CHANGES_V2, "V2 successor changes are incomplete"
    )
    audit = protocol.get("successor_audit")
    require(
        isinstance(audit, dict)
        and set(audit) == {"path", "sha256", "created_before_development_outcomes"}
        and (audit.get("path") == SUCCESSOR_AUDIT_RELATIVE)
        and re.fullmatch("[0-9a-f]{64}", str(audit.get("sha256")))
        and (audit.get("created_before_development_outcomes") is True),
        "V2 successor audit binding changed",
    )
    source_hashes = protocol.get("source_sha256")
    require(
        isinstance(source_hashes, dict) and REQUIRED_SOURCE_PATHS_V2.issubset(source_hashes),
        "V2 protocol omits successor source bindings",
    )
    activation = protocol.get("activation")
    if development:
        if not (
            isinstance(activation, dict)
            and set(activation)
            == {"predecessor_protocol", "predecessor_result", "pact_v10_trace_equivalence"}
            and _reference_exact(activation.get("predecessor_protocol"), path=PREDECESSOR_PROTOCOL_RELATIVE)
            and _reference_exact(activation.get("predecessor_result"), path=PREDECESSOR_RESULT_RELATIVE)
            and _reference_exact(
                activation.get("pact_v10_trace_equivalence"), path=PACT_V10_EQUIVALENCE_RELATIVE
            )
            and (
                protocol.get("state_boundary")
                == {"development_states_previously_opened_by_v1": True, "holdout_states_opened": False}
            )
        ):
            raise ValueError("V2 development predecessor binding changed")
    elif not (
        isinstance(activation, dict)
        and set(activation) == {"development_result", "pact_v10_trace_equivalence"}
        and _reference_exact(activation.get("development_result"), path=DEVELOPMENT_RESULT_V2_RELATIVE)
        and _reference_exact(activation.get("pact_v10_trace_equivalence"), path=PACT_V10_EQUIVALENCE_RELATIVE)
        and (
            protocol.get("state_boundary")
            == {"development_states_opened": True, "holdout_states_opened": False}
        )
    ):
        raise ValueError("V2 holdout development binding changed")


def successor_audit_path(root: Path) -> Path:
    path = (Path(root) / SUCCESSOR_AUDIT_RELATIVE).resolve()
    notes = (Path(root) / "paper" / "aaai27" / "notes").resolve()
    try:
        path.relative_to(notes)
    except ValueError as error:
        raise ValueError("successor audit escaped the paper notes") from error
    return path


def _official_component_audit_v2_top_structurally_valid(*, top_score: Any, top_status: Any) -> Any:
    """Compute top structurally valid from explicit study inputs."""
    return bool(
        isinstance(top_status, str)
        and top_status in {"success", "failure"}
        and (type(top_score) in {int, float})
        and (
            top_status == "success"
            and float(top_score) == 1.0
            or (top_status == "failure" and float(top_score) == 0.0)
        )
    )


def _recovery_reservation_audit_v2_forward_exact(*, forward_events: Any) -> Any:
    """Compute forward exact from explicit study inputs."""
    return all(
        (
            int(event.get("inverse_action_cost", -1)) >= 1
            and int(event.get("commit_action_cost", -1)) == 1
            and (int(event.get("interrupt_repair_action_cost", -1)) == 2)
            and (
                int(event.get("required_after_forward", -1))
                == int(event.get("inverse_action_cost", -1))
                + int(event.get("commit_action_cost", -1))
                + int(event.get("interrupt_repair_action_cost", -1))
            )
            and (
                bool(event.get("allowed"))
                == (
                    int(event.get("remaining_after_forward", -1))
                    >= int(event.get("required_after_forward", -1))
                )
            )
            and (event.get("reservation_version") == "PACT-v10-recovery-plus-commit")
            for event in forward_events
        )
    )


def _official_component_valid(name: Any, status: Any, score: Any) -> bool:
    return (
        isinstance(name, str)
        and name in OFFICIAL_COMPONENTS
        and isinstance(status, str)
        and (status in {"success", "failure", "error"})
        and (type(score) in {int, float})
        and (float(score) in {0.0, 1.0})
        and (
            status == "success"
            and float(score) == 1.0
            or (status in {"failure", "error"} and float(score) == 0.0)
        )
    )


def _runtime_exact_audit(runtime_events: Any) -> Any:
    return all(
        (
            int(event.get("repair_pair_actions", -1)) == 2
            and int(event.get("registered_inverse_reserve", -1)) >= 1
            and (
                bool(event.get("allowed"))
                == (
                    int(event.get("remaining_gui_actions", -1)) - int(event.get("repair_pair_actions", -1))
                    >= int(event.get("registered_inverse_reserve", -1))
                )
            )
            for event in runtime_events
        )
    )


def _forward_coverage_audit(forward_by_episode: Any, rows: Any) -> Any:
    return all(
        (
            row.get("typed_target_form_reached") is not True
            or len(forward_by_episode[str(row.get("episode", {}).get("episode_id"))]) == 1
            for row in rows
        )
    )


def _inverse_groundings_audit(rows: Any) -> Any:
    return sum(
        (
            event.get("type") == "compensator_grounding" and event.get("policy") == "inverse"
            for row in rows
            for event in row.get("runtime_events", [])
        )
    )


def _all_components_passed(identity_exact: Any, normalized: Any) -> Any:
    return bool(
        identity_exact and all((row["status"] == "success" and row["score"] == 1.0 for row in normalized))
    )


def _forward_events_by_episode(rows: Any) -> Any:
    return {
        str(row.get("episode", {}).get("episode_id")): [
            event for event in row.get("trace", []) if event.get("type") == "inverse_budget_reservation"
        ]
        for row in rows
    }


def _runtime_repair_events(rows: Any) -> Any:
    return [
        event
        for row in rows
        for event in row.get("runtime_events", [])
        if event.get("type") == "interrupt_repair_reservation"
    ]
