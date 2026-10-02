"""Sealed boundary for post-navigation-v4 WebArena development V5."""

from __future__ import annotations

import copy
import re
from typing import Any

from inversereserve.studies import inversereserve_webarena_final_v1 as root_design
from inversereserve.studies import inversereserve_webarena_navigation_dev_v4 as parent_design
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v5"
STATUS = "sealed_after_v4_failure_before_v5_development_reset"
ROOT_PROTOCOL_RELATIVE = parent_design.ROOT_PROTOCOL_RELATIVE
ROOT_PROTOCOL_SHA256 = parent_design.ROOT_PROTOCOL_SHA256
GREAT_GRANDPARENT_PROTOCOL_RELATIVE = parent_design.GRANDPARENT_PROTOCOL_RELATIVE
GREAT_GRANDPARENT_PROTOCOL_SHA256 = parent_design.GRANDPARENT_PROTOCOL_SHA256
GRANDPARENT_PROTOCOL_RELATIVE = parent_design.PARENT_PROTOCOL_RELATIVE
GRANDPARENT_PROTOCOL_SHA256 = parent_design.PARENT_PROTOCOL_SHA256
PARENT_PROTOCOL_RELATIVE = parent_design.PROTOCOL_RELATIVE
PARENT_PROTOCOL_SHA256 = "597dad6225ef3e8def6ef9dfaff108246e19063760418258c54439b61ab8c929"
FAILED_DEVELOPMENT_RELATIVE = parent_design.RESULT_RELATIVE
FAILED_DEVELOPMENT_SHA256 = "7146f99ced757c0d9973bd0d0ef83e6ea91f3bf3eb9618abf67c192c0749116d"
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/2026-07-18_inversereserve_webarena_navigation_v5_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v5"
RESULT_RELATIVE = "validation/inversereserve_webarena_navigation_development_v5.json"
PROTOCOL_RELATIVE = "validation/inversereserve_webarena_navigation_dev_v5_protocol.json"
METHOD_ID = "full_pact_v15_webarena_exact_mutation_nav5"
METHOD_IDENTITY = {
    "paper_name": "InverseReserve",
    "mutation_runtime": "pact_v13_exact_mutation_public_edit_surface_v4",
    "navigation_runtime": "public_navigation_v5",
    "observation_runtime": "indexed_semantic_snapshot_v1",
    "executor_runtime": "reward_isolated_click_no_wait_v3",
    "controller_arm": METHOD_ID,
    "mutation_path_changed_after_v4_result": True,
    "navigation_path_changed_after_v4_result": True,
    "post_failure_development_adaptation": True,
}
LEARNED_FROM = {
    "parent_protocol": {"path": PARENT_PROTOCOL_RELATIVE, "sha256": PARENT_PROTOCOL_SHA256},
    "failed_development": {
        "path": FAILED_DEVELOPMENT_RELATIVE,
        "sha256": FAILED_DEVELOPMENT_SHA256,
        "official_successes": 1,
        "episodes": 3,
    },
    "public_failure_diagnosis": {
        "gitlab": "the recovered public profile form exposed Website url and one Update action, but broad accessibility ancestry polluted field labels and forced an ambiguous fail-closed binding",
        "shopping_admin": "the exact quoted row was mutated through a public inline editor, while the official workflow requires its visible row action, public Edit surface, and standard full-form Save",
    },
    "permitted_change": "field-local public label binding with a 32-descendant wrapper bound; a 128-candidate public scan that promotes one same-row Select or Actions disclosure into the unchanged 64-candidate planner bound; and one exact visible Edit action after that disclosure",
}
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v5.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v5.py",
        "src/inversereserve/studies/inversereserve_webarena_navigation_dev_v5.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v15_nav5.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_v4.py",
        "src/inversereserve/adapters/webarena/webarena_public_navigation_v5.py",
        "tests/test_inversereserve_webarena_navigation_dev_v5.py",
        "tests/test_webarena_exact_mutation_v4.py",
        "tests/test_webarena_public_navigation_v5.py",
    }
)
DECISION_RULE = {
    "on_pass": "freeze an independent navigation-v5 holdout protocol over the still-unopened original holdout before its first reset",
    "on_failure": "preserve the complete v5 development result; the original holdout remains unopened and unauthorized",
}


