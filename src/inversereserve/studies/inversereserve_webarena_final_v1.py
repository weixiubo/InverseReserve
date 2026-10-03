"""Frozen design for the independent InverseReserve WebArena final suite.

This module is declarative: it opens no browser, container, model, task state,
or evaluator.  One suite protocol fixes both development and holdout before
the first selected-state reset.
"""

from __future__ import annotations

import copy
import re
from typing import Any

from inversereserve.adapters.webarena.webarena_verified_runtime_v1 import validate_image_record_v1
from inversereserve.studies.validation import require
from inversereserve.studies.webarena_exact_mutation_transfer_v1 import (
    EXPECTED_BUDGETS,
    EXPECTED_GENERATION,
    EXPECTED_INFORMATION_BOUNDARY,
    EXPECTED_OFFICIAL_EVALUATOR,
    EXPECTED_OFFICIAL_IMAGES,
    EXPECTED_REPOSITORIES,
    EXPECTED_RUNTIME,
    episode_manifest,
    expected_official_source,
)
from inversereserve.studies.webarena_exact_mutation_transfer_v2 import REQUIRED_SOURCE_PATHS_V2

DEVELOPMENT = "adapter_development"
HOLDOUT = "mechanism_holdout"
STAGES = (DEVELOPMENT, HOLDOUT)
PRIMARY_RESULT_RELATIVE = "validation/inversereserve_final_result_v1.json"
PRIMARY_RESULT_SHA256 = "a861decad2b180675895e50fe04d4b0bc2c5089a8493f27f7fa5f849825210f7"
PREOPEN_AUDIT_RELATIVE = "paper/aaai27/notes/2026-07-18_inversereserve_webarena_preopen_audit_v1.md"
CONFIG_SHA256 = "d3375a811654eb2a30c6d3e1a6e07d10021436abc44e5055ab08cc3f3f9f245a"
OCR_CACHE_SHA256 = "2264926fb0d2ae2a8ec648e23693a4d593e51d3937c1f07fb7e836fb1aebcfd5"
RUN_ROOT_RELATIVE = "runs/inversereserve_webarena_final_v1"
DEVELOPMENT_RESULT_RELATIVE = "validation/inversereserve_webarena_final_development_v1.json"
HOLDOUT_RESULT_RELATIVE = "validation/inversereserve_webarena_final_holdout_v1.json"
EXPECTED_STAGE_GATES = {
    DEVELOPMENT: {
        "minimum_official_successes": 2,
        "expected_episodes": 3,
        "require_every_analysis_check_true": True,
        "holdout_must_remain_unopened": True,
    },
    HOLDOUT: {
        "minimum_official_successes": 5,
        "expected_episodes": 6,
        "require_success_on_every_represented_site": True,
        "require_every_analysis_check_true": True,
    },
}
EXPECTED_DECISION_RULES = {
    DEVELOPMENT: {
        "on_pass": "open the already-frozen same-suite mechanism holdout without changing source, tasks, budgets, or gates",
        "on_failure": "preserve the complete development result and keep the frozen mechanism holdout unopened",
    },
    HOLDOUT: {
        "on_pass": "report bounded InverseReserve exact-mutation transfer across the four frozen sites",
        "on_failure": "report the complete negative holdout result without replacement",
    },
}
REQUIRED_SOURCE_PATHS = frozenset(
    {
        *REQUIRED_SOURCE_PATHS_V2,
        "ops/run_inversereserve_webarena_final_v1_resource_gate.sh",
        "scripts/inversereserve_webarena_final_v1.py",
        "scripts/seal_inversereserve_webarena_final_v1.py",
        "scripts/webarena_exact_mutation_transfer_v1.py",
        "scripts/webarena_exact_mutation_transfer_v2.py",
        "scripts/webarena_exact_mutation_transfer_v13.py",
        "scripts/pact_v13_reexecution_common.py",
        "scripts/pact_v13_full_reexecution_template.py",
        "src/inversereserve/studies/inversereserve_webarena_final_v1.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v12.py",
        "src/inversereserve/adapters/webarena/webarena_exact_mutation_agent_v13.py",
        "src/inversereserve/controllers/confirmation_agents_v12.py",
        "src/inversereserve/controllers/confirmation_agents_v13.py",
        "src/inversereserve/controllers/pact_controller_v11.py",
        "src/inversereserve/controllers/pact_controller_v12.py",
        "src/inversereserve/controllers/pact_controller_v13.py",
    }
)


def stage_manifest(partition: str) -> list[dict[str, Any]]:
    if partition not in STAGES:
        raise ValueError(f"unknown InverseReserve WebArena stage: {partition}")
    return episode_manifest(partition)


def result_relative(partition: str) -> str:
    if partition == DEVELOPMENT:
        return DEVELOPMENT_RESULT_RELATIVE
    if partition == HOLDOUT:
        return HOLDOUT_RESULT_RELATIVE
    raise ValueError(f"unknown InverseReserve WebArena stage: {partition}")


