"""Prestart-corrected prospective validation of host-requested handoff."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from inversereserve.studies import inversereserve_exogenous_handoff_v1 as v1
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-exogenous-handoff-v2"
STATUS = "frozen_after_v1_prestart_template_date_supersession_before_any_seed_39001_through_39020_reset"
CHAT_TEMPLATE_DATE = "21 July 2026"
DEPTH_ONE = v1.DEPTH_ONE
DEPTH_TWO = v1.DEPTH_TWO
ARMS = v1.ARMS
DRIVERS = v1.DRIVERS
SEEDS = v1.SEEDS
TASK_FAMILIES = v1.TASK_FAMILIES
TASK_BUDGETS = v1.TASK_BUDGETS
COMMON_BUDGETS = v1.COMMON_BUDGETS
GENERATION = v1.GENERATION
RUNTIME_DEPLOYMENT = v1.RUNTIME_DEPLOYMENT
PLANNER_MODEL = {
    **v1.PLANNER_MODEL,
    "snapshot_files_sha256": dict(v1.PLANNER_MODEL["snapshot_files_sha256"]),
    "chat_template_date": CHAT_TEMPLATE_DATE,
}
MINIMUM_DEPTH_TWO_HANDOFFS = v1.MINIMUM_DEPTH_TWO_HANDOFFS
MINIMUM_DEPTH_TWO_FAMILIES = v1.MINIMUM_DEPTH_TWO_FAMILIES
MINIMUM_TOTAL_HANDOFFS = v1.MINIMUM_TOTAL_HANDOFFS
OUTCOME_DEFINITIONS = v1.OUTCOME_DEFINITIONS
PRIMARY_QUESTION = v1.PRIMARY_QUESTION
VALIDITY_GATES = v1.VALIDITY_GATES
DECISION_RULE = v1.DECISION_RULE
SELECTION_DISCLOSURE = {
    **v1.SELECTION_DISCLOSURE,
    "v1_superseded_before_any_seed_reset": True,
    "successor_change_is_template_date_pin_only": True,
}
PRESTART_SUPERSESSION = {
    "superseded_candidate": v1.CANDIDATE,
    "protocol": "runs/inversereserve_exogenous_handoff_v1/protocol.json",
    "protocol_sha256": "11a4590bc4c2933cef7802c3aaf9e05cb1cc5634bc8bf9795d970c02e8bfab87",
    "scientific_source_commit": "2d4e8ec0b5f9643c9e304483da31474bd0ea51e8",
    "claims_opened": 0,
    "episodes_opened": 0,
    "scientific_outcome_observed": False,
    "failure_logs": [
        {
            "path": "runs/inversereserve_exogenous_handoff_v1/prestart_infrastructure_rejection_001.log",
            "sha256": "40dcc7111c776a036f0872b5401922f46831dd03077cb5b7d195b99dc768d593",
            "reason": "frozen external repositories were not mounted",
        },
        {
            "path": "runs/inversereserve_exogenous_handoff_v1/prestart_infrastructure_rejection_002.log",
            "sha256": "d38cc156c829fce709b1e3f9d69841a8aa7d555f4a4b602996044a6d4702af2e",
            "reason": "the system Python lacked the frozen torch runtime",
        },
        {
            "path": "runs/inversereserve_exogenous_handoff_v1/prestart_infrastructure_rejection_003.log",
            "sha256": "2ac86ecf034cc55bb34812ccd9d0f70d8db002e4dad0e025b561ee547e6a115d",
            "reason": "the chat template injected the current date instead of the date used by the passing predecessor runtime",
        },
    ],
    "successor_change": "freeze the chat-template date to the predecessor's exact rendered prompt; tasks, seeds, interventions, model files, generation, budgets, validity gates, and decision rule are unchanged",
}


def _as_v1_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    translated = deepcopy(protocol)
    translated["candidate"] = v1.CANDIDATE
    translated["status"] = v1.STATUS
    translated["planner_model"] = deepcopy(v1.PLANNER_MODEL)
    translated["selection_disclosure"] = dict(v1.SELECTION_DISCLOSURE)
    translated.pop("prestart_supersession", None)
    return translated


def task_records() -> list[dict[str, Any]]:
    return v1.task_records()


def expected_episodes() -> int:
    return v1.expected_episodes()


def build_protocol(**kwargs: Any) -> dict[str, Any]:
    protocol = v1.build_protocol(**kwargs)
    protocol["candidate"] = CANDIDATE
    protocol["status"] = STATUS
    protocol["planner_model"] = deepcopy(PLANNER_MODEL)
    protocol["selection_disclosure"] = dict(SELECTION_DISCLOSURE)
    protocol["prestart_supersession"] = deepcopy(PRESTART_SUPERSESSION)
    validate_protocol(protocol)
    return protocol


def validate_protocol(protocol: dict[str, Any]) -> None:
    require(not protocol.get("candidate") != CANDIDATE, "unexpected exogenous-handoff successor candidate")
    require(not protocol.get("status") != STATUS, "unexpected exogenous-handoff successor status")
    require(
        not protocol.get("planner_model") != PLANNER_MODEL,
        "exogenous-handoff successor model contract changed",
    )
    require(
        not protocol.get("selection_disclosure") != SELECTION_DISCLOSURE,
        "exogenous-handoff successor disclosure changed",
    )
    require(
        not protocol.get("prestart_supersession") != PRESTART_SUPERSESSION,
        "exogenous-handoff prestart supersession changed",
    )
    v1.validate_protocol(_as_v1_protocol(protocol))


def episode_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_protocol(protocol)
    return v1.episode_manifest(_as_v1_protocol(protocol))


def arm_order_counts(protocol: dict[str, Any]) -> dict[str, dict[int, int]]:
    validate_protocol(protocol)
    return v1.arm_order_counts(_as_v1_protocol(protocol))


def summarize_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return v1.summarize_rows(rows)


def analyze_rows(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any], *, all_claims_complete: bool
) -> dict[str, Any]:
    validate_protocol(protocol)
    return v1.analyze_rows(rows, _as_v1_protocol(protocol), all_claims_complete=all_claims_complete)