def _validate_parent(
    parent_protocol: dict[str, Any],
    *,
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
) -> None:
    parent_design.validate_protocol_shape(
        parent_protocol,
        parent_protocol=grandparent_protocol,
        grandparent_protocol=great_grandparent_protocol,
        root_protocol=root_protocol,
    )
    if parent_protocol.get("source_commit") != "c9c224e9bd0ddde81023a5e234234da448373230":
        raise ValueError("navigation-v4 source commit changed")


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
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
        root_protocol=root_protocol,
    )
    execution = copy.deepcopy(parent_protocol["execution"])
    execution["candidate"] = "InverseReserve-WebArena-navigation-development-execution-v5"
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
        "preregistration": {"path": PREREGISTRATION_RELATIVE, "sha256": preregistration_sha256},
        "development": copy.deepcopy(parent_protocol["development"]),
        "embargoed_holdout": copy.deepcopy(parent_protocol["embargoed_holdout"]),
        "source_sha256": dict(sorted(source_sha256.items())),
        "execution": execution,
        "outputs": {"run_root": RUN_ROOT_RELATIVE, "result": RESULT_RELATIVE},
    }
    validate_protocol_shape(
        protocol,
        parent_protocol=parent_protocol,
        grandparent_protocol=grandparent_protocol,
        great_grandparent_protocol=great_grandparent_protocol,
        root_protocol=root_protocol,
    )
    return protocol


def validate_protocol_shape(
    protocol: dict[str, Any],
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    great_grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
) -> None:
    _validate_parent(
        parent_protocol,
        grandparent_protocol=grandparent_protocol,
        great_grandparent_protocol=great_grandparent_protocol,
        root_protocol=root_protocol,
    )
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected WebArena navigation-v5 identity",
    )
    require(
        re.fullmatch("[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is not None,
        "navigation-v5 source commit is not immutable",
    )
    require(not protocol.get("method_identity") != METHOD_IDENTITY, "navigation-v5 method identity changed")
    require(not protocol.get("learned_from") != LEARNED_FROM, "navigation-v5 failure lineage changed")
    preregistration = protocol.get("preregistration")
    require(
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch("[0-9a-f]{64}", str(preregistration.get("sha256", ""))),
        "navigation-v5 preregistration changed",
    )
    require(
        not protocol.get("development") != parent_protocol["development"],
        "navigation-v5 development population or gate changed",
    )
    require(
        not protocol.get("embargoed_holdout") != parent_protocol["embargoed_holdout"],
        "navigation-v5 holdout embargo changed",
    )
    sources = protocol.get("source_sha256")
    required = set(parent_protocol["source_sha256"]) | set(NEW_SOURCE_PATHS)
    require(
        not (not isinstance(sources, dict) or set(sources) != required),
        "navigation-v5 source closure changed",
    )
    require(
        not any((re.fullmatch("[0-9a-f]{64}", str(value)) is None for value in sources.values())),
        "navigation-v5 source hash is malformed",
    )
    execution = protocol.get("execution")
    require(isinstance(execution, dict), "navigation-v5 execution view is absent")
    require(
        not execution.get("source_commit") != protocol["source_commit"],
        "navigation-v5 execution source changed",
    )
    require(not execution.get("source_sha256") != sources, "navigation-v5 execution closure changed")
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_protocol["execution"].items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation-v5 changed frozen field: {key}")
    require(not execution.get("decision_rule") != DECISION_RULE, "navigation-v5 decision rule changed")
    require(
        not protocol.get("outputs") != {"run_root": RUN_ROOT_RELATIVE, "result": RESULT_RELATIVE},
        "navigation-v5 outputs changed",
    )
    require(
        not protocol["development"]
        != {
            "episodes": root_design.stage_manifest(root_design.DEVELOPMENT),
            "minimum_official_successes": 2,
            "expected_episodes": 3,
            "all_outcomes_retained": True,
            "official_evaluator_once_per_episode": True,
        },
        "navigation-v5 scientific gate changed",
    )
