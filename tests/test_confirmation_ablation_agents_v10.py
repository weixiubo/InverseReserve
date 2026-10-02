from __future__ import annotations

from pathlib import Path

import numpy as np

from inversereserve.controllers.confirmation_ablation_agents_v9 import TypedNoCertificateConfirmationDriverV9
from inversereserve.controllers.confirmation_ablation_agents_v10 import (
    MATCHED_CONFIRMATION_DRIVERS_V10,
    RawOpenLoopConfirmationDriverV10,
    TypedNoCertificateConfirmationDriverV10,
)
from inversereserve.controllers.confirmation_ablation_agents_v11 import (
    MATCHED_CONFIRMATION_DRIVERS_V11,
    RawOpenLoopConfirmationDriverV11,
    TypedNoCertificateConfirmationDriverV11,
)
from inversereserve.controllers.confirmation_agents_v10 import (
    FullPactConfirmationDriverV10,
    RecoverySolventRepairDriverMixinV10,
)
from inversereserve.controllers.confirmation_agents_v11 import FullPactConfirmationDriverV11
from inversereserve.controllers.pact_controller_v10 import FailClosedTransactionRuntimeV10
from inversereserve.controllers.pact_controller_v11 import FailClosedTransactionRuntimeV11

ROOT = Path(__file__).resolve().parents[1]


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
            "documents": [{"nodes": {"attributes": [[1, 2]], "parentIndex": [-1], "nodeName": [0]}}],
        },
        "extra_element_properties": {
            "1": {"visibility": 1.0, "clickable": True, "bbox": [5.0, 5.0, 80.0, 30.0]}
        },
        "screenshot": np.zeros((100, 100, 3), dtype=np.uint8),
        "last_action_error": "",
    }


class NoEffectEnvironment:
    def step(self, _code: str):
        return (observation(), 0.0, False, False, {})


BUDGETS = {"maximum_gui_actions": 40, "maximum_planner_calls": 40, "maximum_wall_seconds": 30.0}


def forbidden_model(_messages):
    raise AssertionError("singleton no-certificate envelope called the model")


def test_v10_registry_is_exactly_the_prespecified_three_arm_intervention() -> None:
    assert MATCHED_CONFIRMATION_DRIVERS_V10 == {
        "raw_open_loop_v10_matched": RawOpenLoopConfirmationDriverV10,
        "typed_no_certificate_v10": TypedNoCertificateConfirmationDriverV10,
        "full_pact_v10": FullPactConfirmationDriverV10,
    }


def test_v10_no_certificate_arm_retains_recovery_solvent_runtime() -> None:
    assert issubclass(TypedNoCertificateConfirmationDriverV10, TypedNoCertificateConfirmationDriverV9)
    assert RecoverySolventRepairDriverMixinV10 in TypedNoCertificateConfirmationDriverV10.__mro__
    assert (
        TypedNoCertificateConfirmationDriverV10.interrupt_repair_reservation
        is FullPactConfirmationDriverV10.interrupt_repair_reservation
    )
    driver = TypedNoCertificateConfirmationDriverV10(
        environment=NoEffectEnvironment(),
        observation=observation(),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    assert isinstance(driver.runtime, FailClosedTransactionRuntimeV10)
    driver.run()
    result = driver.result()
    assert result["method_input"]["controller_arm"] == "typed_no_certificate_v10"
    assert result["metrics"]["uncertified_commits"] == 1
    assert result["metrics"]["interrupt_repair_reservation_audits"] == 0
    assert result["metrics"]["interrupt_repair_reservation_fallbacks"] == 0


def test_v11_rerun_registry_upgrades_every_versioned_matched_arm() -> None:
    assert MATCHED_CONFIRMATION_DRIVERS_V11 == {
        "raw_open_loop_v11_matched": RawOpenLoopConfirmationDriverV11,
        "typed_no_certificate_v11": TypedNoCertificateConfirmationDriverV11,
        "full_pact_v11": FullPactConfirmationDriverV11,
    }
    driver = TypedNoCertificateConfirmationDriverV11(
        environment=NoEffectEnvironment(),
        observation=observation(),
        budgets=BUDGETS,
        planner_generate=forbidden_model,
    )
    assert isinstance(driver.runtime, FailClosedTransactionRuntimeV11)
    assert driver.runtime._executor is driver.executor
    driver.run()
    result = driver.result()
    assert result["method_input"]["controller_arm"] == "typed_no_certificate_v11"
    assert result["metrics"]["uncertified_commits"] == 1
    assert result["metrics"]["unchanged_public_inverse_skips"] == 0
