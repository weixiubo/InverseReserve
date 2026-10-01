"""Sealed boundary for post-navigation-v7 WebArena development V8."""

from __future__ import annotations

import copy
import re
from typing import Any

from . import inversereserve_webarena_final_v1 as root_design
from . import inversereserve_webarena_navigation_dev_v7 as parent_design


CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v8"
STATUS = "sealed_after_v7_failure_before_v8_development_reset"
ROOT_PROTOCOL_RELATIVE = parent_design.ROOT_PROTOCOL_RELATIVE
ROOT_PROTOCOL_SHA256 = parent_design.ROOT_PROTOCOL_SHA256
GREAT_GREAT_GREAT_GREAT_GRANDPARENT_PROTOCOL_RELATIVE = (
    parent_design.GREAT_GREAT_GREAT_GRANDPARENT_PROTOCOL_RELATIVE
)
GREAT_GREAT_GREAT_GREAT_GRANDPARENT_PROTOCOL_SHA256 = (
    parent_design.GREAT_GREAT_GREAT_GRANDPARENT_PROTOCOL_SHA256
)
GREAT_GREAT_GREAT_GRANDPARENT_PROTOCOL_RELATIVE = (
    parent_design.GREAT_GREAT_GRANDPARENT_PROTOCOL_RELATIVE
)
GREAT_GREAT_GREAT_GRANDPARENT_PROTOCOL_SHA256 = (
    parent_design.GREAT_GREAT_GRANDPARENT_PROTOCOL_SHA256
)
GREAT_GREAT_GRANDPARENT_PROTOCOL_RELATIVE = (
    parent_design.GREAT_GRANDPARENT_PROTOCOL_RELATIVE
)
GREAT_GREAT_GRANDPARENT_PROTOCOL_SHA256 = (
    parent_design.GREAT_GRANDPARENT_PROTOCOL_SHA256
)
GREAT_GRANDPARENT_PROTOCOL_RELATIVE = (
    parent_design.GRANDPARENT_PROTOCOL_RELATIVE
)
GREAT_GRANDPARENT_PROTOCOL_SHA256 = (
    parent_design.GRANDPARENT_PROTOCOL_SHA256
)
GRANDPARENT_PROTOCOL_RELATIVE = parent_design.PARENT_PROTOCOL_RELATIVE
GRANDPARENT_PROTOCOL_SHA256 = parent_design.PARENT_PROTOCOL_SHA256
PARENT_PROTOCOL_RELATIVE = parent_design.PROTOCOL_RELATIVE
PARENT_PROTOCOL_SHA256 = (
    "8c69e09642b3ed38e93d639d861437b015f62d3880f4c890bad40a2316d55fe0"
)
FAILED_DEVELOPMENT_RELATIVE = parent_design.RESULT_RELATIVE
FAILED_DEVELOPMENT_SHA256 = (
    "eb235bbc426aac187eb4de63e59c07b1a0130bf154156d8a783f81c7a57ff406"
)
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/"
    "2026-07-18_inversereserve_webarena_navigation_v8_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v8"
