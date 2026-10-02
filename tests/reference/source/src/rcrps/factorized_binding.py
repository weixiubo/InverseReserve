"""Screenshot-only entity scoping followed by physical-action verification."""

from __future__ import annotations

import dataclasses
import math
import re
from typing import Any, Iterable

from .click_preview import WordBox
from .preview_transaction import normalized_tokens, token_match_score


ENTITY_HANDLE_PATTERN = re.compile(r"@[A-Za-z0-9_-]+")
ENTITY_NAMED_PATTERN = re.compile(
    r"\b(?:named|called|label(?:l)?ed)\s+[\"']([^\"']+)[\"']",
    flags=re.IGNORECASE,
)

ACTION_BINDER_COMMON = (
    "You are a conservative GUI physical-action verifier. A separate "
    "screenshot-OCR and geometry stage has already scoped the candidates to "
    "the entity requested by the instruction. Image 1 is the full current "
    "screen. Image 2 preserves the scoped candidate's local context and marks "
    "the exact proposed click support with red corner brackets. Decide only "
    "whether the BRACKETED PHYSICAL CONTROL visibly realizes the requested "
    "action for that entity. Use the control's icon, text, and immediate "
    "rendered context. Candidate OCR may be empty for an icon. A nearby entity "
    "label, row, card, parent container, or disclosure control is not itself a "
    "YES unless the brackets enclose the requested click-ready action. Reply, "
    "retweet/repost, like/favorite, edit/rename, menu, and similar controls must "
    "match the requested action. Use only the instruction and rendered pixels."
)
ACTION_BINDER_SUFFIX = (
    "Instruction: {instruction}\n"
    "Entity tokens already scoped: {entity_tokens}\n"
    "Candidate OCR: {candidate_ocr}"
)
ACTION_BINDER_NO_A_YES_B = (
    "Answer one letter only. A = NO requested physical action. "
    "B = YES requested physical action."
)
ACTION_BINDER_YES_A_NO_B = (
    "Answer one letter only. A = YES requested physical action. "
    "B = NO requested physical action."
)
ACTION_BINDER_MAXIMUM_CANDIDATES = 8


@dataclasses.dataclass(frozen=True)
class EntityScopeConfig:
    """Scale-normalized constraints for assigning controls to a text entity."""

    maximum_normalized_row_slack: float = 0.75
    parent_area_ratio: float = 4.0
    minimum_scale_pixels: float = 8.0

    def __post_init__(self) -> None:
        if self.maximum_normalized_row_slack < 0.0:
            raise ValueError("maximum_normalized_row_slack must be nonnegative")
        if self.parent_area_ratio <= 1.0:
            raise ValueError("parent_area_ratio must be greater than one")
        if self.minimum_scale_pixels <= 0.0:
            raise ValueError("minimum_scale_pixels must be positive")


@dataclasses.dataclass(frozen=True)
class EntityAnchor:
    text: str
    tokens: tuple[str, ...]
    bbox_xyxy: tuple[int, int, int, int]
    confidence: float
    exact_matches: int
    prefix_matches: int


@dataclasses.dataclass(frozen=True)
class ScopedCandidate:
    candidate_id: str
    normalized_row_distance: float
    euclidean_distance: float


@dataclasses.dataclass(frozen=True)
class EntityScopeDecision:
    applied: bool
    entity_tokens: tuple[str, ...]
    anchors: tuple[EntityAnchor, ...]
    retained: tuple[ScopedCandidate, ...]
    rejected_entity_labels: tuple[str, ...]
    rejected_parent_containers: tuple[str, ...]
    reason: str


def instruction_entity_tokens(instruction: str) -> tuple[str, ...]:
    """Extract an explicit entity anchor without confusing it with the action."""

    handles = ENTITY_HANDLE_PATTERN.findall(str(instruction))
    if handles:
        return normalized_tokens(handles[0])
    named = ENTITY_NAMED_PATTERN.search(str(instruction))
    if named is not None:
        return normalized_tokens(named.group(1))
    return ()


