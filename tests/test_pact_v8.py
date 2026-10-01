from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rcrps.action_envelope_v8 import assemble_action_envelope_v8  # noqa: E402
from rcrps.effect_ledger_v8 import CommitEffectLedgerV8  # noqa: E402
from rcrps.pact_controller_v4 import ActiveTransactionV4  # noqa: E402
from rcrps.pact_controller_v8 import inverse_action_cost_v8  # noqa: E402
from rcrps.pact_grounding_v8 import (  # noqa: E402
    certify_commit_v8,
    verify_commit_grounding_v8,
)
from rcrps.structured_planner_v4 import ActionCandidateV4  # noqa: E402
from rcrps.structured_planner_v6 import compile_v6_inventory  # noqa: E402
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import (  # noqa: E402
    TransactionContractV4,
    check_transaction_postcondition,
    infer_transaction_contract,
)
from rcrps.typed_contracts_v8 import (  # noqa: E402
    check_transaction_postcondition_v8,
)
from rcrps.typed_observation import (  # noqa: E402
    SemanticDelta,
    SemanticElement,
    SemanticSnapshot,
)


def element(
    bid: str,
    *,
    role: str = "generic",
    name: str = "",
    text: str = "",
    tag: str = "div",
    attributes: dict[str, str] | None = None,
    properties: dict[str, object] | None = None,
    dom_parent: str | None = None,
    clickable: bool = False,
    x: float = 0.0,
    y: float = 0.0,
) -> SemanticElement:
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=text,
        ax_properties=tuple(sorted((properties or {}).items())),
        ax_parent_bid=None,
        dom_tag=tag,
        dom_attributes=tuple(sorted((attributes or {}).items())),
        dom_parent_bid=dom_parent,
        visible=True,
        clickable=clickable,
        bbox=(x, y, 20.0, 10.0),
    )


def candidate(
    bid: str,
    *,
    label: str,
    role: str = "option",
    transaction_kind: str | None = None,
    semantic_bid: str | None = None,
) -> ActionCandidateV4:
    return ActionCandidateV4(
        bid=bid,
        action=ContractActionV4("click", bid),
        role=role,
        label=label,
        state=(),
        transaction_kind=transaction_kind,
        semantic_bid=semantic_bid or bid,
        parent_bid=None,
    )


def autocomplete_contract(bid: str, expected: str) -> TransactionContractV4:
    return TransactionContractV4(
        kind="autocomplete_query",
        semantic_bid=bid,
        action=ContractActionV4("fill", bid, expected, True),
        inverse_actions=(
            ContractActionV4("press", bid, "Escape"),
            ContractActionV4("fill", bid, "", False),
        ),
        expected_value=expected,
        prior_value="",
        projection_kind="autocomplete_query",
    )


def test_v8_autocomplete_fallback_requires_three_public_signals() -> None:
    before = SemanticSnapshot(
        (
            element("body"),
            element(
                "field",
                role="textbox",
                name="Tags:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": ""},
                properties={"readonly": False, "value": ""},
                dom_parent="body",
                clickable=True,
            ),
        )
    )
    goal = compile_v6_inventory(
        before, 'Enter an item that starts with "Ma" and ends with "nia".'
    ).goal_contract
    contract = infer_transaction_contract(before, "field", goal).contract
    assert contract is not None
    lagged = SemanticSnapshot(
        (
            element("body"),
            element(
                "field",
                role="textbox",
                name="Tags:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": "Ma"},
                properties={"readonly": False, "value": ""},
                dom_parent="body",
                clickable=True,
            ),
            element(
                "menu",
                role="list",
                name="Macao Macedonia Madagascar",
                tag="ul",
                attributes={"class": "ui-autocomplete"},
                dom_parent="body",
            ),
        )
    )
    assert not check_transaction_postcondition(before, lagged, contract).passed
    repaired = check_transaction_postcondition_v8(before, lagged, contract)
    assert repaired.passed
    assert "corroborate" in repaired.reason

    unrelated = SemanticSnapshot(
        (
            before.get("body"),
            element(
                "field",
                role="textbox",
                name="Tags:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": "Ma"},
                properties={"readonly": False, "value": ""},
                dom_parent="body",
                clickable=True,
            ),
            element(
                "menu",
                role="list",
                name="Zurich",
                tag="ul",
                attributes={"class": "ui-autocomplete"},
                dom_parent="body",
            ),
        )
    )
    assert not check_transaction_postcondition_v8(before, unrelated, contract).passed


def flight_initial() -> SemanticSnapshot:
    return SemanticSnapshot(
        (
            element("form", text="From To Departure Date Search"),
            element(
                "19",
                role="textbox",
                name="From:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": "BRL"},
                properties={"readonly": False, "value": "BRL"},
                dom_parent="form",
                clickable=True,
            ),
            element(
                "21",
                role="textbox",
                name="To:",
                tag="input",
                attributes={"class": "ui-autocomplete-input", "value": "CAK"},
                properties={"readonly": False, "value": "CAK"},
                dom_parent="form",
                clickable=True,
            ),
            element(
                "25",
                role="textbox",
                name="Departure Date",
                tag="input",
                attributes={
                    "class": "hasDatepicker",
                    "readonly": "",
                    "value": "11/22/2016",
                },
                properties={"readonly": True, "value": "11/22/2016"},
                dom_parent="form",
                clickable=True,
            ),
            element(
                "27",
                role="button",
                name="Search",
                tag="button",
                dom_parent="form",
                clickable=True,
            ),
        )
    )


