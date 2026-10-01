"""Declarative boundary for the post-failure WebArena navigation development."""

from __future__ import annotations

import copy
import re
from typing import Any

from . import inversereserve_webarena_final_v1 as parent_design


CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v2"
STATUS = "sealed_after_v1_failure_before_v2_development_reset"
PARENT_PROTOCOL_RELATIVE = (
    "validation/inversereserve_webarena_final_protocol_v1.json"
)
PARENT_PROTOCOL_SHA256 = (
    "bd39bc4831a1a0e45bf2dd388b238d0f3041aeabcae5311dd94e8c5747085f6c"
)
FAILED_DEVELOPMENT_RELATIVE = (
    "validation/inversereserve_webarena_final_development_v1.json"
)
FAILED_DEVELOPMENT_SHA256 = (
    "925264a694d7ba866dc0017842cc76b6413f68b5939410d8c4d647fb09c3b3fd"
)
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/"
    "2026-07-18_inversereserve_webarena_navigation_v2_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v2"
RESULT_RELATIVE = (
    "validation/inversereserve_webarena_navigation_development_v2.json"
)
PROTOCOL_RELATIVE = (
    "validation/inversereserve_webarena_navigation_dev_v2_protocol.json"
)
METHOD_ID = "full_pact_v13_webarena_exact_mutation_nav2"
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v2.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v2.py",
        "src/rcrps/inversereserve_webarena_navigation_dev_v2.py",
        "src/rcrps/webarena_exact_mutation_agent_v13_nav2.py",
        "src/rcrps/webarena_public_navigation_v2.py",
        "tests/test_inversereserve_webarena_navigation_dev_v2.py",
        "tests/test_webarena_public_navigation_v2.py",
    }
)


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    source_commit: str,
    source_sha256: dict[str, str],
    preregistration_sha256: str,
    created_utc: str,
) -> dict[str, Any]:
    parent_design.validate_protocol_shape(parent_protocol)
    execution = parent_design.execution_protocol(
        parent_protocol,
        parent_design.DEVELOPMENT,
    )
    execution["candidate"] = (
        "InverseReserve-WebArena-navigation-development-execution-v2"
    )
    execution["source_commit"] = source_commit
    execution["source_sha256"] = dict(sorted(source_sha256.items()))
    execution["decision_rule"] = {
        "on_pass": (
            "freeze one successor protocol over the still-unopened original "
            "holdout before its first reset"
        ),
        "on_failure": (
            "preserve the complete development result; the original holdout "
            "remains unopened and unauthorized"
        ),
    }
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "source_commit": source_commit,
        "method_identity": {
            "paper_name": "InverseReserve",
            "mutation_runtime": (
                "full_pact_v13_webarena_exact_mutation_v2"
            ),
            "navigation_runtime": "public_navigation_v2",
            "controller_arm": METHOD_ID,
            "mutation_path_changed_after_primary_result": False,
        },
        "learned_from": {
            "parent_protocol": {
                "path": PARENT_PROTOCOL_RELATIVE,
                "sha256": PARENT_PROTOCOL_SHA256,
            },
            "failed_development": {
                "path": FAILED_DEVELOPMENT_RELATIVE,
                "sha256": FAILED_DEVELOPMENT_SHA256,
                "official_successes": 0,
                "episodes": 3,
                "failure": "public base navigator abstained",
            },
            "permitted_change": (
                "public candidate coverage, bounded public context, and "
                "navigation prompt only"
            ),
        },
        "preregistration": {
            "path": PREREGISTRATION_RELATIVE,
            "sha256": preregistration_sha256,
        },
        "development": {
            "episodes": parent_design.stage_manifest(
                parent_design.DEVELOPMENT
            ),
            "minimum_official_successes": 2,
            "expected_episodes": 3,
            "all_outcomes_retained": True,
            "official_evaluator_once_per_episode": True,
        },
        "embargoed_holdout": {
            "episodes": parent_design.stage_manifest(parent_design.HOLDOUT),
            "opened": False,
            "authorized_by_this_protocol": False,
        },
        "source_sha256": dict(sorted(source_sha256.items())),
        "execution": execution,
        "outputs": {
            "run_root": RUN_ROOT_RELATIVE,
            "result": RESULT_RELATIVE,
        },
    }
    validate_protocol_shape(protocol, parent_protocol=parent_protocol)
    return protocol