def _word_lines(words: Iterable[WordBox]) -> list[list[WordBox]]:
    # Tesseract can assign two visibly aligned words to adjacent line IDs when
    # their glyph baselines differ by only a few pixels (for example
    # ``Roadmap sync``).  Geometry is the method input, so build rendered rows
    # from vertical overlap rather than trusting OCR's semantic line IDs.
    lines: list[list[WordBox]] = []
    for word in sorted(
        words,
        key=lambda row: (
            (row.bbox_xyxy[1] + row.bbox_xyxy[3]) / 2.0,
            row.bbox_xyxy[0],
        ),
    ):
        center = (word.bbox_xyxy[1] + word.bbox_xyxy[3]) / 2.0
        destination = None
        for line in lines:
            top = min(row.bbox_xyxy[1] for row in line)
            bottom = max(row.bbox_xyxy[3] for row in line)
            height = max(1.0, float(bottom - top))
            if top - 0.5 * height <= center <= bottom + 0.5 * height:
                destination = line
                break
        if destination is None:
            lines.append([word])
        else:
            destination.append(word)
            destination.sort(key=lambda row: (row.bbox_xyxy[0], row.bbox_xyxy[1]))
    return lines


def _matches_token(target: str, observed: str) -> bool:
    return target == observed or (
        min(len(target), len(observed)) >= 4
        and (target.startswith(observed) or observed.startswith(target))
    )


def entity_anchors(
    instruction: str,
    words: Iterable[WordBox],
) -> tuple[EntityAnchor, ...]:
    """Localize every rendered OCR line that covers the explicit entity."""

    target = instruction_entity_tokens(instruction)
    if not target:
        return ()
    candidates: list[EntityAnchor] = []
    minimum_coverage = max(1, int(math.ceil(0.5 * len(target))))
    for line in _word_lines(words):
        observed = normalized_tokens(" ".join(word.text for word in line))
        exact, prefix, covered, _surplus = token_match_score(target, observed)
        if covered < minimum_coverage:
            continue
        matched = [
            word
            for word in line
            if any(
                _matches_token(wanted, token)
                for wanted in target
                for token in normalized_tokens(word.text)
            )
        ]
        if not matched:
            continue
        bbox = (
            min(word.bbox_xyxy[0] for word in matched),
            min(word.bbox_xyxy[1] for word in matched),
            max(word.bbox_xyxy[2] for word in matched),
            max(word.bbox_xyxy[3] for word in matched),
        )
        candidates.append(
            EntityAnchor(
                text=" ".join(word.text for word in matched),
                tokens=observed,
                bbox_xyxy=bbox,
                confidence=sum(float(word.confidence) for word in matched)
                / len(matched),
                exact_matches=exact,
                prefix_matches=prefix,
            )
        )
    if not candidates:
        return ()
    best = max(
        (anchor.exact_matches, anchor.prefix_matches)
        for anchor in candidates
    )
    retained = [
        anchor
        for anchor in candidates
        if (anchor.exact_matches, anchor.prefix_matches) == best
    ]
    return tuple(
        sorted(
            retained,
            key=lambda anchor: (
                anchor.bbox_xyxy[1],
                anchor.bbox_xyxy[0],
                -anchor.confidence,
                anchor.text,
            ),
        )
    )


def _candidate_id(candidate: Any) -> str:
    return str(getattr(candidate, "proposal_id", getattr(candidate, "candidate_id", "")))


def _candidate_bbox(candidate: Any) -> tuple[float, float, float, float]:
    value = getattr(candidate, "bbox_xyxy")
    if len(value) != 4:
        raise ValueError("candidate bbox must contain four coordinates")
    return tuple(float(item) for item in value)  # type: ignore[return-value]


def _candidate_text(candidate: Any) -> str:
    return str(getattr(candidate, "text", getattr(candidate, "candidate_ocr", "")) or "")


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0


def _area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _is_entity_label(candidate: Any, entity_tokens: tuple[str, ...]) -> bool:
    observed = normalized_tokens(_candidate_text(candidate))
    if not observed:
        return False
    _exact, _prefix, covered, _surplus = token_match_score(entity_tokens, observed)
    return covered >= len(entity_tokens)


def _is_parent_container(
    candidate: Any,
    anchors: tuple[EntityAnchor, ...],
    config: EntityScopeConfig,
) -> bool:
    box = _candidate_bbox(candidate)
    candidate_area = _area(box)
    for anchor in anchors:
        anchor_box = tuple(float(value) for value in anchor.bbox_xyxy)
        anchor_center = _center(anchor_box)
        contains = (
            box[0] <= anchor_center[0] <= box[2]
            and box[1] <= anchor_center[1] <= box[3]
        )
        if contains and candidate_area > config.parent_area_ratio * max(
            1.0, _area(anchor_box)
        ):
            return True
    return False