def _reference_exact(value: object, *, path: str, sha256: str | None = None) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == {"path", "sha256"}
        and (value.get("path") == path)
        and re.fullmatch("[0-9a-f]{64}", str(value.get("sha256")))
        and (sha256 is None or value.get("sha256") == sha256)
    )


def build_protocol(
    *, source_commit: str, source_sha256: dict[str, str], preopen_audit_sha256: str, created_utc: str
) -> dict[str, Any]:
    stages = {}
    for partition in STAGES:
        manifest = stage_manifest(partition)
        stages[partition] = {
            "episodes": manifest,
            "expected_episodes": len(manifest),
            "analysis": "analyze_transfer_rows_v13",
            "gates": copy.deepcopy(EXPECTED_STAGE_GATES[partition]),
            "decision_rule": copy.deepcopy(EXPECTED_DECISION_RULES[partition]),
            "result": result_relative(partition),
        }
    protocol = {
        "candidate": "InverseReserve-WebArena-final-suite-protocol-v1",
        "status": "sealed_before_any_selected_state_opened",
        "created_utc": created_utc,
        "scientific_source_commit": source_commit,
        "method_identity": {
            "paper_name": "InverseReserve",
            "runtime_driver": "full_pact_v13_webarena_exact_mutation_v2",
            "complete_public_observation_guard": True,
            "complete_public_commit_freshness": True,
        },
        "activation": {"primary_result": {"path": PRIMARY_RESULT_RELATIVE, "sha256": PRIMARY_RESULT_SHA256}},
        "preopen_audit": {"path": PREOPEN_AUDIT_RELATIVE, "sha256": preopen_audit_sha256},
        "stages": stages,
        "budgets": copy.deepcopy(EXPECTED_BUDGETS),
        "generation": copy.deepcopy(EXPECTED_GENERATION),
        "information_boundary": copy.deepcopy(EXPECTED_INFORMATION_BOUNDARY),
        "runtime": copy.deepcopy(EXPECTED_RUNTIME),
        "official_source": expected_official_source(),
        "repositories": copy.deepcopy(EXPECTED_REPOSITORIES),
        "official_images": copy.deepcopy(EXPECTED_OFFICIAL_IMAGES),
        "official_evaluator": copy.deepcopy(EXPECTED_OFFICIAL_EVALUATOR),
        "external_config_sha256": CONFIG_SHA256,
        "ocr_cache_sha256": OCR_CACHE_SHA256,
        "source_sha256": dict(sorted(source_sha256.items())),
        "state_boundary": {
            "selected_development_states_opened": False,
            "selected_holdout_states_opened": False,
            "one_suite_protocol_seals_both_stages": True,
            "holdout_requires_same_suite_development_pass": True,
            "outcome_based_task_replacement_allowed": False,
        },
        "outputs": {
            "run_root": RUN_ROOT_RELATIVE,
            "development_result": DEVELOPMENT_RESULT_RELATIVE,
            "holdout_result": HOLDOUT_RESULT_RELATIVE,
        },
    }
    validate_protocol_shape(protocol)
    return protocol


