from __future__ import annotations

import json
from pathlib import Path

from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import (
    certify_webarena_commit_v1,
    compile_webarena_goal_contract_v1,
    compile_webarena_inventory_v1,
    parse_reply_payload_v1,
)
from inversereserve.contracts.typed_contracts_v4 import (
    check_transaction_postcondition,
    check_transaction_restoration,
)
from inversereserve.controllers.pact_controller_v4 import ActiveTransactionV4
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot, semantic_delta

ROOT = Path(__file__).resolve().parents[1]


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
    visible: bool = True,
    clickable: bool = False,
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
        visible=visible,
        clickable=clickable,
        bbox=(0.0, 0.0, 20.0, 10.0),
    )


def reply_form(
    *, value: str = "", second_textarea: bool = False, submit_label: str = "Comment"
) -> SemanticSnapshot:
    rows = [
        element("page", text="Public forum page"),
        element("reply-form", tag="form", text="Reply form", dom_parent="page"),
        element(
            "comment",
            role="textbox",
            name="Comment",
            tag="textarea",
            attributes={"value": value},
            properties={"value": value, "readonly": False, "disabled": False},
            dom_parent="reply-form",
            clickable=False,
        ),
        element(
            "submit", role="button", name=submit_label, tag="button", dom_parent="reply-form", clickable=True
        ),
        element(
            "search",
            role="searchbox",
            name="Search",
            tag="input",
            properties={"value": ""},
            dom_parent="page",
            clickable=True,
        ),
    ]
    if second_textarea:
        rows.extend(
            [
                element("other-form", tag="form", text="Other form", dom_parent="page"),
                element(
                    "other-comment",
                    role="textbox",
                    name="Comment",
                    tag="textarea",
                    properties={"value": "", "readonly": False, "disabled": False},
                    dom_parent="other-form",
                ),
                element(
                    "other-submit",
                    role="button",
                    name="Reply",
                    tag="button",
                    dom_parent="other-form",
                    clickable=True,
                ),
            ]
        )
    return SemanticSnapshot(tuple(rows))


GOAL = 'Reply to the manager of the website in this post with "thanks! I am a big fan."'


def test_reply_payload_parser_preserves_exact_instruction_spans() -> None:
    direct = parse_reply_payload_v1(GOAL)
    assert direct is not None
    assert direct.value == "thanks! I am a big fan."
    assert direct.action_span.text == "Reply"
    assert GOAL[direct.value_span.start : direct.value_span.end] == direct.value
    possessive = parse_reply_payload_v1("Reply to the post with my comment “Yeah, traffic, you know...”")
    assert possessive is not None
    assert possessive.value == "Yeah, traffic, you know..."
    nested_reply = parse_reply_payload_v1('Reply to the first reply in this post with "don\'t panic"')
    assert nested_reply is not None
    assert nested_reply.action_span.text == "Reply"
    assert nested_reply.value == "don't panic"
    selected_wordings = (
        'Reply to the manager of the website in this post with "thanks! I am a big fan of your website."',
        'Reply to the first reply in this post with "don\'t panic"',
        'Reply to the post on this page with my comment "Yeah, pittsburgh traffic, you know..."',
    )
    assert [parse_reply_payload_v1(row).value for row in selected_wordings] == [
        "thanks! I am a big fan of your website.",
        "don't panic",
        "Yeah, pittsburgh traffic, you know...",
    ]
    assert parse_reply_payload_v1('Re-post the image using the title "from /f/pics"') is None


def test_unique_public_reply_form_compiles_fill_and_exact_inverse() -> None:
    before = reply_form(value="draft")
    contract = compile_webarena_goal_contract_v1(GOAL, before)
    assert len(contract.payload_bindings) == 1
    binding = contract.payload_bindings[0]
    assert binding.bid == "comment"
    assert binding.form_bid == "reply-form"
    assert binding.submit_bid == "submit"
    assert binding.value_span.text == "thanks! I am a big fan."
    inventory = compile_webarena_inventory_v1(before, GOAL, goal_contract=contract)
    typed = inventory.contract_by_bid["comment"]
    assert typed.kind == "editable_field_assignment"
    assert typed.expected_value == "thanks! I am a big fan."
    assert typed.prior_value == "draft"
    assert typed.action.operation == "fill"
    assert typed.action.argument == "thanks! I am a big fan."
    assert len(typed.inverse_actions) == 1
    assert typed.inverse_actions[0].argument == "draft"


