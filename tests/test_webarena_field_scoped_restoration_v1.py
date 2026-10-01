from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import TransactionContractV4  # noqa: E402
from rcrps.typed_observation import (  # noqa: E402
    SemanticElement,
    SemanticSnapshot,
)
from rcrps.webarena_field_scoped_restoration_v1 import (  # noqa: E402
    FIELD_RESTORATION_PROJECTION_V1,
    FailClosedWebArenaFieldRuntimeV1,
    check_editable_field_restoration_v1,
)
import rcrps.webarena_multifield_agent_v3 as agent_module  # noqa: E402


def element(
    bid: str,
    *,
    role: str = "generic",
    tag: str = "div",
    value: str | None = None,
    readonly: bool = False,
    disabled: bool = False,
    visible: bool = True,
) -> SemanticElement:
    properties: dict[str, object] = {}
    attributes: dict[str, str] = {}
    if value is not None:
        properties["value"] = value
        attributes["value"] = value
    if readonly:
        properties["readonly"] = True
    if disabled:
        properties["disabled"] = True
    return SemanticElement(
        bid=bid,
        role=role,
        name=bid,
        subtree_text="",
        ax_properties=tuple(sorted(properties.items())),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted(attributes.items())),
        dom_parent_bid=None,
        visible=visible,
        clickable=True,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def snapshot(
    *,
    target_value: str = "",
    target_readonly: bool = False,
    target_disabled: bool = False,
    extra: tuple[SemanticElement, ...] = (),
) -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element(
                "target",
                role="textbox",
                tag="textarea",
                value=target_value,
                readonly=target_readonly,
                disabled=target_disabled,
            ),
            element("submit", role="button", tag="button"),
            *extra,
        )
    )


def contract() -> TransactionContractV4:
    return TransactionContractV4(
        kind="editable_field_assignment",
        semantic_bid="target",
        action=ContractActionV4("fill", "target", "new value"),
        inverse_actions=(ContractActionV4("fill", "target", ""),),
        expected_value="new value",
        prior_value="",
        projection_kind="editable_field_assignment",
    )


def test_unrelated_dynamic_form_nodes_do_not_expand_owned_projection() -> None:
    before = snapshot()
    restored = snapshot(
        extra=(
            element("dynamic", role="textbox", tag="input", value="async"),
            element("cancel", role="button", tag="button"),
        )
    )
    check = check_editable_field_restoration_v1(
        before,
        restored,
        contract(),
    )
    assert check.passed
    assert check.delta.added_visible_bids == ("cancel", "dynamic")


@pytest.mark.parametrize(
    ("value", "readonly", "disabled"),
    (
        ("not restored", False, False),
        ("", True, False),
        ("", False, True),
    ),
)
def test_target_value_and_status_mismatches_fail_closed(
    value: str,
    readonly: bool,
    disabled: bool,
) -> None:
    check = check_editable_field_restoration_v1(
        snapshot(),
        snapshot(
            target_value=value,
            target_readonly=readonly,
            target_disabled=disabled,
        ),
        contract(),
    )
    assert not check.passed


def test_runtime_audits_global_delta_but_certifies_declared_field() -> None:
    runtime = FailClosedWebArenaFieldRuntimeV1(
        lambda _action, _role: None,
        lambda _contract, _cost: True,
    )
    check = runtime._check_restoration(
        snapshot(),
        snapshot(
            extra=(
                element("dynamic", role="textbox", tag="input", value="async"),
            )
        ),
        contract(),
        trigger="test cleanup",
    )
    assert check is not None and check.passed
    assert runtime.events == [
        {
            "event_index": 0,
            "type": "restoration",
            "trigger": "test cleanup",
            "projection_kind": FIELD_RESTORATION_PROJECTION_V1,
            "declared_contract_projection": "editable_field_assignment",
            "semantic_bid": "target",
            "passed": True,
            "reason": "typed field value and status restored",
            "global_delta": {
                "added_visible_bids": ("dynamic",),
                "removed_visible_bids": (),
                "changed_visible_bids": (),
                "newly_visible_text": ("dynamic",),
            },
            "global_delta_empty": False,
        }
    ]


def test_v3_agent_installs_field_scoped_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = lambda _action, _role: None
    reserve = lambda _contract, _cost: True

    def fake_parent_init(self, **_kwargs) -> None:
        self.executor = executor
        self.interrupt_repair_reservation = reserve

    monkeypatch.setattr(
        agent_module.MultiFieldInverseReserveAgentV2,
        "__init__",
        fake_parent_init,
    )
    agent = agent_module.MultiFieldInverseReserveAgentV3()
    assert isinstance(agent.runtime, FailClosedWebArenaFieldRuntimeV1)
