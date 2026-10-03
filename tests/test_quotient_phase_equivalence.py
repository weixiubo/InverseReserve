"""Fixed-observation comparisons against the complete hash-verified original search."""

import sys
from dataclasses import asdict
from types import ModuleType

import numpy as np
import pytest

from inversereserve.interface import PreviewObservation
from inversereserve.quotient_search import QuotientConfig, generate_quotient_query_order

from .reference_support import read_reference


@pytest.fixture(scope="module")
def original():
    source = read_reference("src/rcrps/quotient_search.py").decode()
    module = ModuleType("inverse_original_quotient")
    module.__package__ = "inversereserve"
    sys.modules[module.__name__] = module
    exec(compile(source, "frozen-original-quotient", "exec"), vars(module))
    yield module.generate_quotient_query_order
    del sys.modules[module.__name__]


def evidence(mode, point):
    x, y = (int(value) for value in point)
    if mode == "null":
        return ""
    if mode == "constant":
        return "one"
    if mode == "horizontal":
        return f"x-{x // 8}"
    if mode == "vertical":
        return f"y-{y // 8}"
    if mode == "repeated":
        return f"x-{(x // 8) % 2}-y-{(y // 8) % 2}"
    if mode == "sparse" and (x + y) % 3:
        return ""
    return f"x-{x // 8}-y-{y // 8}"


@pytest.mark.parametrize("mode", ["null", "constant", "horizontal", "vertical", "grid", "repeated", "sparse"])
@pytest.mark.parametrize(
    "progressive,allowed,posterior,budget",
    [
        (False, True, "quotient", 120),
        (True, True, "quotient", 120),
        (True, False, "static_tail", 60),
        (False, True, "static_tail", 24),
    ],
)
def test_query_order_budget_and_topology_are_unchanged(
    original, mode, progressive, allowed, posterior, budget
):
    calls = []

    def observe(point):
        calls.append(point)
        value = evidence(mode, point)
        return PreviewObservation(point=point, positive=bool(value), evidence=value)

    points = [(64, 64)] + [(x, y) for x in range(8, 128, 16) for y in range(8, 128, 16)]
    pool = [{"point": point, "source": "fixture"} for point in points]
    kwargs = dict(
        width=128,
        height=128,
        pool=pool,
        observe=observe,
        descriptors=np.random.default_rng(2701).normal(size=(len(pool), 4)).astype(np.float32),
        config=QuotientConfig(8, 8, 4),
        maximum_queries=budget,
        seed_maximum=8,
        maximum_inducing=8,
        progressive_rank_two=progressive,
        allow_rank_two=allowed,
        posterior_mode=posterior,
    )
    expected = original(**kwargs)
    expected_calls = calls[:]
    calls.clear()
    actual = generate_quotient_query_order(**kwargs)
    assert asdict(actual) == asdict(expected)
    assert calls == expected_calls
    assert len(actual.events) <= budget
    assert len(calls) == len(set(calls))


def test_topology_disabled_and_duplicate_pool_coordinates(original):
    points = [(10, 10), (10, 10), (20, 20)]
    kwargs = dict(
        width=40,
        height=40,
        pool=[{"point": point, "source": "fixture"} for point in points],
        observe=lambda point: PreviewObservation(point, True, "positive"),
        descriptors=np.ones((3, 4)),
        config=QuotientConfig(8, 8, 2),
        maximum_queries=4,
        seed_maximum=1,
        enable_topology=False,
        posterior_mode="static_tail",
    )
    assert asdict(generate_quotient_query_order(**kwargs)) == asdict(original(**kwargs))