def _spatial_distance(
    candidate: Any,
    anchors: tuple[EntityAnchor, ...],
    config: EntityScopeConfig,
) -> tuple[float, float]:
    box = _candidate_bbox(candidate)
    center_x, center_y = _center(box)
    candidate_height = max(1.0, box[3] - box[1])
    rows = []
    for anchor in anchors:
        anchor_box = tuple(float(value) for value in anchor.bbox_xyxy)
        anchor_x, anchor_y = _center(anchor_box)
        anchor_height = max(1.0, anchor_box[3] - anchor_box[1])
        scale = max(config.minimum_scale_pixels, candidate_height, anchor_height)
        rows.append(
            (
                abs(center_y - anchor_y) / scale,
                math.hypot(center_x - anchor_x, center_y - anchor_y) / scale,
            )
        )
    return min(rows)


def scope_candidates_to_entity(
    *,
    instruction: str,
    words: Iterable[WordBox],
    candidates: Iterable[Any],
    config: EntityScopeConfig | None = None,
) -> tuple[list[Any], EntityScopeDecision]:
    """Scope physical candidates to explicit screenshot-localized entities."""

    cfg = config or EntityScopeConfig()
    rows = list(candidates)
    tokens = instruction_entity_tokens(instruction)
    if not tokens:
        return rows, EntityScopeDecision(
            applied=False,
            entity_tokens=(),
            anchors=(),
            retained=(),
            rejected_entity_labels=(),
            rejected_parent_containers=(),
            reason="no_explicit_entity",
        )
    anchors = entity_anchors(instruction, words)
    if not anchors:
        return [], EntityScopeDecision(
            applied=True,
            entity_tokens=tokens,
            anchors=(),
            retained=(),
            rejected_entity_labels=(),
            rejected_parent_containers=(),
            reason="entity_not_localized",
        )
    labels = tuple(
        sorted(_candidate_id(candidate) for candidate in rows if _is_entity_label(candidate, tokens))
    )
    nonlabels = [candidate for candidate in rows if not _is_entity_label(candidate, tokens)]
    parents = tuple(
        sorted(
            _candidate_id(candidate)
            for candidate in nonlabels
            if _is_parent_container(candidate, anchors, cfg)
        )
    )
    physical = [
        candidate
        for candidate in nonlabels
        if not _is_parent_container(candidate, anchors, cfg)
    ]
    if not physical:
        return [], EntityScopeDecision(
            applied=True,
            entity_tokens=tokens,
            anchors=anchors,
            retained=(),
            rejected_entity_labels=labels,
            rejected_parent_containers=parents,
            reason="no_physical_candidate_after_filtering",
        )
    distances = {
        _candidate_id(candidate): _spatial_distance(candidate, anchors, cfg)
        for candidate in physical
    }
    nearest = min(value[0] for value in distances.values())
    retained_rows = [
        candidate
        for candidate in physical
        if distances[_candidate_id(candidate)][0]
        <= nearest + cfg.maximum_normalized_row_slack + 1e-12
    ]
    retained_rows.sort(
        key=lambda candidate: (
            distances[_candidate_id(candidate)][0],
            distances[_candidate_id(candidate)][1],
            _candidate_id(candidate),
        )
    )
    retained = tuple(
        ScopedCandidate(
            candidate_id=_candidate_id(candidate),
            normalized_row_distance=distances[_candidate_id(candidate)][0],
            euclidean_distance=distances[_candidate_id(candidate)][1],
        )
        for candidate in retained_rows
    )
    return retained_rows, EntityScopeDecision(
        applied=True,
        entity_tokens=tokens,
        anchors=anchors,
        retained=retained,
        rejected_entity_labels=labels,
        rejected_parent_containers=parents,
        reason="scoped",
    )


def action_binder_prompts(
    *,
    instruction: str,
    entity_tokens: Iterable[str],
    candidate_ocr: str,
) -> tuple[str, str]:
    tokens = " ".join(str(token) for token in entity_tokens).strip() or "<none>"
    suffix = ACTION_BINDER_SUFFIX.format(
        instruction=instruction,
        entity_tokens=tokens,
        candidate_ocr=candidate_ocr.strip() or "<empty>",
    )
    return (
        "\n".join((ACTION_BINDER_COMMON, suffix, ACTION_BINDER_NO_A_YES_B)),
        "\n".join((ACTION_BINDER_COMMON, suffix, ACTION_BINDER_YES_A_NO_B)),
    )
