"""Every exposed test protocol retains first-failure validation semantics."""

from __future__ import annotations

import copy
import importlib
import inspect
from pathlib import Path

from .test_controller_differential import original_package as original_package


def outcome(validate, value):
    try:
        return ("accepted", validate(value))
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        return (type(error).__name__, str(error))


def protocol_cases():
    for path in sorted(Path(__file__).parent.glob("test_inversereserve_*.py")):
        module = importlib.import_module("tests." + path.stem)
        design = getattr(module, "design", None)
        factory = getattr(module, "protocol", None)
        if design is None or factory is None or inspect.signature(factory).parameters:
            continue
        if not getattr(design, "__name__", "").startswith("inversereserve.studies."):
            continue
        names = [
            name
            for name in ("validate_protocol", "validate_protocol_shape", "validate_protocol_shape_v2")
            if hasattr(design, name)
        ]
        if len(names) == 1:
            yield design, names[0], factory()


def test_registered_protocol_requirements_match_original_failures(original_package):
    comparisons = 0
    protocols = 0
    for current, name, protocol in protocol_cases():
        previous = importlib.import_module("rcrps." + current.__name__.rsplit(".", 1)[1])
        old_validate, new_validate = getattr(previous, name), getattr(current, name)
        assert outcome(new_validate, copy.deepcopy(protocol)) == outcome(
            old_validate, copy.deepcopy(protocol)
        ), current.__name__
        protocols += 1
        for key in protocol:
            for replacement in ("missing", None, "invalid"):
                value = copy.deepcopy(protocol)
                if replacement == "missing":
                    del value[key]
                else:
                    value[key] = replacement
                assert outcome(new_validate, copy.deepcopy(value)) == outcome(
                    old_validate, copy.deepcopy(value)
                ), (current.__name__, key, replacement)
                comparisons += 1
    assert protocols >= 10
    assert comparisons >= 300
