"""Sealed boundary for post-navigation-v3 WebArena development V4."""

from __future__ import annotations

import copy
import re
from typing import Any

from inversereserve.studies import inversereserve_webarena_final_v1 as root_design
from inversereserve.studies import inversereserve_webarena_navigation_dev_v3 as parent_design
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v4"
STATUS = "sealed_after_v3_failure_before_v4_development_reset"
ROOT_PROTOCOL_RELATIVE = parent_design.ROOT_PROTOCOL_RELATIVE
ROOT_PROTOCOL_SHA256 = parent_design.ROOT_PROTOCOL_SHA256
GRANDPARENT_PROTOCOL_RELATIVE = parent_design.PARENT_PROTOCOL_RELATIVE
GRANDPARENT_PROTOCOL_SHA256 = parent_design.PARENT_PROTOCOL_SHA256
PARENT_PROTOCOL_RELATIVE = parent_design.PROTOCOL_RELATIVE
PARENT_PROTOCOL_SHA256 = "fae3a32f5ec658b9928d726356d7cfb5279a88ccf8f264e21002153aa6cb291f"
FAILED_DEVELOPMENT_RELATIVE = parent_design.RESULT_RELATIVE
FAILED_DEVELOPMENT_SHA256 = "0f85f3a5457005fe762959fbb4cacc446a8e56e6f575d38d4280922cdb4d238a"
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/2026-07-18_inversereserve_webarena_navigation_v4_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v4"
RESULT_RELATIVE = "validation/inversereserve_webarena_navigation_development_v4.json"
PROTOCOL_RELATIVE = "validation/inversereserve_webarena_navigation_dev_v4_protocol.json"
METHOD_ID = "full_pact_v14_webarena_exact_mutation_nav4"
METHOD_IDENTITY = {
    "paper_name": "InverseReserve",
    "mutation_runtime": "pact_v13_exact_mutation_public_edit_surface_v3",
    "navigation_runtime": "public_navigation_v4",
    "observation_runtime": "indexed_semantic_snapshot_v1",
    "executor_runtime": "reward_isolated_click_no_wait_v3",
    "controller_arm": METHOD_ID,
    "mutation_path_changed_after_v3_result": True,
    "navigation_path_changed_after_v3_result": True,
    "post_failure_development_adaptation": True,
}
LEARNED_FROM = {
    "parent_protocol": {"path": PARENT_PROTOCOL_RELATIVE, "sha256": PARENT_PROTOCOL_SHA256},
    "failed_development": {
        "path": FAILED_DEVELOPMENT_RELATIVE,
        "sha256": FAILED_DEVELOPMENT_SHA256,
        "official_successes": 0,
        "episodes": 3,
    },
    "public_failure_diagnosis": {
        "reddit": "one text field and a non-text input inherited the same public Biography context, so the exact adapter failed closed",
        "gitlab": "a public 502 recovery returned to a re-rendered dashboard; the planner then wandered and emitted a stale public bid",
        "shopping_admin": "the planner selected Add New Page although one quoted existing entity exactly matched Home Page, then emitted a stale control bid",
    },
    "permitted_change": "public input-type projection, Back as a public neutralization witness, unique exact quoted-entity binding, unique stable semantic bid rebinding, and at most one replay of an already-effective public route prefix after a visible recovery page",
}
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v4.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v4.py",
        "src/inversereserve/studies/inversereserve_webarena_navigation_dev_v4.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v14_nav4.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_v3.py",
        "src/inversereserve/adapters/webarena/webarena_public_navigation_v4.py",
        "tests/test_inversereserve_webarena_navigation_dev_v4.py",
        "tests/test_webarena_exact_mutation_v3.py",
        "tests/test_webarena_public_navigation_v4.py",
    }
)
DECISION_RULE = {
    "on_pass": "freeze a navigation-v5 protocol over the still-unopened original holdout before its first reset",
    "on_failure": "preserve the complete v4 development result; the original holdout remains unopened and unauthorized",
}


def _validate_parent(
    parent_protocol: dict[str, Any], *, grandparent_protocol: dict[str, Any], root_protocol: dict[str, Any]
) -> None:
    parent_design.validate_protocol_shape(
        parent_protocol, parent_protocol=grandparent_protocol, root_protocol=root_protocol
    )
    if parent_protocol.get("source_commit") != "2dc5786e0502f6d343e0e5aeb1659f774173cb39":
        raise ValueError("navigation-v3 source commit changed")


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
    source_commit: str,
    source_sha256: dict[str, str],
    preregistration_sha256: str,
    created_utc: str,
) -> dict[str, Any]:
    _validate_parent(parent_protocol, grandparent_protocol=grandparent_protocol, root_protocol=root_protocol)
    execution = copy.deepcopy(parent_protocol["execution"])
    execution["candidate"] = "InverseReserve-WebArena-navigation-development-execution-v4"
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
        root_protocol=root_protocol,
    )
    return protocol


def validate_protocol_shape(
    protocol: dict[str, Any],
    *,
    parent_protocol: dict[str, Any],
    grandparent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
) -> None:
    _validate_parent(parent_protocol, grandparent_protocol=grandparent_protocol, root_protocol=root_protocol)
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected WebArena navigation-v4 identity",
    )
    require(
        re.fullmatch("[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is not None,
        "navigation-v4 source commit is not immutable",
    )
    require(not protocol.get("method_identity") != METHOD_IDENTITY, "navigation-v4 method identity changed")
    require(not protocol.get("learned_from") != LEARNED_FROM, "navigation-v4 failure lineage changed")
    preregistration = protocol.get("preregistration")
    require(
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch("[0-9a-f]{64}", str(preregistration.get("sha256", ""))),
        "navigation-v4 preregistration changed",
    )
    require(
        not protocol.get("development") != parent_protocol["development"],
        "navigation-v4 development population or gate changed",
    )
    require(
        not protocol.get("embargoed_holdout") != parent_protocol["embargoed_holdout"],
        "navigation-v4 holdout embargo changed",
    )
    sources = protocol.get("source_sha256")
    required = set(parent_protocol["source_sha256"]) | set(NEW_SOURCE_PATHS)
    require(
        not (not isinstance(sources, dict) or set(sources) != required),
        "navigation-v4 source closure changed",
    )
    require(
        not any((re.fullmatch("[0-9a-f]{64}", str(value)) is None for value in sources.values())),
        "navigation-v4 source hash is malformed",
    )
    execution = protocol.get("execution")
    require(isinstance(execution, dict), "navigation-v4 execution view is absent")
    require(
        not execution.get("source_commit") != protocol["source_commit"],
        "navigation-v4 execution source changed",
    )
    require(not execution.get("source_sha256") != sources, "navigation-v4 execution closure changed")
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_protocol["execution"].items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation-v4 changed frozen field: {key}")
    require(not execution.get("decision_rule") != DECISION_RULE, "navigation-v4 decision rule changed")
    require(
        not protocol.get("outputs") != {"run_root": RUN_ROOT_RELATIVE, "result": RESULT_RELATIVE},
        "navigation-v4 outputs changed",
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
        "navigation-v4 scientific gate changed",
    )