RESULT_RELATIVE = (
    "validation/inversereserve_webarena_navigation_development_v8.json"
)
PROTOCOL_RELATIVE = (
    "validation/inversereserve_webarena_navigation_dev_v8_protocol.json"
)
METHOD_ID = "full_pact_v18_webarena_exact_mutation_nav8"
METHOD_IDENTITY = {
    "paper_name": "InverseReserve",
    "mutation_runtime": "pact_v13_exact_mutation_public_surface_v6",
    "navigation_runtime": "public_navigation_v6",
    "typed_value_runtime": "joint_public_url_semantics_v6",
    "editor_surface_runtime": "frozen_bounded_semantic_viewport_editor_v5",
    "observation_runtime": "indexed_semantic_snapshot_v1",
    "executor_runtime": "reward_isolated_click_no_wait_v3",
    "controller_arm": METHOD_ID,
    "mutation_path_changed_after_v7_result": True,
    "navigation_path_changed_after_v7_result": False,
    "post_failure_development_adaptation": True,
}
LEARNED_FROM = {
    "parent_protocol": {
        "path": PARENT_PROTOCOL_RELATIVE,
        "sha256": PARENT_PROTOCOL_SHA256,
    },
    "failed_development": {
        "path": FAILED_DEVELOPMENT_RELATIVE,
        "sha256": FAILED_DEVELOPMENT_SHA256,
        "official_successes": 2,
        "episodes": 3,
    },
    "public_failure_diagnosis": {
        "gitlab": (
            "the complete v7 trace uniquely bound the visible Website url "
            "field and committed the verbatim bare hostname; its public DOM "
            "type was text, so the frozen type=url rule did not apply and the "
            "official evaluator rejected the retained bare hostname"
        ),
        "other_development_episodes": (
            "tasks 399 and 488 both succeeded officially, including the "
            "frozen bounded viewport-editor mechanism on task 488"
        ),
    },
    "permitted_change": (
        "prepend https only to one syntactically valid bare hostname derived "
        "verbatim from the goal when both the exact mutation clause and the "
        "uniquely bound public input expose url, website, or homepage "
        "semantics; retain every frozen V5 mutation and V6 navigation rule"
    ),
}
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v8.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v8.py",
        "src/rcrps/inversereserve_webarena_navigation_dev_v8.py",
        "src/rcrps/webarena_exact_mutation_agent_v18_nav8.py",
        "src/rcrps/webarena_exact_mutation_v6.py",
        "tests/test_inversereserve_webarena_navigation_dev_v8.py",
        "tests/test_webarena_exact_mutation_v6.py",
    }
)


DECISION_RULE = {
    "on_pass": (
        "freeze an independent navigation-v8 holdout protocol over the "
        "still-unopened original holdout before its first reset"
    ),
    "on_failure": (
        "preserve the complete v8 development result; the original holdout "
        "remains unopened and unauthorized"
    ),
}


def _validate_parent(
    parent_protocol: dict[str, Any],
    *,
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    great_great_grandparent_protocol: dict[str, Any],
    great_great_great_grandparent_protocol: dict[str, Any],
    great_great_great_great_grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
) -> None:
    parent_design.validate_protocol_shape(
        parent_protocol,
        parent_protocol=grandparent_protocol,
        grandparent_protocol=great_grandparent_protocol,
        great_grandparent_protocol=great_great_grandparent_protocol,
        great_great_grandparent_protocol=(
            great_great_great_grandparent_protocol
        ),
        great_great_great_grandparent_protocol=(
            great_great_great_great_grandparent_protocol
        ),
        root_protocol=root_protocol,
    )
    if parent_protocol.get("source_commit") != (
        "79feb6db1051b2d6cc5804b9b43a7e885704459d"
    ):
        raise ValueError("navigation-v7 source commit changed")


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    great_great_grandparent_protocol: dict[str, Any],
    great_great_great_grandparent_protocol: dict[str, Any],
    great_great_great_great_grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
    source_commit: str,
    source_sha256: dict[str, str],
    preregistration_sha256: str,
    created_utc: str,
) -> dict[str, Any]:
    _validate_parent(
        parent_protocol,
        grandparent_protocol=grandparent_protocol,
        great_grandparent_protocol=great_grandparent_protocol,
        great_great_grandparent_protocol=great_great_grandparent_protocol,
        great_great_great_grandparent_protocol=(
            great_great_great_grandparent_protocol
        ),
        great_great_great_great_grandparent_protocol=(
            great_great_great_great_grandparent_protocol
        ),
        root_protocol=root_protocol,
    )
    execution = copy.deepcopy(parent_protocol["execution"])
    execution["candidate"] = (
        "InverseReserve-WebArena-navigation-development-execution-v8"
    )
    execution["source_commit"] = source_commit
    execution["source_sha256"] = dict(sorted(source_sha256.items()))
    execution["decision_rule"] = copy.deepcopy(DECISION_RULE)
    protocol = {
        "candidate": CANDIDATE,
        "status": STATUS,
        "created_utc": created_utc,
        "source_commit": source_commit,
        "method_identity": copy.deepcopy(METHOD_IDENTITY),
        "learned_from": copy.deepcopy(LEARNED_FROM),
        "preregistration": {
            "path": PREREGISTRATION_RELATIVE,
            "sha256": preregistration_sha256,
        },
        "development": copy.deepcopy(parent_protocol["development"]),
        "embargoed_holdout": copy.deepcopy(
            parent_protocol["embargoed_holdout"]
        ),
        "source_sha256": dict(sorted(source_sha256.items())),
        "execution": execution,
        "outputs": {
            "run_root": RUN_ROOT_RELATIVE,
            "result": RESULT_RELATIVE,
        },
    }
    validate_protocol_shape(
        protocol,
        parent_protocol=parent_protocol,
        grandparent_protocol=grandparent_protocol,
        great_grandparent_protocol=great_grandparent_protocol,
        great_great_grandparent_protocol=great_great_grandparent_protocol,
        great_great_great_grandparent_protocol=(
            great_great_great_grandparent_protocol
        ),
        great_great_great_great_grandparent_protocol=(
            great_great_great_great_grandparent_protocol
        ),
        root_protocol=root_protocol,
    )
    return protocol


