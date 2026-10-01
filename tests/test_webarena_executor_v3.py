from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_observation import SemanticElement, SemanticSnapshot  # noqa: E402
from rcrps.webarena_executor_v3 import (  # noqa: E402
    WebArenaConfirmationExecutorV3,
)


class Screenshot:
    shape = (100, 200, 3)


def observation(url: str) -> dict[str, object]:
    return {
        "url": url,
        "goal": "edit profile",
        "axtree_object": {},
        "dom_object": {},
        "extra_element_properties": {},
        "last_action_error": "",
        "screenshot": Screenshot(),
    }


def snapshot(name: str) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            SemanticElement(
                bid="button",
                role="button",
                name=name,
                subtree_text=name,
                ax_properties=(),
                ax_parent_bid=None,
                dom_tag="button",
                dom_attributes=(),
                dom_parent_bid=None,
                visible=True,
                clickable=True,
                bbox=(0.0, 0.0, 10.0, 10.0),
            ),
        )
    )


class Environment:
    def __init__(self, next_observation: dict[str, object]) -> None:
        self.next_observation = next_observation
        self.codes: list[str] = []

    def step(self, code: str) -> tuple[dict[str, object], float, bool, bool, dict]:
        self.codes.append(code)
        return self.next_observation, 1.0, False, False, {"message": "hidden"}


def test_executor_caches_indexed_snapshot_and_uses_no_wait_navigation(
    monkeypatch,
) -> None:
    first_observation = observation("http://example.local/")
    second_observation = observation("http://example.local/profile")
    environment = Environment(second_observation)
    calls: list[str] = []

    def build(_ax, _dom, _extra) -> SemanticSnapshot:
        calls.append("build")
        return snapshot("before" if len(calls) == 1 else "after")

    monkeypatch.setattr("rcrps.webarena_executor_v3.semantic_snapshot", build)
    executor = WebArenaConfirmationExecutorV3(
        environment,
        first_observation,
        maximum_gui_actions=2,
    )
    assert executor.snapshot is executor.snapshot
    assert calls == ["build"]
    outcome = executor(ContractActionV4("click", "button"), "navigation")
    assert environment.codes == ["click_no_wait('button')"]
    assert outcome.snapshot.get("button").name == "after"
    assert calls == ["build", "build"]
    assert executor.actions[0]["reward_or_info_retained_by_method"] is False
