"""Preserve posterior, refinement and manifold event ordering through state extraction."""

import sys
from dataclasses import asdict
from types import ModuleType

import numpy as np
import pytest

from inversereserve.interface import PreviewObservation
from inversereserve.search import GeometryConfig, KernelConfig, generate_query_order

from .reference_support import read_reference
from .test_quotient_phase_equivalence import evidence


@pytest.fixture(scope="module")
def original_search():
    source = read_reference("src/rcrps/search.py").decode()
    module = ModuleType("inverse_original_local")
    module.__package__ = "inversereserve"
    sys.modules[module.__name__] = module
    exec(compile(source, "frozen-original-local", "exec"), vars(module))
    yield module.generate_query_order
    del sys.modules[module.__name__]


@pytest.mark.parametrize("mode", ["null", "constant", "horizontal", "grid", "sparse"])
@pytest.mark.parametrize("budget", [0, 1, 16, 64])
def test_local_posterior_refinement_and_trace_events_match(original_search, mode, budget):
    calls = []

    def observe(point):
        calls.append(point)
        value = evidence(mode, point)
        return PreviewObservation(point, bool(value), value)

    pool = [
        {"point": point, "source": "fixture"}
        for point in [(64, 64)] + [(x, y) for x in range(9, 128, 17) for y in range(9, 128, 17)]
    ]
    options = dict(
        width=128,
        height=128,
        pool=pool,
        observe=observe,
        descriptors=np.random.default_rng(2718).normal(size=(len(pool), 4)).astype(np.float32),
        kernel=KernelConfig("dinov2_vits14", 0.1, 1.0, 2),
        geometry=GeometryConfig(4, 12, 8),
        maximum_queries=budget,
        maximum_inducing=8,
        posterior_batch_size=4,
    )
    expected = original_search(**options)
    expected_calls = calls[:]
    calls.clear()
    actual = generate_query_order(**options)
    assert [asdict(event) for event in actual] == [asdict(event) for event in expected]
    assert calls == expected_calls
    assert len(actual) <= budget
    assert len(calls) == len(set(calls))


def test_duplicate_pool_reaches_exhaustion_without_spending_budget_again():
    from inversereserve.preview.local_search import LocalSearch, LocalSearchRequest

    calls = []

    def observe(point):
        calls.append(point)
        return PreviewObservation(point, False, "")

    request = LocalSearchRequest(
        width=40,
        height=40,
        pool=[{"point": point, "source": "fixture"} for point in [(10, 10), (10, 10), (20, 20)]],
        observe=observe,
        descriptors=np.ones((3, 4)),
        kernel=KernelConfig("dinov2_vits14", 0.1, 1.0, 2),
        geometry=GeometryConfig(1, 12, 8),
        maximum_queries=20,
    )
    controller = LocalSearch(request)
    # Bound the scheduler turns so a regression fails instead of hanging the test process.
    controller.initialize()
    for _ in range(10):
        if controller.state.pool_batch_queue:
            controller.consume_pool()
        elif not controller.enqueue_posterior_batch():
            break
    else:
        pytest.fail("duplicate pool candidate prevents search exhaustion")
    assert calls == [(10.0, 10.0), (20.0, 20.0)]
    assert controller.state.excluded_pool == {1}
    assert len(controller.state.events) == 2