def validate_protocol_shape(
    protocol: dict[str, Any],
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    great_great_grandparent_protocol: dict[str, Any],
    great_great_great_grandparent_protocol: dict[str, Any],
    great_great_great_great_grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
) -> None:
    _validate_parent(
        parent_protocol,
        grandparent_protocol=grandparent_protocol,
        great_grandparent_protocol=great_grandparent_protocol,
        great_great_grandparent_protocol=great_great_grandparent_protocol,
        great_great_great_grandparent_protocol=(
            great_great_great_grandparent_protocol
        ),
        great_great_great_great_grandparent_protocol=(
            great_great_great_great_grandparent_protocol
        ),
        root_protocol=root_protocol,
    )
    if (
        protocol.get("candidate") != CANDIDATE
        or protocol.get("status") != STATUS
    ):
        raise ValueError("unexpected WebArena navigation-v8 identity")
    if re.fullmatch(
        r"[0-9a-f]{40}", str(protocol.get("source_commit", ""))
    ) is None:
        raise ValueError("navigation-v8 source commit is not immutable")
    if protocol.get("method_identity") != METHOD_IDENTITY:
        raise ValueError("navigation-v8 method identity changed")
    if protocol.get("learned_from") != LEARNED_FROM:
        raise ValueError("navigation-v8 failure lineage changed")
    preregistration = protocol.get("preregistration")
    if not (
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch(
            r"[0-9a-f]{64}", str(preregistration.get("sha256", ""))
        )
    ):
        raise ValueError("navigation-v8 preregistration changed")
    if protocol.get("development") != parent_protocol["development"]:
        raise ValueError("navigation-v8 development population or gate changed")
    if protocol.get("embargoed_holdout") != parent_protocol["embargoed_holdout"]:
        raise ValueError("navigation-v8 holdout embargo changed")
    sources = protocol.get("source_sha256")
    required = set(parent_protocol["source_sha256"]) | set(NEW_SOURCE_PATHS)
    if not isinstance(sources, dict) or set(sources) != required:
        raise ValueError("navigation-v8 source closure changed")
    if any(
        re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
        for value in sources.values()
    ):
        raise ValueError("navigation-v8 source hash is malformed")
    execution = protocol.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("navigation-v8 execution view is absent")
    if execution.get("source_commit") != protocol["source_commit"]:
        raise ValueError("navigation-v8 execution source changed")
    if execution.get("source_sha256") != sources:
        raise ValueError("navigation-v8 execution closure changed")
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_protocol["execution"].items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation-v8 changed frozen field: {key}")
    if execution.get("decision_rule") != DECISION_RULE:
        raise ValueError("navigation-v8 decision rule changed")
    if protocol.get("outputs") != {
        "run_root": RUN_ROOT_RELATIVE,
        "result": RESULT_RELATIVE,
    }:
        raise ValueError("navigation-v8 outputs changed")
    if protocol["development"] != {
        "episodes": root_design.stage_manifest(root_design.DEVELOPMENT),
        "minimum_official_successes": 2,
        "expected_episodes": 3,
        "all_outcomes_retained": True,
        "official_evaluator_once_per_episode": True,
    }:
        raise ValueError("navigation-v8 scientific gate changed")
