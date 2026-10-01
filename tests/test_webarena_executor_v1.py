from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_observation import SemanticSnapshot  # noqa: E402
from rcrps.webarena_executor_v1 import (  # noqa: E402
    WebArenaConfirmationExecutorV1,
    browsergym_code_webarena_v1,
)


class _Screen:
    shape = (720, 1280, 3)


class _Environment:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def step(self, code: str):
        self.calls.append(code)
        observation = {"screenshot": _Screen(), "last_action_error": ""}
        return observation, 0.0, False, False, {"message": "harness only"}


def test_commit_click_uses_single_shot_navigation_decoupled_backend() -> None:
    action = ContractActionV4("click", "313")
    assert browsergym_code_webarena_v1(
        action,
        "commit",
        viewport_width=1280,
        viewport_height=720,
    ) == "click_no_wait('313')"


def test_noncommit_actions_keep_frozen_browsergym_code() -> None:
    click = ContractActionV4("click", "313")
    fill = ContractActionV4("fill", "173", "???")
    assert browsergym_code_webarena_v1(
        click,
        "typed_forward",
        viewport_width=1280,
        viewport_height=720,
    ) == "click('313')"
    assert browsergym_code_webarena_v1(
        fill,
        "typed_forward",
        viewport_width=1280,
        viewport_height=720,
    ) == "fill('173', '???', False)"


def test_executor_is_an_isolated_subclass_not_a_frozen_core_edit() -> None:
    assert WebArenaConfirmationExecutorV1.__mro__[1].__name__ == (
        "ConfirmationExecutorV7"
    )


def test_executor_emits_exactly_one_commit_call_and_audits_backend(
    monkeypatch,
) -> None:
    sentinel = SemanticSnapshot(())
    monkeypatch.setattr(
        WebArenaConfirmationExecutorV1,
        "snapshot",
        property(lambda _self: sentinel),
    )
    environment = _Environment()
    executor = WebArenaConfirmationExecutorV1(
        environment,
        {"screenshot": _Screen(), "last_action_error": ""},
        maximum_gui_actions=2,
    )
    result = executor(ContractActionV4("click", "313"), "commit")

    assert environment.calls == ["click_no_wait('313')"]
    assert result.snapshot is sentinel
    assert executor.actions == [
        {
            "action_index": 0,
            "role": "commit",
            "code": "click_no_wait('313')",
            "certified_operation": "click",
            "certified_bid": "313",
            "execution_backend": "single_shot_click_no_wait",
            "reward": 0.0,
            "terminated": False,
            "truncated": False,
            "last_action_error_before": "",
            "last_action_error_after": "",
            "evaluator_reason": "harness only",
            "method_received_reward": False,
            "method_received_info": False,
        }
    ]
