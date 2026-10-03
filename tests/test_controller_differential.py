"""Compare current controllers against the exact pre-refactor package."""

from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

import pytest

from .reference_support import copy_reference
from .test_confirmation_agents_v8 import BUDGETS, NoEffectEnvironment, forbidden_model, observation
from .test_webarena_exact_mutation_agent_v1 import (
    BUDGETS as WEB_BUDGETS,
)
from .test_webarena_exact_mutation_agent_v1 import (
    QueueEnvironment,
    exact_form,
    navigation_page,
    navigator,
)


@pytest.fixture(scope="module")
def original_package(tmp_path_factory):
    root = tmp_path_factory.mktemp("reference-inversereserve")
    copy_reference(root)
    source = str(root / "src")
    sys.path.insert(0, source)
    try:
        package = importlib.import_module("rcrps")
        assert Path(package.__file__).is_relative_to(root)
        yield package
    finally:
        sys.path.remove(source)
        for name in list(sys.modules):
            if name == "rcrps" or name.startswith("rcrps."):
                del sys.modules[name]


@pytest.mark.parametrize("version", [8, 13, 16])
@pytest.mark.parametrize("success", [False, True])
@pytest.mark.parametrize("budget", [0, 1, 4, 40])
def test_matched_controller_event_budget_and_outcome_equivalence(
    original_package, monkeypatch, version, success, budget
):
    # Exclude machine speed while preserving hard action/planner budget semantics.
    monkeypatch.setattr(time, "monotonic", lambda: 1000.0)
    results = []
    for prefix in ("rcrps", "inversereserve.controllers"):
        module = importlib.import_module(f"{prefix}.confirmation_agents_v{version}")
        cls = getattr(module, f"FullPactConfirmationDriverV{version}")
        env = NoEffectEnvironment(success=success)
        driver = cls(
            environment=env,
            observation=observation(),
            budgets={**BUDGETS, "maximum_gui_actions": budget},
            planner_generate=forbidden_model,
        )
        driver.run()
        results.append((driver.result(), env.calls))
    assert results[1] == results[0]


@pytest.mark.parametrize("version", [1, 13])
@pytest.mark.parametrize("case", ["target", "navigation", "no_effect", "lost_binding"])
def test_mutation_controller_preserves_all_events_and_recovery(original_package, monkeypatch, version, case):
    monkeypatch.setattr(time, "monotonic", lambda: 1000.0)
    results = []
    for prefix in ("rcrps", "inversereserve.adapters.webarena"):
        module = importlib.import_module(f"{prefix}.webarena_exact_mutation_agent_v{version}")
        cls = getattr(module, f"ExactMutationTransferAgentV{version}")
        initial = navigation_page() if case == "navigation" else exact_form(value="prior")
        outputs = [exact_form(value="hello"), exact_form(value="hello", saved=True)]
        if case == "navigation":
            outputs.insert(0, exact_form(value="prior"))
        if case == "no_effect":
            outputs[-1] = exact_form(value="hello")
        if case == "lost_binding":
            outputs[0] = navigation_page()
        outputs += [exact_form(value="prior")] * 8
        env = QueueEnvironment(outputs)
        agent = cls(environment=env, observation=initial, budgets=WEB_BUDGETS, planner_generate=navigator())
        agent.run()
        results.append((agent.result(), env.calls))
    assert results[1] == results[0]
