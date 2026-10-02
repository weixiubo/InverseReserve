"""Sealed boundary for post-v2 WebArena development adaptation V3."""

from __future__ import annotations

import copy
import re
from typing import Any

from inversereserve.studies import inversereserve_webarena_final_v1 as root_design
from inversereserve.studies import inversereserve_webarena_navigation_dev_v2 as parent_design
from inversereserve.studies.validation import require

CANDIDATE = "InverseReserve-WebArena-navigation-development-protocol-v3"
STATUS = "sealed_after_v2_failure_before_v3_development_reset"
ROOT_PROTOCOL_RELATIVE = parent_design.PARENT_PROTOCOL_RELATIVE
ROOT_PROTOCOL_SHA256 = parent_design.PARENT_PROTOCOL_SHA256
PARENT_PROTOCOL_RELATIVE = parent_design.PROTOCOL_RELATIVE
PARENT_PROTOCOL_SHA256 = "d87433fafaa290c04587036a1702a6c81a0e3322fee6be4b00df0ce3c6ed9e5f"
FAILED_DEVELOPMENT_RELATIVE = parent_design.RESULT_RELATIVE
FAILED_DEVELOPMENT_SHA256 = "af597fbb04849765d2bc57656ae03c6b109a421e44e8aa09fa37b408c3a06177"
PREREGISTRATION_RELATIVE = (
    "paper/aaai27/notes/2026-07-18_inversereserve_webarena_navigation_v3_preregistration.md"
)
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_navigation_dev_v3"
RESULT_RELATIVE = "validation/inversereserve_webarena_navigation_development_v3.json"
PROTOCOL_RELATIVE = "validation/inversereserve_webarena_navigation_dev_v3_protocol.json"
METHOD_ID = "full_pact_v13_webarena_exact_mutation_nav3"
METHOD_IDENTITY = {
    "paper_name": "InverseReserve",
    "mutation_runtime": "pact_v13_exact_mutation_public_edit_surface_v2",
    "navigation_runtime": "public_navigation_v3",
    "observation_runtime": "indexed_semantic_snapshot_v1",
    "executor_runtime": "reward_isolated_click_no_wait_v3",
    "controller_arm": METHOD_ID,
    "mutation_path_changed_after_primary_result": True,
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
        "reddit": "a visible standard account disclosure lacked the optional BrowserGym clickable marker and v2 later looped",
        "gitlab": "the public profile endpoint reproducibly displayed a 502 recovery page",
        "shopping_admin": "the target inline editor had Save and Cancel but no DOM form, while repeated public snapshot traversal dominated compilation time",
    },
    "permitted_change": "semantics-preserving public observation indexes, standard link/button coverage, at most one public-error-authorized retry, click/no-wait synchronization, and one bounded form-less public edit surface",
}
NEW_SOURCE_PATHS = frozenset(
    {
        "scripts/inversereserve_webarena_navigation_dev_v3.py",
        "scripts/seal_inversereserve_webarena_navigation_dev_v3.py",
        "src/inversereserve/studies/inversereserve_webarena_navigation_dev_v3.py",
        "src/inversereserve/observations/typed_observation_indexed_v1.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v13_nav3.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_v2.py",
        "src/inversereserve/adapters/webarena/webarena_executor_v3.py",
        "src/inversereserve/adapters/webarena/webarena_public_navigation_v3.py",
        "tests/test_inversereserve_webarena_navigation_dev_v3.py",
        "tests/test_typed_observation_indexed_v1.py",
        "tests/test_webarena_exact_mutation_v2.py",
        "tests/test_webarena_executor_v3.py",
        "tests/test_webarena_public_navigation_v3.py",
    }
)


def _validate_parent(parent_protocol: dict[str, Any], *, root_protocol: dict[str, Any]) -> None:
    parent_design.validate_protocol_shape(parent_protocol, parent_protocol=root_protocol)
    if parent_protocol.get("source_commit") != "a3f71f983c3f1abd10059811df7180392aa6a097":
        raise ValueError("navigation-v2 source commit changed")