def test_equivalent_base_and_adapter_bindings_deduplicate_without_value_loss() -> None:
    goal_text = 'Reply to the post with my comment "???"'
    before = reply_form()
    goal = compile_webarena_goal_contract_v1(goal_text, before)
    assert len(goal.base.field_assignments) == 1
    assert len(goal.payload_bindings) == 1
    assert len(goal.field_assignments) == 1
    assert goal.assignment_for_bid("comment").value == "???"
    inventory = compile_webarena_inventory_v1(before, goal_text, goal_contract=goal)
    typed = inventory.contract_by_bid["comment"]
    assert typed.expected_value == "???"
    assert typed.prior_value == ""


def test_ambiguous_reply_forms_fail_closed_without_a_payload_transaction() -> None:
    snapshot = reply_form(second_textarea=True)
    contract = compile_webarena_goal_contract_v1(GOAL, snapshot)
    assert contract.reply_payload is not None
    assert contract.payload_bindings == ()
    assert "exactly one" in contract.payload_resolution
    inventory = compile_webarena_inventory_v1(snapshot, GOAL, goal_contract=contract)
    assert "comment" not in inventory.contract_by_bid
    assert "other-comment" not in inventory.contract_by_bid


def test_payload_transaction_postcondition_and_restoration_are_scoped() -> None:
    before = reply_form(value="draft")
    filled = reply_form(value="thanks! I am a big fan.")
    goal = compile_webarena_goal_contract_v1(GOAL, before)
    typed = compile_webarena_inventory_v1(before, GOAL, goal_contract=goal).contract_by_bid["comment"]
    post = check_transaction_postcondition(before, filled, typed)
    restored = check_transaction_restoration(before, before, typed)
    assert post.passed is True
    assert restored.passed is True
    assert typed.projection_kind == "editable_field_assignment"


def test_commit_requires_active_exact_payload_and_unique_same_form_action() -> None:
    before = reply_form()
    filled = reply_form(value="thanks! I am a big fan.")
    goal = compile_webarena_goal_contract_v1(GOAL, before)
    before_inventory = compile_webarena_inventory_v1(before, GOAL, goal_contract=goal)
    typed = before_inventory.contract_by_bid["comment"]
    active = ActiveTransactionV4(typed, "Comment", before, filled, semantic_delta(before, filled))
    current_inventory = compile_webarena_inventory_v1(filled, GOAL, goal_contract=goal)
    submit = next((row for row in current_inventory.candidates if row.bid == "submit"))
    early = certify_webarena_commit_v1(
        current=filled,
        goal=goal,
        candidate=submit,
        inventory=current_inventory.candidates,
        active_transactions=(),
    )
    assert early.allowed is False
    admitted = certify_webarena_commit_v1(
        current=filled,
        goal=goal,
        candidate=submit,
        inventory=current_inventory.candidates,
        active_transactions=(active,),
    )
    assert admitted.allowed is True
    assert admitted.grounding.anchor_kind == "payload_form_action"
    assert admitted.grounding.evidence_bids == ("comment",)
    assert admitted.certified_action == submit.action
    assert admitted.observation_fingerprint == filled.semantic_fingerprint()


def test_adapter_record_exposes_public_only_information_boundary() -> None:
    contract = compile_webarena_goal_contract_v1(GOAL, reply_form())
    record = contract.record()
    adapter = record["webarena_public_adapter_v1"]
    assert adapter["uses_task_id"] is False
    assert adapter["uses_evaluator"] is False
    assert adapter["uses_reward"] is False
    serialized = json.dumps(record, sort_keys=True).lower()
    assert "expected answer" not in serialized
    assert "task_id" in serialized and "evaluator" in serialized and ("reward" in serialized)