def validate_protocol_shape(
    protocol: dict[str, Any],
    *,
    parent_protocol: dict[str, Any],
) -> None:
    parent_design.validate_protocol_shape(parent_protocol)
    if protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS:
        raise ValueError("unexpected WebArena navigation development identity")
    if re.fullmatch(r"[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is None:
        raise ValueError("navigation development source commit is not immutable")
    if protocol.get("method_identity") != {
        "paper_name": "InverseReserve",
        "mutation_runtime": "full_pact_v13_webarena_exact_mutation_v2",
        "navigation_runtime": "public_navigation_v2",
        "controller_arm": METHOD_ID,
        "mutation_path_changed_after_primary_result": False,
    }:
        raise ValueError("navigation development method identity changed")
    if protocol.get("learned_from") != {
        "parent_protocol": {
            "path": PARENT_PROTOCOL_RELATIVE,
            "sha256": PARENT_PROTOCOL_SHA256,
        },
        "failed_development": {
            "path": FAILED_DEVELOPMENT_RELATIVE,
            "sha256": FAILED_DEVELOPMENT_SHA256,
            "official_successes": 0,
            "episodes": 3,
            "failure": "public base navigator abstained",
        },
        "permitted_change": (
            "public candidate coverage, bounded public context, and "
            "navigation prompt only"
        ),
    }:
        raise ValueError("navigation development failure lineage changed")
    preregistration = protocol.get("preregistration")
    if not (
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch(
            r"[0-9a-f]{64}", str(preregistration.get("sha256", ""))
        )
    ):
        raise ValueError("navigation development preregistration changed")
    if protocol.get("development") != {
        "episodes": parent_design.stage_manifest(parent_design.DEVELOPMENT),
        "minimum_official_successes": 2,
        "expected_episodes": 3,
        "all_outcomes_retained": True,
        "official_evaluator_once_per_episode": True,
    }:
        raise ValueError("navigation development population or gate changed")
    if protocol.get("embargoed_holdout") != {
        "episodes": parent_design.stage_manifest(parent_design.HOLDOUT),
        "opened": False,
        "authorized_by_this_protocol": False,
    }:
        raise ValueError("navigation development holdout embargo changed")
    source_sha256 = protocol.get("source_sha256")
    required_sources = set(parent_protocol["source_sha256"]) | set(
        NEW_SOURCE_PATHS
    )
    if not isinstance(source_sha256, dict) or set(source_sha256) != required_sources:
        raise ValueError("navigation development source closure changed")
    if any(
        re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
        for value in source_sha256.values()
    ):
        raise ValueError("navigation development source hash is malformed")
    execution = protocol.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("navigation development execution view is absent")
    if execution.get("partition") != parent_design.DEVELOPMENT:
        raise ValueError("navigation development partition changed")
    if execution.get("episodes") != parent_design.stage_manifest(
        parent_design.DEVELOPMENT
    ):
        raise ValueError("navigation development execution population changed")
    if execution.get("source_commit") != protocol["source_commit"]:
        raise ValueError("navigation development execution source changed")
    if execution.get("source_sha256") != source_sha256:
        raise ValueError("navigation development execution closure changed")
    parent_execution = parent_design.execution_protocol(
        parent_protocol,
        parent_design.DEVELOPMENT,
    )
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_execution.items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation development changed frozen field: {key}")
    if protocol.get("outputs") != {
        "run_root": RUN_ROOT_RELATIVE,
        "result": RESULT_RELATIVE,
    }:
        raise ValueError("navigation development outputs changed")