def build_protocol(
    *,
    parent_protocol: dict[str, Any],
    root_protocol: dict[str, Any],
    source_commit: str,
    source_sha256: dict[str, str],
    preregistration_sha256: str,
    created_utc: str,
) -> dict[str, Any]:
    _validate_parent(parent_protocol, root_protocol=root_protocol)
    execution = copy.deepcopy(parent_protocol["execution"])
    execution["candidate"] = "InverseReserve-WebArena-navigation-development-execution-v3"
    execution["source_commit"] = source_commit
    execution["source_sha256"] = dict(sorted(source_sha256.items()))
    execution["decision_rule"] = {
        "on_pass": "freeze one successor protocol over the still-unopened original holdout before its first reset",
        "on_failure": "preserve the complete v3 development result; the original holdout remains unopened and unauthorized",
    }
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
    validate_protocol_shape(protocol, parent_protocol=parent_protocol, root_protocol=root_protocol)
    return protocol


def validate_protocol_shape(
    protocol: dict[str, Any], *, parent_protocol: dict[str, Any], root_protocol: dict[str, Any]
) -> None:
    _validate_parent(parent_protocol, root_protocol=root_protocol)
    require(
        not (protocol.get("candidate") != CANDIDATE or protocol.get("status") != STATUS),
        "unexpected WebArena navigation-v3 identity",
    )
    require(
        re.fullmatch("[0-9a-f]{40}", str(protocol.get("source_commit", ""))) is not None,
        "navigation-v3 source commit is not immutable",
    )
    require(not protocol.get("method_identity") != METHOD_IDENTITY, "navigation-v3 method identity changed")
    require(not protocol.get("learned_from") != LEARNED_FROM, "navigation-v3 failure lineage changed")
    preregistration = protocol.get("preregistration")
    require(
        isinstance(preregistration, dict)
        and preregistration.get("path") == PREREGISTRATION_RELATIVE
        and re.fullmatch("[0-9a-f]{64}", str(preregistration.get("sha256", ""))),
        "navigation-v3 preregistration changed",
    )
    require(
        not protocol.get("development") != parent_protocol["development"],
        "navigation-v3 development population or gate changed",
    )
    require(
        not protocol.get("embargoed_holdout") != parent_protocol["embargoed_holdout"],
        "navigation-v3 holdout embargo changed",
    )
    source_sha256 = protocol.get("source_sha256")
    required_sources = set(parent_protocol["source_sha256"]) | set(NEW_SOURCE_PATHS)
    require(
        not (not isinstance(source_sha256, dict) or set(source_sha256) != required_sources),
        "navigation-v3 source closure changed",
    )
    require(
        not any((re.fullmatch("[0-9a-f]{64}", str(value)) is None for value in source_sha256.values())),
        "navigation-v3 source hash is malformed",
    )
    execution = protocol.get("execution")
    require(isinstance(execution, dict), "navigation-v3 execution view is absent")
    require(
        not execution.get("source_commit") != protocol["source_commit"],
        "navigation-v3 execution source changed",
    )
    require(not execution.get("source_sha256") != source_sha256, "navigation-v3 execution closure changed")
    ignored = {"candidate", "source_commit", "source_sha256", "decision_rule"}
    for key, value in parent_protocol["execution"].items():
        if key not in ignored and execution.get(key) != value:
            raise ValueError(f"navigation-v3 changed frozen field: {key}")
    require(
        not execution.get("decision_rule")
        != {
            "on_pass": "freeze one successor protocol over the still-unopened original holdout before its first reset",
            "on_failure": "preserve the complete v3 development result; the original holdout remains unopened and unauthorized",
        },
        "navigation-v3 decision rule changed",
    )
    require(
        not protocol.get("outputs") != {"run_root": RUN_ROOT_RELATIVE, "result": RESULT_RELATIVE},
        "navigation-v3 outputs changed",
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
        "navigation-v3 scientific gate changed",
    )
