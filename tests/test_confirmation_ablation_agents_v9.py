from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.confirmation_ablation_agents_v9 import (  # noqa: E402
    MATCHED_CONFIRMATION_DRIVERS_V9,
    RawOpenLoopConfirmationDriverV9,
    TypedNoCertificateConfirmationDriverV9,
)
from rcrps.confirmation_agents_v7 import (  # noqa: E402
    RawOpenLoopConfirmationDriverV7,
)
from rcrps.confirmation_agents_v9 import (  # noqa: E402
    FullPactConfirmationDriverV9,
)
from rcrps.pact_controller_v9 import (  # noqa: E402
    FailClosedTransactionRuntimeV9,
)


def observation() -> dict:
    return {
        "goal": 'Click on a "button" widget.',
        "axtree_object": {
            "nodes": [
                {
                    "nodeId": "node-1",
                    "browsergym_id": "1",
                    "role": {"value": "button"},
                    "name": {"value": "Continue"},
                    "properties": [],
                    "childIds": [],
                }
            ]
        },
        "dom_object": {
            "strings": ["button", "bid", "1"],
            "documents": [
                {
                    "nodes": {
                        "attributes": [[1, 2]],
                        "parentIndex": [-1],
                        "nodeName": [0],
                    }
                }
            ],
        },
        "extra_element_properties": {
            "1": {
                "visibility": 1.0,
                "clickable": True,
                "bbox": [5.0, 5.0, 80.0, 30.0],
            }
        },
        "screenshot": np.zeros((100, 100, 3), dtype=np.uint8),
        "last_action_error": "",
    }


class NoEffectEnvironment:
    def __init__(self, *, success: bool = False) -> None:
        self.calls: list[str] = []
        self.success = success

    def step(self, code: str):
        self.calls.append(code)
        return observation(), float(self.success), self.success, False, {}


BUDGETS = {
    "maximum_gui_actions": 40,
    "maximum_planner_calls": 40,
    "maximum_wall_seconds": 30.0,
}


def forbidden_model(_messages):
    raise AssertionError("singleton no-certificate envelope called the model")


def test_v9_matched_driver_registry_is_exact_and_core_is_untouched() -> None:
    assert MATCHED_CONFIRMATION_DRIVERS_V9 == {
        "raw_open_loop_v9_matched": RawOpenLoopConfirmationDriverV9,
        "typed_no_certificate_v9": TypedNoCertificateConfirmationDriverV9,
        "full_pact_v9": FullPactConfirmationDriverV9,
    }
    assert issubclass(
        RawOpenLoopConfirmationDriverV9,
        RawOpenLoopConfirmationDriverV7,
    )
    assert issubclass(
        TypedNoCertificateConfirmationDriverV9,
        FullPactConfirmationDriverV9,
    )


def test_no_certificate_ablation_keeps_v9_runtime_and_quarantines_no_effect() -> None:
    environment = NoEffectEnvironment()
    driver = TypedNoCertificateConfirmationDriverV9(
        environment=environment,
        observation=observation(),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    assert isinstance(driver.runtime, FailClosedTransactionRuntimeV9)
    driver.run()
    result = driver.result()
    assert result["success"] is False
    assert result["method_failure"].startswith("no-certificate envelope abstained")
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["typed_transactions"] == 0
    assert result["metrics"]["certified_commits"] == 0
    assert result["metrics"]["uncertified_commits"] == 1
    assert result["metrics"]["commit_effect_failures"] == 1
    assert result["metrics"]["quarantined_commit_keys"] == 1
    assert result["metrics"]["inverse_reservation_audits"] == 1
    assert result["metrics"]["inverse_reservation_stops"] == 0
    assert environment.calls == ["click('1')"]
    assert [row["role"] for row in result["actions"]] == ["uncertified_commit"]
    assert any(
        row["type"] == "uncertified_commit_result_v9"
        for row in result["trace"]
    )


def test_no_certificate_terminal_success_retains_effect_accounting() -> None:
    environment = NoEffectEnvironment(success=True)
    driver = TypedNoCertificateConfirmationDriverV9(
        environment=environment,
        observation=observation(),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    driver.run()
    result = driver.result()
    assert result["success"] is True
    assert result["method_failure"] is None
    assert result["metrics"]["gui_actions"] == 1
    assert result["metrics"]["certified_commits"] == 0
    assert result["metrics"]["uncertified_commits"] == 1
    assert result["metrics"]["commit_effect_passes"] == 1
    assert result["metrics"]["commit_effect_failures"] == 0
    assert result["metrics"]["quarantined_commit_keys"] == 0
