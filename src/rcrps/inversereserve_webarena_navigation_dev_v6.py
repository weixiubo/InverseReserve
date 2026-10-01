"""Sealed boundary for post-navigation-v5 WebArena development V6."""

from __future__ import annotations

import copy
import re
from typing import Any

from . import inversereserve_webarena_final_v1 as root_design
from . import inversereserve_webarena_navigation_dev_v5 as parent_design


CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v6"
STATUS = "sealed_after_v5_failure_before_v6_development_reset"
ROOT_PROTOCOL_RELATIVE = parent_design.ROOT_PROTOCOL_RELATIVE
ROOT_PROTOCOL_SHA256 = parent_design.ROOT_PROTOCOL_SHA256
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
    "6d4f77c60c428a7e0df57566bb6674085fa23b77197e228c65832aa5bf2e748f"
)
FAILED_DEVELOPMENT_RELATIVE = parent_design.RESULT_RELATIVE
FAILED_DEVELOPMENT_SHA256 = (
    "8b05f12b4399a8588cb28c17e7751253b6b6e04b3006c636a0a419c3772a96fa"
)
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/"
    "2026-07-18_inversereserve_webarena_navigation_v6_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v6"
RESULT_RELATIVE = (
    "validation/inversereserve_webarena_navigation_development_v6.json"
)
PROTOCOL_RELATIVE = (
    "validation/inversereserve_webarena_navigation_dev_v6_protocol.json"
)
METHOD_ID = "full_pact_v16_webarena_exact_mutation_nav6"
METHOD_IDENTITY = {
    "paper_name": "InverseReserve",
    "mutation_runtime": "pact_v13_exact_mutation_public_edit_surface_v4",
    "navigation_runtime": "public_navigation_v6",
    "form_reveal_runtime": "joint_half_visible_public_geometry_v6",
    "observation_runtime": "indexed_semantic_snapshot_v1",
    "executor_runtime": "reward_isolated_click_no_wait_v3",
    "controller_arm": METHOD_ID,
    "mutation_path_changed_after_v5_result": False,
    "navigation_path_changed_after_v5_result": True,
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
            "the complete v5 trace reached the public profile route, while "
            "a public diagnostic measured the exact Website url field at "
            "y=1522 and its unique same-form Update action at y=2212 in a "
            "720-pixel viewport; their joint half-visible scroll interval "
            "was [1508,1539]"
        ),
        "shopping_admin": (
            "the complete v5 trace found two same-row Select representations; "
            "a public diagnostic confirmed a clickable td ancestor and its "
            "unique descendant button with the same exact label"
        ),
    },
    "permitted_change": (
        "one public vertical scroll, bounded to four viewports and 4096 "
        "pixels, only when exact field and same-form submit have a nonempty "
        "joint half-visible interval; and same-label row-action "
        "canonicalization only when one standard leaf is a descendant of "
        "every other public representation"
    ),
}
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v6.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v6.py",
        "src/rcrps/inversereserve_webarena_navigation_dev_v6.py",
        "src/rcrps/webarena_exact_mutation_agent_v16_nav6.py",
        "src/rcrps/webarena_public_navigation_v6.py",
        "tests/test_inversereserve_webarena_navigation_dev_v6.py",
        "tests/test_webarena_public_navigation_v6.py",
    }
)


DECISION_RULE = {
    "on_pass": (
        "freeze an independent navigation-v6 holdout protocol over the "
        "still-unopened original holdout before its first reset"
    ),
    "on_failure": (
        "preserve the complete v6 development result; the original holdout "
        "remains unopened and unauthorized"
    ),
}


def _validate_parent(
    parent_protocol: dict[str, Any],
    *,
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    great_great_grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
) -> None:
    parent_design.validate_protocol_shape(
        parent_protocol,
        parent_protocol=grandparent_protocol,
        grandparent_protocol=great_grandparent_protocol,
        great_grandparent_protocol=great_great_grandparent_protocol,
        root_protocol=root_protocol,
    )
    if parent_protocol.get("source_commit") != (
        "7dc12e42c3d90443ea3f584a2418667d4a90b921"
    ):
        raise ValueError("navigation-v5 source commit changed")


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    great_great_grandparent_protocol: dict[str, Any],
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
        root_protocol=root_protocol,
    )
    execution = copy.deepcopy(parent_protocol["execution"])
    execution["candidate"] = (
        "InverseReserve-WebArena-navigation-development-execution-v6"
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
    root_protocol: dict[str, Any],
) -> None:
    _validate_parent(
        parent_protocol,
        grandparent_protocol=grandparent_protocol,
        great_grandparent_protocol=great_grandparent_protocol,
        great_great_grandparent_protocol=great_great_grandparent_protocol,
        root_protocol=root_protocol,
    )
    if protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS:
        raise ValueError("unexpected WebArena navigation-v6 identity")
    if re.fullmatch(r"[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is None:
        raise ValueError("navigation-v6 source commit is not immutable")
    if protocol.get("method_identity") != METHOD_IDENTITY:
        raise ValueError("navigation-v6 method identity changed")
    if protocol.get("learned_from") != LEARNED_FROM:
        raise ValueError("navigation-v6 failure lineage changed")
    preregistration = protocol.get("preregistration")
    if not (
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch(r"[0-9a-f]{64}", str(preregistration.get("sha256", "")))
    ):
        raise ValueError("navigation-v6 preregistration changed")
    if protocol.get("development") != parent_protocol["development"]:
        raise ValueError("navigation-v6 development population or gate changed")
    if protocol.get("embargoed_holdout") != parent_protocol["embargoed_holdout"]:
        raise ValueError("navigation-v6 holdout embargo changed")
    sources = protocol.get("source_sha256")
    required = set(parent_protocol["source_sha256"]) | set(NEW_SOURCE_PATHS)
    if not isinstance(sources, dict) or set(sources) != required:
        raise ValueError("navigation-v6 source closure changed")
    if any(
        re.fullmatch(r"[0-9a-f]{64}", str(value)) is None
        for value in sources.values()
    ):
        raise ValueError("navigation-v6 source hash is malformed")
    execution = protocol.get("execution")
    if not isinstance(execution, dict):
        raise ValueError("navigation-v6 execution view is absent")
    if execution.get("source_commit") != protocol["source_commit"]:
        raise ValueError("navigation-v6 execution source changed")
    if execution.get("source_sha256") != sources:
        raise ValueError("navigation-v6 execution closure changed")
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_protocol["execution"].items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation-v6 changed frozen field: {key}")
    if execution.get("decision_rule") != DECISION_RULE:
        raise ValueError("navigation-v6 decision rule changed")
    if protocol.get("outputs") != {
        "run_root": RUN_ROOT_RELATIVE,
        "result": RESULT_RELATIVE,
    }:
        raise ValueError("navigation-v6 outputs changed")
    if protocol["development"] != {
        "episodes": root_design.stage_manifest(root_design.DEVELOPMENT),
        "minimum_official_successes": 2,
        "expected_episodes": 3,
        "all_outcomes_retained": True,
        "official_evaluator_once_per_episode": True,
    }:
        raise ValueError("navigation-v6 scientific gate changed")
