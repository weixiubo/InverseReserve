"""Outcome-blind holdout successor for the passing navigation-v8 method.

This module opens no task state. It permits one protocol to be created only
from the exact passing V8 development artifact and preserves the original
six-task holdout without changing the V8 method.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from . import inversereserve_webarena_final_v1 as root_design
from . import inversereserve_webarena_navigation_dev_v8 as parent_design
from .webarena_exact_mutation_transfer_v1 import EXPECTED_HOLDOUT_GATES


CANDIDATE = "InverseReserve-WebArena-navigation-holdout-protocol-v9"
STATUS = "sealed_after_passing_v8_before_first_holdout_reset"
PARENT_PROTOCOL_RELATIVE = parent_design.PROTOCOL_RELATIVE
PARENT_PROTOCOL_SHA256 = (
    "e6dc3ab5d27eac167602f8167330f1564df03e325674863023aede85b889ff18"
)
PARENT_RESULT_RELATIVE = parent_design.RESULT_RELATIVE
PARENT_RESULT_SHA256 = (
    "91d07402034198ca0ee7c523bd8bc1181561bc6b29cee0dce25c1423718b5b7a"
)
PARENT_SOURCE_COMMIT = "868f91e4d653eb8807eec5c3abbf5b86e932abf0"
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/"
    "2026-07-18_inversereserve_webarena_navigation_holdout_v9_preregistration.md"
)
PROTOCOL_RELATIVE = (
    "validation/inversereserve_webarena_navigation_holdout_v9_protocol.json"
)
RESULT_RELATIVE = "validation/inversereserve_webarena_navigation_holdout_v9.json"
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_holdout_v9"
METHOD_ID = parent_design.METHOD_ID
DECISION_RULE = {
    "on_pass": (
        "report bounded InverseReserve exact-mutation transfer across the four "
        "frozen sites together with all retained predecessor outcomes"
    ),
    "on_failure": (
        "report the complete negative holdout without task replacement, gate "
        "relaxation, method adaptation, or another holdout"
    ),
}
NEW_SOURCE_PATHS = frozenset(
    {
        "ops/run_inversereserve_webarena_navigation_holdout_v9_resource_gate.sh",
        "scripts/inversereserve_webarena_navigation_holdout_v9.py",
        "scripts/seal_inversereserve_webarena_navigation_holdout_v9.py",
        "src/rcrps/inversereserve_webarena_navigation_holdout_v9.py",
        "tests/test_inversereserve_webarena_navigation_holdout_v9.py",
    }
)


def _validate_parent(
    parent_protocol: dict[str, Any],
    *,
    root_protocol: dict[str, Any],
) -> None:
    if (
        parent_protocol.get("candidate") != parent_design.CANDIDATE
        or parent_protocol.get("status") != parent_design.STATUS
        or parent_protocol.get("source_commit") != PARENT_SOURCE_COMMIT
        or parent_protocol.get("method_identity")
        != parent_design.METHOD_IDENTITY
    ):
        raise ValueError("navigation-v9 parent identity changed")
    if parent_protocol.get("development") != {
        "episodes": root_design.stage_manifest(root_design.DEVELOPMENT),
        "minimum_official_successes": 2,
        "expected_episodes": 3,
        "all_outcomes_retained": True,
        "official_evaluator_once_per_episode": True,
    }:
        raise ValueError("navigation-v9 parent development boundary changed")
    holdout = parent_protocol.get("embargoed_holdout")
    if not (
        isinstance(holdout, dict)
        and holdout.get("episodes")
        == root_design.stage_manifest(root_design.HOLDOUT)
        and holdout.get("opened") is False
        and holdout.get("authorized_by_this_protocol") is False
    ):
        raise ValueError("navigation-v9 parent holdout boundary changed")
    if parent_protocol.get("source_sha256") != parent_protocol.get(
        "execution", {}
    ).get("source_sha256"):
        raise ValueError("navigation-v9 parent source closure changed")
    if root_protocol.get("candidate") != "InverseReserve-WebArena-final-suite-protocol-v1":
        raise ValueError("navigation-v9 root protocol changed")


def development_authorizes_holdout(
    result: dict[str, Any], *, protocol_sha256: str
) -> bool:
    checks = result.get("checks")
    metrics = result.get("metrics", {})
    rows = result.get("episode_rows")
    claims = result.get("claim_manifest")
    return bool(
        result.get("candidate")
        == "InverseReserve-WebArena-navigation-development-v8"
        and result.get("status") == "development_complete"
        and result.get("passed") is True
        and result.get("protocol") == PARENT_PROTOCOL_RELATIVE
        and result.get("protocol_sha256") == protocol_sha256
        and result.get("source_commit") == PARENT_SOURCE_COMMIT
        and result.get("method_identity") == parent_design.METHOD_IDENTITY
        and result.get("partition") == root_design.DEVELOPMENT
        and result.get("development_states_opened") is True
        and result.get("holdout_states_opened") is False
        and result.get("development_task_ids") == [399, 449, 488]
        and result.get("complete_population") is True
        and result.get("embargoed_holdout_opened") is False
        and result.get("outcome_based_exclusion_allowed") is False
        and metrics.get("episodes") == 3
        and metrics.get("official_success") == 3
        and metrics.get("infrastructure_failures") == 0
        and metrics.get("unrecovered_action_errors") == 0
        and metrics.get("navigation_v8_joint_url_semantic_normalizations") == 1
        and metrics.get("navigation_v8_viewport_editor_bindings") == 1
        and isinstance(checks, dict)
        and checks
        and all(value is True for value in checks.values())
        and isinstance(rows, list)
        and len(rows) == 3
        and isinstance(claims, dict)
        and len(claims) == 3
    )


def required_source_paths(parent_protocol: dict[str, Any]) -> frozenset[str]:
    return frozenset(parent_protocol["source_sha256"]) | NEW_SOURCE_PATHS


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
    parent_result: dict[str, Any],
    parent_result_sha256: str,
    source_commit: str,
    source_sha256: dict[str, str],
    preregistration_sha256: str,
    created_utc: str,
) -> dict[str, Any]:
    _validate_parent(parent_protocol, root_protocol=root_protocol)
    if not development_authorizes_holdout(
        parent_result, protocol_sha256=PARENT_PROTOCOL_SHA256
    ):
        raise ValueError("navigation-v8 development does not authorize holdout")
    if parent_result_sha256 != PARENT_RESULT_SHA256:
        raise ValueError("navigation-v8 result hash changed")

    activation = {
        "primary_result": copy.deepcopy(
            parent_protocol["execution"]["suite_activation"]["primary_result"]
        ),
        "navigation_v8_protocol": {
            "path": PARENT_PROTOCOL_RELATIVE,
            "sha256": PARENT_PROTOCOL_SHA256,
        },
        "navigation_v8_development_result": {
            "path": PARENT_RESULT_RELATIVE,
            "sha256": parent_result_sha256,
        },
    }
    episodes = copy.deepcopy(parent_protocol["embargoed_holdout"]["episodes"])
    execution = copy.deepcopy(parent_protocol["execution"])
    execution.update(
        {
            "candidate": (
                "InverseReserve-WebArena-navigation-holdout-execution-v9"
            ),
            "partition": root_design.HOLDOUT,
            "source_commit": source_commit,
            "episodes": copy.deepcopy(episodes),
            "expected_episodes": len(episodes),
            "source_sha256": dict(sorted(source_sha256.items())),
            "preregistration": {
                "path": PREREGISTRATION_RELATIVE,
                "sha256": preregistration_sha256,
            },
            "holdout_gates": copy.deepcopy(EXPECTED_HOLDOUT_GATES),
            "decision_rule": copy.deepcopy(DECISION_RULE),
            "suite_activation": copy.deepcopy(activation),
        }
    )
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "source_commit": source_commit,
        "method_identity": copy.deepcopy(parent_design.METHOD_IDENTITY),
        "activation": activation,
        "preregistration": {
            "path": PREREGISTRATION_RELATIVE,
            "sha256": preregistration_sha256,
        },
        "holdout": {
            "episodes": episodes,
            "expected_episodes": 6,
            "minimum_official_successes": 5,
            "require_success_on_every_represented_site": True,
            "require_every_analysis_check_true": True,
            "all_outcomes_retained": True,
            "official_evaluator_once_per_episode": True,
        },
        "source_sha256": dict(sorted(source_sha256.items())),
        "execution": execution,
        "state_boundary": {
            "navigation_v8_development_opened": True,
            "original_holdout_opened": False,
            "separate_successor_protocol": True,
            "method_changed_after_v8_outcome": False,
            "outcome_based_task_replacement_allowed": False,
        },
        "outputs": {
            "run_root": RUN_ROOT_RELATIVE,
            "result": RESULT_RELATIVE,
        },
    }
    validate_protocol_shape(
        protocol,
        parent_protocol=parent_protocol,
        root_protocol=root_protocol,
        parent_result=parent_result,
    )
    return protocol


def validate_protocol_shape(
    protocol: dict[str, Any],
    *,
    parent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
    parent_result: dict[str, Any],
) -> None:
    _validate_parent(parent_protocol, root_protocol=root_protocol)
    if protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS:
        raise ValueError("unexpected navigation-v9 holdout identity")
    if re.fullmatch(r"[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is None:
        raise ValueError("navigation-v9 source commit is not immutable")
    if protocol.get("method_identity") != parent_design.METHOD_IDENTITY:
        raise ValueError("navigation-v9 changed the frozen V8 method")

    activation = protocol.get("activation")
    if not isinstance(activation, dict) or set(activation) != {
        "primary_result",
        "navigation_v8_protocol",
        "navigation_v8_development_result",
    }:
        raise ValueError("navigation-v9 activation lineage changed")
    if activation["primary_result"] != parent_protocol["execution"][
        "suite_activation"
    ]["primary_result"]:
        raise ValueError("navigation-v9 primary activation changed")
    if activation["navigation_v8_protocol"] != {
        "path": PARENT_PROTOCOL_RELATIVE,
        "sha256": PARENT_PROTOCOL_SHA256,
    }:
        raise ValueError("navigation-v9 parent protocol changed")
    if activation["navigation_v8_development_result"] != {
        "path": PARENT_RESULT_RELATIVE,
        "sha256": PARENT_RESULT_SHA256,
    }:
        raise ValueError("navigation-v9 parent result changed")
    if not development_authorizes_holdout(
        parent_result, protocol_sha256=PARENT_PROTOCOL_SHA256
    ):
        raise ValueError("navigation-v9 lacks a passing V8 activation")

    preregistration = protocol.get("preregistration")
    if not (
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch(
            r"[0-9a-f]{64}", str(preregistration.get("sha256", ""))
        )
    ):
        raise ValueError("navigation-v9 preregistration changed")

    episodes = root_design.stage_manifest(root_design.HOLDOUT)
    if protocol.get("holdout") != {
        "episodes": episodes,
        "expected_episodes": 6,
        "minimum_official_successes": 5,
        "require_success_on_every_represented_site": True,
        "require_every_analysis_check_true": True,
        "all_outcomes_retained": True,
        "official_evaluator_once_per_episode": True,
    }:
        raise ValueError("navigation-v9 holdout population or gate changed")
    if episodes != parent_protocol["embargoed_holdout"]["episodes"]:
        raise ValueError("navigation-v9 does not preserve the original holdout")

    source_sha256 = protocol.get("source_sha256")
    if not isinstance(source_sha256, dict) or set(source_sha256) != set(
        required_source_paths(parent_protocol)
    ):
        raise ValueError("navigation-v9 source closure changed")
    if any(
        re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
        for value in source_sha256.values()
    ):
        raise ValueError("navigation-v9 source hash is malformed")
    for relative, expected in parent_protocol["source_sha256"].items():
        if source_sha256.get(relative) != expected:
            raise ValueError(f"navigation-v9 changed V8 source: {relative}")

    execution = protocol.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("navigation-v9 execution view is absent")
    expected_changes = {
        "candidate",
        "partition",
        "source_commit",
        "episodes",
        "expected_episodes",
        "source_sha256",
        "preregistration",
        "decision_rule",
        "suite_activation",
        "holdout_gates",
    }
    for key, value in parent_protocol["execution"].items():
        if key not in expected_changes and execution.get(key) != value:
            raise ValueError(f"navigation-v9 changed frozen execution field: {key}")
    if execution.get("candidate") != (
        "InverseReserve-WebArena-navigation-holdout-execution-v9"
    ):
        raise ValueError("navigation-v9 execution identity changed")
    if execution.get("partition") != root_design.HOLDOUT:
        raise ValueError("navigation-v9 execution partition changed")
    if execution.get("source_commit") != protocol["source_commit"]:
        raise ValueError("navigation-v9 execution source changed")
    if execution.get("episodes") != episodes or execution.get(
        "expected_episodes"
    ) != 6:
        raise ValueError("navigation-v9 execution population changed")
    if execution.get("source_sha256") != source_sha256:
        raise ValueError("navigation-v9 execution source closure changed")
    if execution.get("preregistration") != preregistration:
        raise ValueError("navigation-v9 execution preregistration changed")
    if execution.get("holdout_gates") != EXPECTED_HOLDOUT_GATES:
        raise ValueError("navigation-v9 holdout integrity gates changed")
    if execution.get("decision_rule") != DECISION_RULE:
        raise ValueError("navigation-v9 decision rule changed")
    if execution.get("suite_activation") != activation:
        raise ValueError("navigation-v9 execution activation changed")

    if protocol.get("state_boundary") != {
        "navigation_v8_development_opened": True,
        "original_holdout_opened": False,
        "separate_successor_protocol": True,
        "method_changed_after_v8_outcome": False,
        "outcome_based_task_replacement_allowed": False,
    }:
        raise ValueError("navigation-v9 state boundary changed")
    if protocol.get("outputs") != {
        "run_root": RUN_ROOT_RELATIVE,
        "result": RESULT_RELATIVE,
    }:
        raise ValueError("navigation-v9 output paths changed")
