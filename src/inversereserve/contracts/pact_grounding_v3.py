"""Fail-closed public target constraints for successor PACT commits."""

from __future__ import annotations

import re
from dataclasses import dataclass

from inversereserve.observations.typed_observation import SemanticSnapshot

FORM_TERMINAL_LABELS = frozenset({"apply", "continue", "done", "save", "submit"})
TEXT_VALUE_ROLES = frozenset({"combobox", "searchbox", "textbox"})
EXACT_ALIASES = frozenset({("close", "x"), ("x", "close")})


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


@dataclass(frozen=True)
class TargetConstraint:
    kind: str
    prefix: str | None = None
    suffix: str | None = None
    exact: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"exact", "prefix", "suffix", "prefix_suffix"}:
            raise ValueError(f"unsupported target constraint: {self.kind}")
        populated = {
            "prefix": (bool(_normalize(self.prefix)) if self.prefix is not None else False),
            "suffix": (bool(_normalize(self.suffix)) if self.suffix is not None else False),
            "exact": bool(_normalize(self.exact)) if self.exact is not None else False,
        }
        expected = {
            "exact": {"prefix": False, "suffix": False, "exact": True},
            "prefix": {"prefix": True, "suffix": False, "exact": False},
            "suffix": {"prefix": False, "suffix": True, "exact": False},
            "prefix_suffix": {"prefix": True, "suffix": True, "exact": False},
        }[self.kind]
        if populated != expected:
            raise ValueError(f"invalid fields for {self.kind} target constraint")

    def record(self) -> dict[str, str | None]:
        return {
            "kind": self.kind,
            "prefix": self.prefix,
            "suffix": self.suffix,
            "exact": self.exact,
        }


@dataclass(frozen=True)
class ConstraintCompilation:
    allowed: bool
    constraint: TargetConstraint | None
    reason: str


@dataclass(frozen=True)
class ConstraintCertificate:
    allowed: bool
    reason: str
    constraint: TargetConstraint | None
    observed_label: str
    supporting_value_bids: tuple[str, ...] = ()