def validate_protocol_shape(protocol: dict[str, Any]) -> None:
    require(
        not protocol.get("candidate") != "InverseReserve-WebArena-final-suite-protocol-v1",
        "unexpected InverseReserve WebArena protocol candidate",
    )
    require(
        not protocol.get("status") != "sealed_before_any_selected_state_opened",
        "WebArena suite was not sealed before selected states",
    )
    require(
        re.fullmatch("[0-9a-f]{40}", str(protocol.get("scientific_source_commit", ""))) is not None,
        "WebArena scientific source commit is not immutable",
    )
    require(
        not protocol.get("method_identity")
        != {
            "paper_name": "InverseReserve",
            "runtime_driver": "full_pact_v13_webarena_exact_mutation_v2",
            "complete_public_observation_guard": True,
            "complete_public_commit_freshness": True,
        },
        "WebArena method identity changed",
    )
    require(
        not protocol.get("activation")
        != {"primary_result": {"path": PRIMARY_RESULT_RELATIVE, "sha256": PRIMARY_RESULT_SHA256}},
        "WebArena primary-result activation changed",
    )
    require(
        _reference_exact(protocol.get("preopen_audit"), path=PREOPEN_AUDIT_RELATIVE),
        "WebArena pre-open audit binding changed",
    )
    require(not protocol.get("budgets") != EXPECTED_BUDGETS, "WebArena budgets changed")
    require(not protocol.get("generation") != EXPECTED_GENERATION, "WebArena generation settings changed")
    require(
        not protocol.get("information_boundary") != EXPECTED_INFORMATION_BOUNDARY,
        "WebArena information boundary changed",
    )
    require(not protocol.get("runtime") != EXPECTED_RUNTIME, "WebArena runtime settings changed")
    require(
        not protocol.get("official_source") != expected_official_source(), "WebArena official source changed"
    )
    require(not protocol.get("repositories") != EXPECTED_REPOSITORIES, "WebArena repository pins changed")
    require(
        not protocol.get("official_images") != EXPECTED_OFFICIAL_IMAGES, "WebArena official images changed"
    )
    for record in protocol["official_images"].values():
        validate_image_record_v1(record)
    require(
        not protocol.get("official_evaluator") != EXPECTED_OFFICIAL_EVALUATOR,
        "WebArena official evaluator changed",
    )
    validate_image_record_v1(protocol["official_evaluator"]["image"])
    require(
        not protocol.get("external_config_sha256") != CONFIG_SHA256, "WebArena external configuration changed"
    )
    require(not protocol.get("ocr_cache_sha256") != OCR_CACHE_SHA256, "WebArena OCR cache binding changed")
    source_hashes = protocol.get("source_sha256")
    require(
        not (not isinstance(source_hashes, dict) or set(source_hashes) != REQUIRED_SOURCE_PATHS),
        "WebArena causal source inventory changed",
    )
    require(
        not any((re.fullmatch("[0-9a-f]{64}", str(value)) is None for value in source_hashes.values())),
        "WebArena causal source hash is malformed",
    )
    stages = protocol.get("stages")
    require(
        not (not isinstance(stages, dict) or set(stages) != set(STAGES)), "WebArena stage inventory changed"
    )
    for partition in STAGES:
        expected_manifest = stage_manifest(partition)
        expected_stage = {
            "episodes": expected_manifest,
            "expected_episodes": len(expected_manifest),
            "analysis": "analyze_transfer_rows_v13",
            "gates": EXPECTED_STAGE_GATES[partition],
            "decision_rule": EXPECTED_DECISION_RULES[partition],
            "result": result_relative(partition),
        }
        if stages[partition] != expected_stage:
            raise ValueError(f"WebArena frozen stage changed: {partition}")
    require(
        not protocol.get("state_boundary")
        != {
            "selected_development_states_opened": False,
            "selected_holdout_states_opened": False,
            "one_suite_protocol_seals_both_stages": True,
            "holdout_requires_same_suite_development_pass": True,
            "outcome_based_task_replacement_allowed": False,
        },
        "WebArena state boundary changed",
    )
    require(
        not protocol.get("outputs")
        != {
            "run_root": RUN_ROOT_RELATIVE,
            "development_result": DEVELOPMENT_RESULT_RELATIVE,
            "holdout_result": HOLDOUT_RESULT_RELATIVE,
        },
        "WebArena output paths changed",
    )


def execution_protocol(protocol: dict[str, Any], partition: str) -> dict[str, Any]:
    """Return the deterministic stage view consumed by the frozen harness."""
    validate_protocol_shape(protocol)
    stage = protocol["stages"][partition]
    return {
        "candidate": "InverseReserve-WebArena-final-execution-view-v1",
        "status": "derived_without_changing_the_sealed_suite",
        "partition": partition,
        "source_commit": protocol["scientific_source_commit"],
        "episodes": copy.deepcopy(stage["episodes"]),
        "expected_episodes": stage["expected_episodes"],
        "budgets": copy.deepcopy(protocol["budgets"]),
        "generation": copy.deepcopy(protocol["generation"]),
        "information_boundary": copy.deepcopy(protocol["information_boundary"]),
        "runtime": copy.deepcopy(protocol["runtime"]),
        "official_source": copy.deepcopy(protocol["official_source"]),
        "repositories": copy.deepcopy(protocol["repositories"]),
        "official_images": copy.deepcopy(protocol["official_images"]),
        "official_evaluator": copy.deepcopy(protocol["official_evaluator"]),
        "source_sha256": copy.deepcopy(protocol["source_sha256"]),
        "preregistration": copy.deepcopy(protocol["preopen_audit"]),
        "decision_rule": copy.deepcopy(stage["decision_rule"]),
        "suite_activation": copy.deepcopy(protocol["activation"]),
    }


def development_authorizes_holdout(result: dict[str, Any], *, protocol_sha256: str) -> bool:
    checks = result.get("checks")
    return bool(
        result.get("candidate") == "InverseReserve-WebArena-final-development-v1"
        and result.get("status") == "development_complete"
        and (result.get("stage") == DEVELOPMENT)
        and (result.get("passed") is True)
        and (result.get("protocol_sha256") == protocol_sha256)
        and (result.get("development_states_opened") is True)
        and (result.get("holdout_states_opened") is False)
        and (result.get("metrics", {}).get("episodes") == 3)
        and (result.get("development_task_ids") == [399, 449, 488])
        and isinstance(checks, dict)
        and checks
        and all((value is True for value in checks.values()))
    )
