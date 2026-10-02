from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from inversereserve.contracts.goal_contracts_v4 import compile_structured_goal
from inversereserve.contracts.pact_goal_scope_v20 import (
    navigation_contract_requires_replan_v20,
    promote_unique_exact_target_v20,
    resolved_by_commit_v20,
    suppress_repeated_navigation_v20,
)
from inversereserve.contracts.transaction_actions_v4 import ContractActionV4
from inversereserve.contracts.typed_contracts_v4 import TransactionContractV4
from inversereserve.controllers.confirmation_agents_v20 import (
    FullPactConfirmationDriverV20,
    certified_scope_consumption_metrics_v20,
)
from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4
from inversereserve.controllers.pact_controller_v20 import FailClosedTransactionRuntimeV20
from inversereserve.models.structured_planner_v4 import ActionCandidateV4, V4ActionInventory
from inversereserve.observations.typed_observation import SemanticDelta, SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


def element(
    bid: str, *, role: str = "generic", name: str = "", parent: str | None = None, clickable: bool = True
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=(),
        ax_parent_bid=parent,
        dom_tag="button" if role == "button" else "div",
        dom_attributes=(),
        dom_parent_bid=parent,
        visible=True,
        clickable=clickable,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def contract(kind: str, semantic_bid: str, action_bid: str) -> TransactionContractV4:
    if kind == "editable_field_assignment":
        return TransactionContractV4(
            kind=kind,
            semantic_bid=semantic_bid,
            action=ContractActionV4("fill", action_bid, "new"),
            inverse_actions=(ContractActionV4("fill", action_bid, "old"),),
            expected_value="new",
            prior_value="old",
            projection_kind=kind,
        )
    return TransactionContractV4(
        kind=kind,
        semantic_bid=semantic_bid,
        action=ContractActionV4("click", action_bid),
        inverse_actions=(ContractActionV4("click", action_bid),),
        projection_kind="global",
    )


def candidate(
    bid: str,
    *,
    role: str,
    label: str,
    semantic_bid: str | None = None,
    parent: str | None = None,
    kind: str | None = None,
) -> ActionCandidateV4:
    return ActionCandidateV4(
        bid=bid,
        action=ContractActionV4("click", bid),
        role=role,
        label=label,
        state=(),
        transaction_kind=kind,
        semantic_bid=semantic_bid or bid,
        parent_bid=parent,
    )


def inventory(
    current: SemanticSnapshot,
    goal: str,
    rows: tuple[ActionCandidateV4, ...],
    contracts: tuple[tuple[str, TransactionContractV4], ...],
) -> V4ActionInventory:
    return V4ActionInventory(True, "fixture", compile_structured_goal(goal, current), rows, contracts)


def transaction(
    kind: str, semantic_bid: str, action_bid: str, *, added: tuple[str, ...] = ()
) -> ActiveTransactionV4:
    value = contract(kind, semantic_bid, action_bid)
    snapshot = SemanticSnapshot(())
    return ActiveTransactionV4(value, semantic_bid, snapshot, snapshot, SemanticDelta(added, (), (), ()))


def certificate(anchor: str = "exact_target", evidence: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        allowed=True, grounding=SimpleNamespace(anchor_kind=anchor, evidence_bids=evidence)
    )


def test_v20_promotes_leaf_exact_target_and_removes_related_container_alias() -> None:
    current = SemanticSnapshot(
        (element("19", role="tab", name="Submit"), element("22", role="button", name="Submit", parent="19"))
    )
    tab = candidate("19", role="tab", label="Submit", semantic_bid="19", kind="tab_switch")
    button = candidate("22", role="button", label="Submit", semantic_bid="19", parent="19", kind="tab_switch")
    value = inventory(
        current,
        'Expand the section and click "Submit".',
        (tab, button),
        (("19", contract("tab_switch", "19", "19")), ("22", contract("tab_switch", "19", "22"))),
    )
    promoted, record = promote_unique_exact_target_v20(current, value)
    assert record is not None
    assert record["promoted_bid"] == "22"
    assert record["removed_related_alias_bids"] == ["19"]
    assert tuple((row.bid for row in promoted.candidates)) == ("22",)
    assert promoted.candidates[0].transaction_kind is None
    assert promoted.contracts == ()


def test_v20_defers_exact_target_while_typed_prerequisite_is_unopened() -> None:
    current = SemanticSnapshot(
        (
            element("16", role="tab", name="Section"),
            element("19", role="tab", name="Submit"),
            element("22", role="button", name="Submit", parent="19"),
        )
    )
    section = candidate("16", role="tab", label="Section", kind="disclosure_toggle")
    submit_tab = candidate("19", role="tab", label="Submit", kind="tab_switch")
    submit = candidate("22", role="button", label="Submit", parent="19")
    value = inventory(
        current,
        "Expand the section below and click submit.",
        (section, submit_tab, submit),
        (("16", contract("disclosure_toggle", "16", "16")), ("19", contract("tab_switch", "19", "19"))),
    )
    unchanged, record = promote_unique_exact_target_v20(current, value)
    assert record is None
    assert unchanged == value
    opened = transaction("disclosure_toggle", "16", "16")
    promoted, record = promote_unique_exact_target_v20(current, value, transaction_history=(opened,))
    assert record is not None
    assert tuple((row.bid for row in promoted.candidates)) == ("16", "22")
    assert promoted.candidates[-1].transaction_kind is None


def test_v20_promotes_unique_tree_target_but_retains_unrelated_ambiguity() -> None:
    current = SemanticSnapshot(
        (element("19", role="listitem", name="Cristin"), element("27", role="listitem", name="Emile"))
    )
    sibling = candidate("19", role="listitem", label="Cristin", kind="tree_folder_toggle")
    row = candidate("27", role="listitem", label="Emile", kind="tree_folder_toggle")
    value = inventory(
        current,
        'Find and click on the folder or file named "Emile".',
        (sibling, row),
        (
            ("19", contract("tree_folder_toggle", "19", "19")),
            ("27", contract("tree_folder_toggle", "27", "27")),
        ),
    )
    promoted, record = promote_unique_exact_target_v20(current, value)
    assert record is not None
    assert tuple((candidate.bid for candidate in promoted.candidates)) == ("19", "27")
    assert promoted.candidates[-1].transaction_kind is None
    duplicate = SemanticSnapshot(
        (element("a", role="button", name="Target"), element("b", role="button", name="Target"))
    )
    ambiguous = inventory(
        duplicate,
        'Click "Target".',
        (
            candidate("a", role="button", label="Target", kind="tab_switch"),
            candidate("b", role="button", label="Target", kind="tab_switch"),
        ),
        (("a", contract("tab_switch", "a", "a")), ("b", contract("tab_switch", "b", "b"))),
    )
    unchanged, record = promote_unique_exact_target_v20(duplicate, ambiguous)
    assert record is None
    assert unchanged == ambiguous


def test_v20_resolves_structural_menu_path_and_terminal_navigation_suffix() -> None:
    current = SemanticSnapshot(
        (
            element("root", clickable=False),
            element("menu1", role="menuitem", name="Parent", parent="root"),
            element("menu2", role="menuitem", name="Child", parent="menu1"),
            element("leaf", role="menuitem", name="Target", parent="menu2"),
            element("submit", role="button", name="Submit", parent="root"),
        )
    )
    active = (
        transaction("menu_hover", "menu1", "menu1", added=("menu2",)),
        transaction("menu_hover", "menu2", "menu2", added=("leaf",)),
    )
    target = candidate("leaf", role="menuitem", label="Target")
    resolved = resolved_by_commit_v20(
        current=current,
        candidate=target,
        active_transactions=active,
        certificate=certificate(),
        terminal=False,
    )
    assert resolved == ("menu1", "menu2")
    disclosure = (transaction("disclosure_toggle", "section", "section"),)
    terminal = resolved_by_commit_v20(
        current=current,
        candidate=candidate("submit", role="button", label="Submit"),
        active_transactions=disclosure,
        certificate=certificate(),
        terminal=True,
    )
    assert terminal == ("section",)


def test_v20_runtime_consumes_exact_navigation_suffix_fail_closed() -> None:
    value = FailClosedTransactionRuntimeV20(
        lambda _action, _role: None, lambda _contract: None, lambda _contract: None
    )
    value.active = [transaction("menu_hover", "menu1", "menu1"), transaction("menu_hover", "menu2", "menu2")]
    consumed = value.consume_resolved_commit_scope_v20(
        ("menu1", "menu2"), commit_bid="leaf", anchor_kind="exact_target", evidence_bids=()
    )
    assert len(consumed) == 2
    assert value.active == []
    assert value.halted is False
    assert value.events[-1]["allowed"] is True
    unsupported = FailClosedTransactionRuntimeV20(
        lambda _action, _role: None, lambda _contract: None, lambda _contract: None
    )
    unsupported.active = [transaction("arbitrary_crossing_scope", "other", "other")]
    assert (
        unsupported.consume_resolved_commit_scope_v20(
            ("other",), commit_bid="leaf", anchor_kind="exact_target", evidence_bids=()
        )
        == ()
    )
    assert unsupported.halted is True


def test_v20_preserves_terminal_v19_goal_mutation_discharge() -> None:
    current = SemanticSnapshot((element("submit", role="button", name="Submit"),))
    mutation = transaction("editable_field_assignment", "user", "user")
    resolved = resolved_by_commit_v20(
        current=current,
        candidate=candidate("submit", role="button", label="Submit"),
        active_transactions=(mutation,),
        certificate=certificate("state_supported_form_action", ("user",)),
        terminal=False,
    )
    assert resolved == ()
    resolved = resolved_by_commit_v20(
        current=current,
        candidate=candidate("submit", role="button", label="Submit"),
        active_transactions=(mutation,),
        certificate=certificate("state_supported_form_action", ("user",)),
        terminal=True,
    )
    assert resolved == ("user",)
    value = FailClosedTransactionRuntimeV20(
        lambda _action, _role: None, lambda _contract: None, lambda _contract: None
    )
    value.active = [mutation]
    consumed = value.consume_resolved_commit_scope_v20(
        resolved, commit_bid="submit", anchor_kind="state_supported_form_action", evidence_bids=("user",)
    )
    assert len(consumed) == 1
    assert value.active == []
    assert value.halted is False
    driver = SimpleNamespace(runtime=value, trace=[])
    assert certified_scope_consumption_metrics_v20(driver)["goal_mutation_consumption_passes_v20"] == 1


def test_v20_driver_consumes_only_after_effective_terminal_commit() -> None:
    current = SemanticSnapshot(
        (element("section", role="tab", name="Section"), element("submit", role="button", name="Submit"))
    )
    target = candidate("submit", role="button", label="Submit")
    active = transaction("disclosure_toggle", "section", "section")
    value = FullPactConfirmationDriverV20.__new__(FullPactConfirmationDriverV20)
    value.runtime = FailClosedTransactionRuntimeV20(
        lambda _action, _role: None, lambda _contract: None, lambda _contract: None
    )
    value.runtime.active = [active]
    value.trace = []
    value.resolved_semantic_bids = set()
    value._pending_commit_scope_v20 = None
    value._commit_contexts_v20 = {
        "submit": {
            "current": current,
            "candidate": target,
            "certificate": certificate(),
            "active_transactions": (active,),
        }
    }
    value.audit(
        {
            "type": "certified_commit_result_v8",
            "bid": "submit",
            "executed": True,
            "halted": False,
            "terminal": True,
        }
    )
    value.audit({"type": "commit_effect_result_v8", "effective": True})
    assert value.runtime.active == []
    assert value.resolved_semantic_bids == {"section"}
    assert certified_scope_consumption_metrics_v20(value)["goal_navigation_consumption_passes_v20"] == 1
    retained = transaction("disclosure_toggle", "section", "section")
    value.runtime.active = [retained]
    value._commit_contexts_v20["submit"]["active_transactions"] = (retained,)
    value.audit(
        {
            "type": "certified_commit_result_v8",
            "bid": "submit",
            "executed": True,
            "halted": False,
            "terminal": True,
        }
    )
    value.audit({"type": "commit_effect_result_v8", "effective": False})
    assert value.runtime.active == [retained]


def test_v20_suppresses_retyped_navigation_and_replans_outside_top_scope() -> None:
    current = SemanticSnapshot(
        (
            element("parent", clickable=False),
            element("one", role="tab", name="One", parent="parent"),
            element("child", role="tab", name="Child", parent="one"),
            element("two", role="tab", name="Two", parent="parent"),
        )
    )
    top = transaction("disclosure_toggle", "one", "one", added=("child",))
    nested = contract("tab_switch", "child", "child")
    sibling = contract("tab_switch", "two", "two")
    assert not navigation_contract_requires_replan_v20(current, nested, (top,))
    assert navigation_contract_requires_replan_v20(current, sibling, (top,))
    rows = (
        candidate("one", role="tab", label="One", kind="tab_switch"),
        candidate("two", role="tab", label="Two", kind="tab_switch"),
    )
    value = inventory(
        current,
        'Find and click "Target".',
        rows,
        (("one", contract("tab_switch", "one", "one")), ("two", contract("tab_switch", "two", "two"))),
    )
    filtered = suppress_repeated_navigation_v20(
        value,
        active_transactions=(),
        completed_transactions=({"transaction_kind": "disclosure_toggle", "semantic_bid": "one"},),
    )
    assert tuple((row.bid for row in filtered.candidates)) == ("two",)
