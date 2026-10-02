"""Registered transfer declarations and analysis agree across the namespace migration."""

from __future__ import annotations

import copy
import importlib

import pytest

from .test_controller_differential import original_package as original_package
from .test_protocol_differential import outcome


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("partition", ["adapter_development", "mechanism_holdout"])
def test_webarena_exact_mutation_transfer_analysis(original_package, version, partition):
    modules = [
        importlib.import_module(prefix + f"webarena_exact_mutation_transfer_v{version}")
        for prefix in ("rcrps.", "inversereserve.studies.")
    ]
    legacy = modules[1] if version == 1 else modules[1].legacy
    rows = [
        {
            "episode": episode,
            "metrics": {},
            "trace": [],
            "runtime_events": [],
            "official_evaluation": {"passed": True, "returncode": 0},
            "active_transactions_at_stop": [],
        }
        for episode in legacy.episode_manifest(partition)
    ]
    name = "analyze_transfer_rows" if version == 1 else "analyze_transfer_rows_v2"
    for complete in (False, True):
        results = [
            getattr(m, name)(copy.deepcopy(rows), partition=partition, all_claims_complete=complete)
            for m in modules
        ]
        assert results[0] == results[1]
        assert results[1]["metrics"]["official_success"] == len(rows)
        assert results[1]["passed"] is False  # incomplete method-integrity records cannot certify a transfer


def protocol(module, partition):
    base = module.legacy
    dev = partition == "adapter_development"
    p = {
        "candidate": "WebArena-Verified-exact-mutation-development-protocol-v2"
        if dev
        else "WebArena-Verified-exact-mutation-holdout-protocol-v2",
        "status": "sealed_after_v1_development_before_v2_execution"
        if dev
        else "sealed_before_holdout_states_opened",
        "partition": partition,
        "source_commit": "a" * 40,
        "episodes": base.episode_manifest(partition),
        "expected_episodes": len(base.episode_manifest(partition)),
        "budgets": base.EXPECTED_BUDGETS,
        "generation": base.EXPECTED_GENERATION,
        "information_boundary": base.EXPECTED_INFORMATION_BOUNDARY,
        "runtime": base.EXPECTED_RUNTIME,
        "official_source": base.expected_official_source(),
        "repositories": base.EXPECTED_REPOSITORIES,
        "decision_rule": base.EXPECTED_DECISION_RULES[partition],
        "official_images": base.EXPECTED_OFFICIAL_IMAGES,
        "official_evaluator": base.EXPECTED_OFFICIAL_EVALUATOR,
        "holdout_gates": None if dev else module.EXPECTED_HOLDOUT_GATES_V2,
        "development_gates": module.EXPECTED_DEVELOPMENT_GATES_V2,
        "successor_changes": module.SUCCESSOR_CHANGES_V2,
        "successor_audit": {
            "path": module.SUCCESSOR_AUDIT_RELATIVE,
            "sha256": "a" * 64,
            "created_before_development_outcomes": True,
        },
        "source_sha256": {name: "b" * 64 for name in module.REQUIRED_SOURCE_PATHS_V2},
    }
    if dev:
        p["activation"] = {
            "predecessor_protocol": {"path": module.PREDECESSOR_PROTOCOL_RELATIVE, "sha256": "a" * 64},
            "predecessor_result": {"path": module.PREDECESSOR_RESULT_RELATIVE, "sha256": "a" * 64},
            "pact_v10_trace_equivalence": {"path": module.PACT_V10_EQUIVALENCE_RELATIVE, "sha256": "a" * 64},
        }
        p["state_boundary"] = {
            "development_states_previously_opened_by_v1": True,
            "holdout_states_opened": False,
        }
    else:
        p["activation"] = {
            "development_result": {"path": module.DEVELOPMENT_RESULT_V2_RELATIVE, "sha256": "a" * 64},
            "pact_v10_trace_equivalence": {"path": module.PACT_V10_EQUIVALENCE_RELATIVE, "sha256": "a" * 64},
        }
        p["state_boundary"] = {"development_states_opened": True, "holdout_states_opened": False}
    return p


@pytest.mark.parametrize("partition", ["adapter_development", "mechanism_holdout"])
def test_webarena_exact_mutation_transfer_v2_schema(original_package, partition):
    modules = [
        importlib.import_module(prefix + "webarena_exact_mutation_transfer_v2")
        for prefix in ("rcrps.", "inversereserve.studies.")
    ]
    protocols = [protocol(module, partition) for module in modules]
    for module, p in zip(modules, protocols, strict=True):
        module.validate_protocol_shape_v2(p, partition=partition)
    for key in protocols[0]:
        results = []
        for module, p in zip(modules, protocols, strict=True):
            value = copy.deepcopy(p)
            value[key] = None
            results.append(
                outcome(
                    lambda x, module=module: module.validate_protocol_shape_v2(x, partition=partition), value
                )
            )
        assert results[0] == results[1], key
