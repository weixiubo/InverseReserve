from __future__ import annotations

from pathlib import Path

import pytest

from inversereserve.contracts.pact_grounding_v3 import (
    TargetConstraint,
    compile_target_constraint,
    exploration_query,
    satisfies_constraint,
    supporting_public_values,
    verify_commit_constraint,
)
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

ROOT = Path(__file__).resolve().parents[1]


def element(
    bid: str, *, role: str, name: str = "", value: str | None = None, visible: bool = True
) -> SemanticElement:
    properties = () if value is None else (("value", value),)
    return SemanticElement(
        bid=bid,
        role=role,
        name=name,
        subtree_text=name,
        ax_properties=properties,
        ax_parent_bid=None,
        dom_tag="input" if role in {"combobox", "textbox"} else "button",
        dom_attributes=(),
        dom_parent_bid=None,
        visible=visible,
        clickable=True,
        bbox=(0.0, 0.0, 10.0, 10.0),
    )


def test_compile_exact_prefix_suffix_and_path_constraints() -> None:
    both = compile_target_constraint('Enter an item that starts with "Mon" and ends with "ia".')
    prefix = compile_target_constraint('Enter an item that starts with "Ca".')
    suffix = compile_target_constraint('Choose an item that ends with "stan".')
    path = compile_target_constraint("Select Parent > Child > Leaf")
    quoted = compile_target_constraint('Click the item labeled "Open settings".')
    submit = compile_target_constraint("Complete the form and submit it.")
    assert both.constraint == TargetConstraint("prefix_suffix", prefix="Mon", suffix="ia")
    assert prefix.constraint == TargetConstraint("prefix", prefix="Ca")
    assert suffix.constraint == TargetConstraint("suffix", suffix="stan")
    assert path.constraint == TargetConstraint("exact", exact="Leaf")
    assert quoted.constraint == TargetConstraint("exact", exact="Open settings")
    assert submit.constraint == TargetConstraint("exact", exact="Submit")


def test_compile_fails_closed_without_positive_public_constraint() -> None:
    result = compile_target_constraint("Do what is appropriate on this page.")
    assert not result.allowed
    assert result.constraint is None
    assert "no supported positive" in result.reason
    assert not compile_target_constraint(" ").allowed


@pytest.mark.parametrize(
    "goal",
    [
        'Type "Mongolia" into the "Country" field.',
        'Remember "Submit" but do not submit the form.',
        "Compare A > B without selecting either item.",
        'The page mentions "Open settings".',
    ],
)
def test_compile_rejects_quoted_values_not_grammatically_marked_as_targets(goal: str) -> None:
    assert not compile_target_constraint(goal).allowed


def test_compile_uses_the_last_explicit_action_target_not_the_last_quote() -> None:
    result = compile_target_constraint(
        'For user "alice", click the button labeled "Like", then type "thanks".'
    )
    assert result.constraint == TargetConstraint("exact", exact="Like")


@pytest.mark.parametrize(
    ("value", "constraint", "expected"),
    [
        ("Open settings", TargetConstraint("exact", exact="Open settings"), True),
        ("  OPEN   SETTINGS ", TargetConstraint("exact", exact="open settings"), True),
        ("X", TargetConstraint("exact", exact="Close"), True),
        ("Mongolia", TargetConstraint("prefix", prefix="Mon"), True),
        ("Pakistan", TargetConstraint("suffix", suffix="stan"), True),
        ("Mongolia", TargetConstraint("prefix_suffix", prefix="Mon", suffix="ia"), True),
        ("Monaco", TargetConstraint("prefix_suffix", prefix="Mon", suffix="ia"), False),
        ("", TargetConstraint("prefix", prefix="Mon"), False),
    ],
)
def test_constraint_verifier_has_explicit_string_semantics(
    value: str, constraint: TargetConstraint, expected: bool
) -> None:
    assert satisfies_constraint(value, constraint) is expected


def test_exploration_query_is_derived_only_from_positive_prefix_or_exact() -> None:
    assert exploration_query(TargetConstraint("exact", exact="Canada")) == "Canada"
    assert exploration_query(TargetConstraint("prefix", prefix="Can")) == "Can"
    assert exploration_query(TargetConstraint("prefix_suffix", prefix="Can", suffix="da")) == "Can"
    assert exploration_query(TargetConstraint("suffix", suffix="stan")) is None


def test_option_label_commit_uses_compiled_constraint_directly() -> None:
    snapshot = SemanticSnapshot(())
    certificate = verify_commit_constraint(
        goal='Enter an item that starts with "Mon" and ends with "ia".',
        candidate_label="Mongolia",
        candidate_role="option",
        current=snapshot,
    )
    assert certificate.allowed
    assert certificate.supporting_value_bids == ()
    rejected = verify_commit_constraint(
        goal='Enter an item that starts with "Mon" and ends with "ia".',
        candidate_label="Monaco",
        candidate_role="option",
        current=snapshot,
    )
    assert not rejected.allowed


def test_submit_requires_one_matching_visible_public_input_value() -> None:
    goal = 'Enter an item that starts with "Mon" and ends with "ia".'
    matching = SemanticSnapshot((element("input1", role="combobox", value="Mongolia"),))
    certificate = verify_commit_constraint(
        goal=goal, candidate_label="Submit", candidate_role="button", current=matching
    )
    assert certificate.allowed
    assert certificate.supporting_value_bids == ("input1",)
    empty = SemanticSnapshot((element("input1", role="combobox", value=""),))
    assert not verify_commit_constraint(
        goal=goal, candidate_label="Submit", candidate_role="button", current=empty
    ).allowed
    ambiguous = SemanticSnapshot(
        (
            element("input1", role="combobox", value="Mongolia"),
            element("input2", role="textbox", value="Montesia"),
        )
    )
    ambiguous_certificate = verify_commit_constraint(
        goal=goal, candidate_label="Submit", candidate_role="button", current=ambiguous
    )
    assert not ambiguous_certificate.allowed
    assert ambiguous_certificate.supporting_value_bids == ("input1", "input2")


def test_hidden_or_nontext_values_cannot_support_terminal_form_commit() -> None:
    constraint = TargetConstraint("exact", exact="Canada")
    snapshot = SemanticSnapshot(
        (
            element("hidden", role="textbox", value="Canada", visible=False),
            element("status", role="status", value="Canada"),
        )
    )
    assert supporting_public_values(snapshot, constraint) == ()


def test_constraint_dataclass_rejects_incoherent_fields() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        TargetConstraint("contains", exact="x")
    with pytest.raises(ValueError, match="invalid fields"):
        TargetConstraint("exact", exact="x", prefix="x")
    with pytest.raises(ValueError, match="invalid fields"):
        TargetConstraint("prefix", prefix="")
    with pytest.raises(ValueError, match="invalid fields"):
        TargetConstraint("exact", exact="   ")