def _quoted_after(pattern: str, goal: str) -> str | None:
    match = re.search(
        pattern + r'\s*["“]([^"”]+)["”]',
        goal,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else None


def _explicit_exact_target(goal: str) -> str | None:
    """Return only quoted text that grammar marks as an action target.

    Treating the final quoted phrase as a target is unsafe: in ``type "foo"
    into "Search"`` it is a field name, not a requested commit.  The accepted
    forms below contain either an explicit target descriptor (label/name) or a
    supported commit imperative whose direct object is quoted.
    """

    quote = r'["“]([^"”]+)["”]'
    patterns = (
        rf"\b(?:labeled|labelled|named|called)\s+{quote}",
        rf"\b(?:click|press|select|choose|pick|open|activate)\s+"
        rf"(?:(?:on|the)\s+)*"
        rf"(?:(?:menu\s+item|button|control|item|option|tab|link)\s+)?"
        rf"{quote}",
    )
    matches: list[tuple[int, str]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, goal, flags=re.IGNORECASE):
            target = re.sub(r"\s+", " ", match.group(1)).strip()
            if target:
                matches.append((match.start(), target))
    return max(matches, default=(-1, ""))[1] or None


def _explicit_submit_target(goal: str) -> bool:
    patterns = (
        r"\b(?:click|press)\s+(?:the\s+)?submit(?:\s+button)?\b",
        r"\b(?:and|then)\s+submit(?:\s+(?:it|the\s+form))?\b",
        r"^\s*(?:please\s+)?submit(?:\s+(?:it|the\s+form))?\b",
    )
    return any(re.search(pattern, goal, flags=re.IGNORECASE) for pattern in patterns)


def compile_target_constraint(goal: str) -> ConstraintCompilation:
    """Compile only target constraints explicitly verifiable from goal text."""

    goal = str(goal).strip()
    if not goal:
        return ConstraintCompilation(False, None, "instruction is empty")

    prefix = _quoted_after(r"\bstarts?\s+with\b", goal)
    suffix = _quoted_after(r"\bends?\s+with\b", goal)
    if prefix and suffix:
        return ConstraintCompilation(
            True,
            TargetConstraint("prefix_suffix", prefix=prefix, suffix=suffix),
            "instruction explicitly declares prefix and suffix constraints",
        )
    if prefix:
        return ConstraintCompilation(
            True,
            TargetConstraint("prefix", prefix=prefix),
            "instruction explicitly declares a prefix constraint",
        )
    if suffix:
        return ConstraintCompilation(
            True,
            TargetConstraint("suffix", suffix=suffix),
            "instruction explicitly declares a suffix constraint",
        )

    if ">" in goal and re.search(r"\b(?:select|choose|navigate|open)\b", goal, flags=re.IGNORECASE):
        tail = re.sub(r"\s+", " ", goal.rsplit(">", 1)[-1]).strip(" .")
        if tail:
            return ConstraintCompilation(
                True,
                TargetConstraint("exact", exact=tail),
                "instruction exposes an exact path-tail target",
            )

    exact = _explicit_exact_target(goal)
    if exact:
        return ConstraintCompilation(
            True,
            TargetConstraint("exact", exact=exact),
            "instruction exposes an explicitly marked exact target",
        )

    if _explicit_submit_target(goal):
        return ConstraintCompilation(
            True,
            TargetConstraint("exact", exact="Submit"),
            "instruction explicitly requests Submit",
        )

    return ConstraintCompilation(
        False,
        None,
        "instruction exposes no supported positive public target constraint",
    )


def satisfies_constraint(value: str, constraint: TargetConstraint) -> bool:
    observed = _normalize(value)
    if not observed:
        return False
    if constraint.kind == "exact":
        expected = _normalize(str(constraint.exact))
        return observed == expected or (expected, observed) in EXACT_ALIASES
    if constraint.kind == "prefix":
        return observed.startswith(_normalize(str(constraint.prefix)))
    if constraint.kind == "suffix":
        return observed.endswith(_normalize(str(constraint.suffix)))
    return observed.startswith(_normalize(str(constraint.prefix))) and observed.endswith(
        _normalize(str(constraint.suffix))
    )


def exploration_query(constraint: TargetConstraint) -> str | None:
    """Return a publicly grounded query when the constraint supplies one."""

    if constraint.kind == "exact":
        return constraint.exact
    if constraint.kind in {"prefix", "prefix_suffix"}:
        return constraint.prefix
    return None


def _public_value(snapshot: SemanticSnapshot, bid: str) -> str:
    element = snapshot.get(bid)
    if element is None:
        return ""
    value = element.ax_property("value")
    if value is None:
        value = element.dom_attribute("value", "")
    return "" if value is None else str(value)


def supporting_public_values(
    snapshot: SemanticSnapshot,
    constraint: TargetConstraint,
) -> tuple[str, ...]:
    matches = []
    for element in snapshot.elements:
        if not snapshot.is_effectively_visible(element.bid):
            continue
        if element.role.casefold() not in TEXT_VALUE_ROLES:
            continue
        if satisfies_constraint(_public_value(snapshot, element.bid), constraint):
            matches.append(element.bid)
    return tuple(sorted(matches))


def verify_commit_constraint(
    *,
    goal: str,
    candidate_label: str,
    candidate_role: str,
    current: SemanticSnapshot,
) -> ConstraintCertificate:
    """Require positive label or unique public-state support for a commit."""

    compilation = compile_target_constraint(goal)
    if not compilation.allowed or compilation.constraint is None:
        return ConstraintCertificate(
            False,
            compilation.reason,
            None,
            candidate_label,
        )
    constraint = compilation.constraint
    if satisfies_constraint(candidate_label, constraint):
        return ConstraintCertificate(
            True,
            "candidate label satisfies the compiled public target constraint",
            constraint,
            candidate_label,
        )

    normalized_label = _normalize(candidate_label)
    if candidate_role.casefold() == "button" and normalized_label in FORM_TERMINAL_LABELS:
        supporting = supporting_public_values(current, constraint)
        if len(supporting) == 1:
            return ConstraintCertificate(
                True,
                "terminal form control is supported by one matching public input value",
                constraint,
                candidate_label,
                supporting,
            )
        reason = (
            "terminal form control has no matching public input value"
            if not supporting
            else "terminal form control has ambiguous matching public input values"
        )
        return ConstraintCertificate(
            False,
            reason,
            constraint,
            candidate_label,
            supporting,
        )

    return ConstraintCertificate(
        False,
        "candidate label does not satisfy the compiled public target constraint",
        constraint,
        candidate_label,
    )