def active_autocomplete(
    *,
    before: SemanticSnapshot,
    after: SemanticSnapshot,
    added: tuple[str, ...],
) -> ActiveTransactionV4:
    contract = autocomplete_contract("21", "CAK")
    return ActiveTransactionV4(
        contract=contract,
        candidate_label="To:",
        before=before,
        after=after,
        delta=SemanticDelta(added, (), ("21",), tuple()),
    )


def test_v8_equivalent_airport_codes_choose_one_public_representative() -> None:
    before = flight_initial()
    current = SemanticSnapshot(
        before.elements
        + (
            element(
                "surface",
                role="list",
                name="Akron Canton",
                tag="ul",
                attributes={"class": "ui-autocomplete"},
            ),
            element("40", role="option", name="Akron, OH (CAK)", clickable=True, y=10),
            element("41", role="option", name="Canton, OH (CAK)", clickable=True, y=20),
        )
    )
    goal = compile_v6_inventory(
        before,
        "Book the shortest one-way flight from: BRL to: CAK on 11/22/2016.",
    ).goal_contract
    rows = (
        candidate("40", label="Akron, OH (CAK)"),
        candidate("41", label="Canton, OH (CAK)"),
    )
    active = (active_autocomplete(before=before, after=current, added=("40", "41")),)
    first = verify_commit_grounding_v8(
        current=current,
        goal=goal,
        candidate=rows[0],
        inventory=rows,
        active_transactions=active,
    )
    second = verify_commit_grounding_v8(
        current=current,
        goal=goal,
        candidate=rows[1],
        inventory=rows,
        active_transactions=active,
    )
    assert first.allowed and first.anchor_kind == "active_field_equivalence"
    assert first.certified_bid == "40"
    assert not second.allowed


def test_v8_terminal_form_commit_requires_overlay_resolution() -> None:
    current = flight_initial()
    goal = compile_v6_inventory(
        current,
        "Book the shortest one-way flight from: BRL to: CAK on 11/22/2016.",
    ).goal_contract
    search = candidate("27", label="Search", role="button")
    active = (
        active_autocomplete(before=current, after=current, added=()),
    )
    blocked = verify_commit_grounding_v8(
        current=current,
        goal=goal,
        candidate=search,
        inventory=(search,),
        active_transactions=active,
    )
    assert not blocked.allowed
    assert blocked.anchor_kind == "unresolved_transaction_barrier"
    admitted = verify_commit_grounding_v8(
        current=current,
        goal=goal,
        candidate=search,
        inventory=(search,),
        active_transactions=active,
        resolved_semantic_bids=("21",),
    )
    assert admitted.allowed
    assert admitted.anchor_kind == "state_supported_form_action"


def test_v8_no_effect_commit_is_quarantined_at_same_state_and_stack() -> None:
    snapshot = SemanticSnapshot(
        (element("1", role="button", name="Continue", tag="button", clickable=True),)
    )
    inventory = compile_v6_inventory(snapshot, 'Click on a "button" widget.')
    row = next(candidate for candidate in inventory.candidates if candidate.bid == "1")
    initial = certify_commit_v8(
        current=snapshot,
        goal=inventory.goal_contract,
        candidate=row,
        inventory=inventory.candidates,
        active_transactions=(),
    )
    assert initial.allowed
    ledger = CommitEffectLedgerV8()
    effect = ledger.assess(
        before=snapshot,
        after=snapshot,
        action=row.action,
        active_transactions=(),
        terminal=False,
    )
    assert not effect.effective and effect.quarantined
    repeated = certify_commit_v8(
        current=snapshot,
        goal=inventory.goal_contract,
        candidate=row,
        inventory=inventory.candidates,
        active_transactions=(),
        quarantined_commit_keys=ledger.frozen_quarantine(),
    )
    assert not repeated.allowed
    assert repeated.grounding.anchor_kind == "no_effect_quarantine"


def test_v8_overlay_envelope_withholds_unrelated_typed_controls() -> None:
    before = flight_initial()
    active = (active_autocomplete(before=before, after=before, added=()),)
    date = candidate(
        "25",
        label="Departure Date",
        role="textbox",
        transaction_kind="datepicker_open",
        semantic_bid="25",
    )
    envelope = assemble_action_envelope_v8(
        candidates=(date,),
        active_transactions=active,
    )
    assert envelope.decision == "abstain"
    assert "unrelated actions are withheld" in envelope.reason


def test_v8_inverse_cost_counts_static_and_dynamic_inverses() -> None:
    assert inverse_action_cost_v8(autocomplete_contract("field", "Ma")) == 2
    dynamic = TransactionContractV4(
        kind="calendar_month_shift",
        semantic_bid="date",
        action=ContractActionV4("click", "next"),
        inverse_actions=(),
        projection_kind="calendar_month_shift",
        prior_calendar=(10, 2016),
        expected_calendar=(11, 2016),
        dynamic_inverse_class_token="ui-datepicker-prev",
    )
    assert inverse_action_cost_v8(dynamic) == 1
