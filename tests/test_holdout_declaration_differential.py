"""Holdout activation and child declarations preserve original first-failure behavior.

The parent-validation dependency is isolated only in the child-schema comparison;
this does not claim that unavailable historical parent artifacts were verified.
"""

from __future__ import annotations

import copy
import importlib
import inspect

import pytest

from .test_controller_differential import original_package as original_package
from .test_protocol_differential import outcome


def development_result(module, version):
    metrics = {
        "episodes": 3,
        "official_success": 3,
        "infrastructure_failures": 0,
        "unrecovered_action_errors": 0,
        "navigation_v8_joint_url_semantic_normalizations": 1,
        "navigation_v8_viewport_editor_bindings": 1,
    }
    return {
        "candidate": f"InverseReserve-WebArena-navigation-development-v{3 if version == 4 else 8}",
        "status": "development_complete",
        "passed": True,
        "protocol": module.PARENT_PROTOCOL_RELATIVE,
        "protocol_sha256": module.PARENT_PROTOCOL_SHA256,
        "source_commit": module.PARENT_SOURCE_COMMIT,
        "method_identity": module.parent_design.METHOD_IDENTITY,
        "partition": module.root_design.DEVELOPMENT,
        "development_states_opened": True,
        "holdout_states_opened": False,
        "development_task_ids": [399, 449, 488],
        "complete_population": True,
        "embargoed_holdout_opened": False,
        "outcome_based_exclusion_allowed": False,
        "metrics": metrics,
        "checks": {"all_claims_complete": True},
        "episode_rows": [{}, {}, {}],
        "claim_manifest": {"a": "a", "b": "b", "c": "c"},
    }


@pytest.mark.parametrize("version", [4, 9])
def test_activation_declaration_matches_original(original_package, version):
    modules = [
        importlib.import_module(prefix + f"inversereserve_webarena_navigation_holdout_v{version}")
        for prefix in ("rcrps.", "inversereserve.studies.")
    ]
    valid = development_result(modules[1], version)
    for module in modules:
        assert module.development_authorizes_holdout(valid, protocol_sha256=module.PARENT_PROTOCOL_SHA256)
    for key in valid:
        for value in (None, "invalid", False):
            candidate = copy.deepcopy(valid)
            candidate[key] = value
            results = [
                outcome(
                    lambda v, m=m: m.development_authorizes_holdout(
                        v, protocol_sha256=m.PARENT_PROTOCOL_SHA256
                    ),
                    candidate,
                )
                for m in modules
            ]
            assert results[0] == results[1], (key, value)
    for key in valid["metrics"]:
        candidate = copy.deepcopy(valid)
        candidate["metrics"][key] = -1
        assert modules[0].development_authorizes_holdout(
            candidate, protocol_sha256=modules[0].PARENT_PROTOCOL_SHA256
        ) == modules[1].development_authorizes_holdout(
            candidate, protocol_sha256=modules[1].PARENT_PROTOCOL_SHA256
        )


@pytest.mark.parametrize("version", [4, 9])
def test_child_protocol_declaration_matches_original(original_package, monkeypatch, version):
    modules = [
        importlib.import_module(prefix + f"inversereserve_webarena_navigation_holdout_v{version}")
        for prefix in ("rcrps.", "inversereserve.studies.")
    ]
    protocols = []
    contexts = []
    for module in modules:
        parent = {
            "execution": {"suite_activation": {"primary_result": {"path": "fixture", "sha256": "a" * 64}}},
            "embargoed_holdout": {"episodes": module.root_design.stage_manifest(module.root_design.HOLDOUT)},
            "source_sha256": {},
        }
        # A real invalid parent is rejected before any child validation.
        with pytest.raises((ValueError, KeyError)):
            if version == 4:
                module._validate_parent({}, parent_parent_protocol={}, root_protocol={})
            else:
                module._validate_parent({}, root_protocol={})
        monkeypatch.setattr(module, "_validate_parent", lambda *_args, **_kwargs: None)
        context = {
            "parent_protocol": parent,
            "parent_parent_protocol": {},
            "root_protocol": {},
            "parent_result": development_result(module, version),
        }
        parameters = inspect.signature(module.build_protocol).parameters
        context = {k: v for k, v in context.items() if k in parameters}
        protocol = module.build_protocol(
            **context,
            parent_result_sha256=getattr(module, "PARENT_RESULT_SHA256", "b" * 64),
            source_commit="a" * 40,
            source_sha256={name: "c" * 64 for name in module.required_source_paths(parent)},
            preregistration_sha256="d" * 64,
            created_utc="2026-01-01T00:00:00Z",
        )
        protocols.append(protocol)
        contexts.append(context)
    assert protocols[0].keys() == protocols[1].keys()
    for key in protocols[0]:
        for value in (None, "invalid"):
            results = []
            for module, protocol, context in zip(modules, protocols, contexts, strict=True):
                candidate = copy.deepcopy(protocol)
                candidate[key] = value
                results.append(
                    outcome(
                        lambda v, module=module, context=context: module.validate_protocol_shape(
                            v, **context
                        ),
                        candidate,
                    )
                )
            assert results[0] == results[1], (key, value)
