"""Sealed boundary for post-navigation-v6 WebArena development V7."""

from __future__ import annotations

import copy
import re
from typing import Any

from . import inversereserve_webarena_final_v1 as root_design
from . import inversereserve_webarena_navigation_dev_v6 as parent_design


CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v7"
STATUS = "sealed_after_v6_failure_before_v7_development_reset"
ROOT_PROTOCOL_RELATIVE = parent_design.ROOT_PROTOCOL_RELATIVE
ROOT_PROTOCOL_SHA256 = parent_design.ROOT_PROTOCOL_SHA256
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
    "d0fd4607568f28bef7613f9f0c5335c6a1078a227c27a14fdf4718c938622e2b"
)
FAILED_DEVELOPMENT_RELATIVE = parent_design.RESULT_RELATIVE
FAILED_DEVELOPMENT_SHA256 = (
    "a4d8a467721fd347dc467ac4e99c31873e03e28b7d03688d73d9b772a533c0f1"
)
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/"
    "2026-07-18_inversereserve_webarena_navigation_v7_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v7"
RESULT_RELATIVE = (
    "validation/inversereserve_webarena_navigation_development_v7.json"
)
PROTOCOL_RELATIVE = (
    "validation/inversereserve_webarena_navigation_dev_v7_protocol.json"
)
METHOD_ID = "full_pact_v17_webarena_exact_mutation_nav7"
METHOD_IDENTITY = {
    "paper_name": "InverseReserve",
    "mutation_runtime": "pact_v13_exact_mutation_public_surface_v5",
    "navigation_runtime": "public_navigation_v6",
    "typed_value_runtime": "public_url_input_canonicalization_v5",
    "editor_surface_runtime": "bounded_semantic_viewport_editor_v5",
    "observation_runtime": "indexed_semantic_snapshot_v1",
    "executor_runtime": "reward_isolated_click_no_wait_v3",
    "controller_arm": METHOD_ID,
    "mutation_path_changed_after_v6_result": True,
    "navigation_path_changed_after_v6_result": False,
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
        "official_successes": 1,
        "episodes": 3,
    },
    "public_failure_diagnosis": {
        "gitlab": (
            "the complete v6 trace filled and committed the visible Website "
            "input with the verbatim bare hostname; the public input type was "
            "url and the official public POST used that bare hostname while "
            "the instruction-equivalent absolute URL required https"
        ),
        "shopping_admin": (
            "the complete v6 trace opened the quoted row's Edit page, where "
            "one exact Page Title field, one canonical exact Save leaf, Save "
            "options, and an icon-prefixed Back button were jointly visible "
            "inside one bounded main editor but the field-to-main depth was 11"
        ),
    },
    "permitted_change": (
        "prepend https only to a bare hostname derived verbatim from the goal "
        "when the uniquely bound public input declares type=url; and admit a "
        "form-less exact field only when it and one exact Save leaf share one "
        "bounded semantic viewport editor with a public Back/Cancel witness, "
        "canonicalizing same-label ancestor wrappers and excluding Save options"
    ),
}
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v7.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v7.py",
        "src/rcrps/inversereserve_webarena_navigation_dev_v7.py",
        "src/rcrps/webarena_exact_mutation_agent_v17_nav7.py",
        "src/rcrps/webarena_exact_mutation_v5.py",
        "tests/test_inversereserve_webarena_navigation_dev_v7.py",
        "tests/test_webarena_exact_mutation_v5.py",
    }
)


DECISION_RULE = {
    "on_pass": (
        "freeze an independent navigation-v7 holdout protocol over the "
        "still-unopened original holdout before its first reset"
    ),
    "on_failure": (
        "preserve the complete v7 development result; the original holdout "
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
        root_protocol=root_protocol,
    )
    if parent_protocol.get("source_commit") != (
        "2835c4273b68d36be588f6e814bb68f08fd41d6d"
    ):
        raise ValueError("navigation-v6 source commit changed")


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    great_great_grandparent_protocol: dict[str, Any],
    great_great_great_grandparent_protocol: dict[str, Any],
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
        root_protocol=root_protocol,
    )
    execution = copy.deepcopy(parent_protocol["execution"])
    execution["candidate"] = (
        "InverseReserve-WebArena-navigation-development-execution-v7"
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
        root_protocol=root_protocol,
    )
    if (
        protocol.get("candidate") != CANDIDATE
        or protocol.get("status") != STATUS
    ):
        raise ValueError("unexpected WebArena navigation-v7 identity")
    if re.fullmatch(
        r"[0-9a-f]{40}", str(protocol.get("source_commit", ""))
    ) is None:
        raise ValueError("navigation-v7 source commit is not immutable")
    if protocol.get("method_identity") != METHOD_IDENTITY:
        raise ValueError("navigation-v7 method identity changed")
    if protocol.get("learned_from") != LEARNED_FROM:
        raise ValueError("navigation-v7 failure lineage changed")
    preregistration = protocol.get("preregistration")
    if not (
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch(
            r"[0-9a-f]{64}", str(preregistration.get("sha256", ""))
        )
    ):
        raise ValueError("navigation-v7 preregistration changed")
    if protocol.get("development") != parent_protocol["development"]:
        raise ValueError("navigation-v7 development population or gate changed")
    if protocol.get("embargoed_holdout") != parent_protocol["embargoed_holdout"]:
        raise ValueError("navigation-v7 holdout embargo changed")
    sources = protocol.get("source_sha256")
    required = set(parent_protocol["source_sha256"]) | set(NEW_SOURCE_PATHS)
    if not isinstance(sources, dict) or set(sources) != required:
        raise ValueError("navigation-v7 source closure changed")
    if any(
        re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
        for value in sources.values()
    ):
        raise ValueError("navigation-v7 source hash is malformed")
    execution = protocol.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("navigation-v7 execution view is absent")
    if execution.get("source_commit") != protocol["source_commit"]:
        raise ValueError("navigation-v7 execution source changed")
    if execution.get("source_sha256") != sources:
        raise ValueError("navigation-v7 execution closure changed")
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_protocol["execution"].items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation-v7 changed frozen field: {key}")
    if execution.get("decision_rule") != DECISION_RULE:
        raise ValueError("navigation-v7 decision rule changed")
    if protocol.get("outputs") != {
        "run_root": RUN_ROOT_RELATIVE,
        "result": RESULT_RELATIVE,
    }:
        raise ValueError("navigation-v7 outputs changed")
    if protocol["development"] != {
        "episodes": root_design.stage_manifest(root_design.DEVELOPMENT),
        "minimum_official_successes": 2,
        "expected_episodes": 3,
        "all_outcomes_retained": True,
        "official_evaluator_once_per_episode": True,
    }:
        raise ValueError("navigation-v7 scientific gate changed")
