"""Frozen transaction utilities for equal-budget external GUI evaluation."""

from __future__ import annotations

import hashlib
import io
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

from inversereserve.observations.click_preview import WordBox

METHOD_ORDER = (
    "passive",
    "risk_only",
    "click_restore",
    "rps_no_provenance",
    "rps_no_binding",
    "full_rps",
)


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    permits_preview: bool
    uses_semantic_risk: bool
    restores_after_preview: bool
    blocks_novel_click_preview: bool
    requires_evidence_binding: bool
    permits_recursive_click_preview: bool


METHOD_SPECS = {
    "passive": MethodSpec(
        method_id="passive",
        permits_preview=False,
        uses_semantic_risk=False,
        restores_after_preview=False,
        blocks_novel_click_preview=False,
        requires_evidence_binding=True,
        permits_recursive_click_preview=False,
    ),
    "risk_only": MethodSpec(
        method_id="risk_only",
        permits_preview=True,
        uses_semantic_risk=True,
        restores_after_preview=False,
        blocks_novel_click_preview=False,
        requires_evidence_binding=True,
        permits_recursive_click_preview=True,
    ),
    "click_restore": MethodSpec(
        method_id="click_restore",
        permits_preview=True,
        uses_semantic_risk=False,
        restores_after_preview=True,
        blocks_novel_click_preview=False,
        requires_evidence_binding=True,
        permits_recursive_click_preview=True,
    ),
    "rps_no_provenance": MethodSpec(
        method_id="rps_no_provenance",
        permits_preview=True,
        uses_semantic_risk=True,
        restores_after_preview=True,
        blocks_novel_click_preview=False,
        requires_evidence_binding=True,
        permits_recursive_click_preview=True,
    ),
    "rps_no_binding": MethodSpec(
        method_id="rps_no_binding",
        permits_preview=True,
        uses_semantic_risk=True,
        restores_after_preview=True,
        blocks_novel_click_preview=True,
        requires_evidence_binding=False,
        permits_recursive_click_preview=False,
    ),
    "full_rps": MethodSpec(
        method_id="full_rps",
        permits_preview=True,
        uses_semantic_risk=True,
        restores_after_preview=True,
        blocks_novel_click_preview=True,
        requires_evidence_binding=True,
        permits_recursive_click_preview=False,
    ),
}


@dataclass(frozen=True)
class FrozenPlattGate:
    """C418 all-synthetic calibrated click-preview gate."""

    coefficient: float = 3.92044377708801
    intercept: float = -0.9233542612810259
    threshold: float = 0.3437227851574854
    clip: float = 1e-7

    def __post_init__(self) -> None:
        if self.coefficient <= 0.0:
            raise ValueError("calibration coefficient must be positive")
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        if not 0.0 < self.clip < 0.5:
            raise ValueError("clip must be in (0, 0.5)")

    def calibrate(self, raw_risk: float) -> float:
        if not math.isfinite(raw_risk) or not 0.0 <= raw_risk <= 1.0:
            return 1.0
        clipped = min(max(float(raw_risk), self.clip), 1.0 - self.clip)
        logit = math.log(clipped / (1.0 - clipped))
        value = self.coefficient * logit + self.intercept
        if value >= 0.0:
            return 1.0 / (1.0 + math.exp(-value))
        exponential = math.exp(value)
        return exponential / (1.0 + exponential)

    def allows(self, raw_risk: float) -> bool:
        return self.calibrate(raw_risk) <= self.threshold + 1e-12


@dataclass(frozen=True)
class ExternalBudgetConfig:
    maximum_gui_actions: int = 20
    maximum_scroll_actions: int = 6
    maximum_preview_transactions: int = 6
    maximum_hover_probes_per_preview: int = 2
    maximum_candidate_proposals_per_state: int = 128
    maximum_risk_candidates_per_state: int = 16
    maximum_risk_forwards: int = 192
    maximum_binder_forwards: int = 96
    maximum_fullscreen_ocr_calls: int = 24
    maximum_crop_ocr_calls: int = 512
    maximum_wall_seconds: float = 300.0

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if float(value) <= 0.0:
                raise ValueError(f"{name} must be positive")


class BudgetExhausted(RuntimeError):
    pass


@dataclass
class BudgetLedger:
    config: ExternalBudgetConfig
    started: float = 0.0
    gui_actions: int = 0
    scroll_actions: int = 0
    restoration_cleanup_actions: int = 0
    preview_transactions: int = 0
    hover_probes: int = 0
    candidate_proposals: int = 0
    risk_forwards: int = 0
    binder_forwards: int = 0
    fullscreen_ocr_calls: int = 0
    crop_ocr_calls: int = 0

    def __post_init__(self) -> None:
        if self.started <= 0.0:
            self.started = time.monotonic()

    def _consume(self, field: str, amount: int, maximum: int) -> None:
        if amount < 0:
            raise ValueError("budget consumption must be nonnegative")
        self.require_time()
        updated = int(getattr(self, field)) + int(amount)
        if updated > int(maximum):
            raise BudgetExhausted(f"{field}: {updated} > {maximum}")
        setattr(self, field, updated)

    def require_time(self) -> None:
        elapsed = time.monotonic() - self.started
        if elapsed > self.config.maximum_wall_seconds:
            raise BudgetExhausted(f"wall_seconds: {elapsed:.3f} > {self.config.maximum_wall_seconds}")

    def consume_gui_action(self, amount: int = 1) -> None:
        self._consume("gui_actions", amount, self.config.maximum_gui_actions)

    def remaining_gui_actions(self) -> int:
        return self.config.maximum_gui_actions - self.gui_actions

    def require_gui_capacity(self, amount: int) -> None:
        self.require_time()
        if amount < 0:
            raise ValueError("required GUI capacity must be nonnegative")
        if self.remaining_gui_actions() < amount:
            raise BudgetExhausted(f"gui_action_reserve: need {amount}, have {self.remaining_gui_actions()}")

    def consume_scroll(self, amount: int = 1) -> None:
        self._consume("scroll_actions", amount, self.config.maximum_scroll_actions)

    def consume_scroll_gui_action(self) -> None:
        """Atomically charge one scroll and one GUI action."""

        self.require_time()
        if self.scroll_actions + 1 > self.config.maximum_scroll_actions:
            raise BudgetExhausted(
                f"scroll_actions: {self.scroll_actions + 1} > {self.config.maximum_scroll_actions}"
            )
        if self.gui_actions + 1 > self.config.maximum_gui_actions:
            raise BudgetExhausted(f"gui_actions: {self.gui_actions + 1} > {self.config.maximum_gui_actions}")
        self.scroll_actions += 1
        self.gui_actions += 1

    def consume_restoration_gui_action(self) -> None:
        """Charge mandatory rollback even when inference crossed the wall cap."""

        if self.gui_actions + 1 > self.config.maximum_gui_actions:
            raise BudgetExhausted(f"gui_actions: {self.gui_actions + 1} > {self.config.maximum_gui_actions}")
        self.gui_actions += 1
        self.restoration_cleanup_actions += 1

    def consume_preview(self, amount: int = 1) -> None:
        self._consume(
            "preview_transactions",
            amount,
            self.config.maximum_preview_transactions,
        )

    def consume_hover(self, amount: int = 1) -> None:
        maximum = self.config.maximum_preview_transactions * self.config.maximum_hover_probes_per_preview
        self._consume("hover_probes", amount, maximum)

    def consume_candidates(self, amount: int) -> None:
        self._consume(
            "candidate_proposals",
            amount,
            self.config.maximum_candidate_proposals_per_state * (self.config.maximum_gui_actions + 1),
        )

    def consume_risk_forwards(self, amount: int = 1) -> None:
        self._consume("risk_forwards", amount, self.config.maximum_risk_forwards)

    def consume_binder_forwards(self, amount: int = 1) -> None:
        self._consume("binder_forwards", amount, self.config.maximum_binder_forwards)

    def consume_fullscreen_ocr(self, amount: int = 1) -> None:
        self._consume(
            "fullscreen_ocr_calls",
            amount,
            self.config.maximum_fullscreen_ocr_calls,
        )

    def consume_crop_ocr(self, amount: int = 1) -> None:
        self._consume("crop_ocr_calls", amount, self.config.maximum_crop_ocr_calls)

    def snapshot(self) -> dict[str, Any]:
        return {
            "gui_actions": self.gui_actions,
            "scroll_actions": self.scroll_actions,
            "restoration_cleanup_actions": self.restoration_cleanup_actions,
            "preview_transactions": self.preview_transactions,
            "hover_probes": self.hover_probes,
            "candidate_proposals": self.candidate_proposals,
            "risk_forwards": self.risk_forwards,
            "binder_forwards": self.binder_forwards,
            "fullscreen_ocr_calls": self.fullscreen_ocr_calls,
            "crop_ocr_calls": self.crop_ocr_calls,
            "wall_seconds": time.monotonic() - self.started,
        }


@dataclass(frozen=True)
class RestorationConfig:
    pixel_threshold: int = 12
    maximum_changed_pixels: int = 512
    maximum_changed_fraction: float = 0.002

    def __post_init__(self) -> None:
        if self.pixel_threshold < 0:
            raise ValueError("pixel_threshold must be nonnegative")
        if self.maximum_changed_pixels < 0:
            raise ValueError("maximum_changed_pixels must be nonnegative")
        if not 0.0 <= self.maximum_changed_fraction <= 1.0:
            raise ValueError("maximum_changed_fraction must be in [0, 1]")


@dataclass(frozen=True)
class RestorationCertificate:
    changed_pixels: int
    total_pixels: int
    changed_fraction: float
    passed: bool


def restoration_certificate(
    reference: Any,
    restored: Any,
    config: RestorationConfig | None = None,
) -> RestorationCertificate:
    """Certify pixel restoration under the frozen dual threshold."""

    import numpy as np

    cfg = config or RestorationConfig()
    left = np.asarray(reference.convert("RGB"), dtype=np.int16)
    right = np.asarray(restored.convert("RGB"), dtype=np.int16)
    if left.shape != right.shape:
        raise ValueError(f"restoration image shape mismatch: {left.shape} != {right.shape}")
    difference = np.max(np.abs(left - right), axis=2)
    changed = int((difference >= cfg.pixel_threshold).sum())
    total = int(difference.size)
    fraction = changed / total if total else 0.0
    passed = changed <= cfg.maximum_changed_pixels and fraction <= cfg.maximum_changed_fraction + 1e-12
    return RestorationCertificate(
        changed_pixels=changed,
        total_pixels=total,
        changed_fraction=fraction,
        passed=passed,
    )


TARGET_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "button",
        "click",
        "control",
        "file",
        "find",
        "folder",
        "for",
        "icon",
        "in",
        "item",
        "label",
        "labeled",
        "menu",
        "named",
        "navigate",
        "on",
        "option",
        "please",
        "post",
        "select",
        "target",
        "the",
        "then",
        "through",
        "to",
        "ui",
        "with",
    }
)


def normalized_tokens(value: str) -> tuple[str, ...]:
    expanded = re.sub(r"[_/]+", "-", str(value).lower())
    pieces = re.findall(r"[a-z0-9]+", expanded)
    output = []
    for token in pieces:
        if token in TARGET_STOPWORDS:
            continue
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        if token and token not in output:
            output.append(token)
    return tuple(output)


def instruction_target_tokens(instruction: str) -> tuple[str, ...]:
    """Extract the terminal click object without mistaking an earlier disclosure.

    A frequent GUI construction is ``click \"Menu\", then ... click the item
    with the icon``.  In that case the only quoted text names the preview
    control, not the final target.  The parser prefers a quoted phrase that
    occurs after the final click imperative and otherwise parse only that
    imperative's suffix.  The full-instruction fallback is retained for goals
    without a click imperative.
    """

    value = str(instruction)
    if ">" in value:
        path_tail = value.rsplit(">", 1)[-1]
        path_tokens = normalized_tokens(path_tail)
        if path_tokens:
            return path_tokens
    click_matches = list(re.finditer(r"\bclick\b", value, flags=re.IGNORECASE))
    quoted_matches = list(re.finditer(r"[\"']([^\"']+)[\"']", value))
    final_click_end = click_matches[-1].end() if click_matches else -1
    eligible_quotes = [match for match in quoted_matches if match.start() >= final_click_end]
    if eligible_quotes:
        tokens = normalized_tokens(eligible_quotes[-1].group(1))
        if tokens:
            return tokens
    if click_matches:
        suffix = value[final_click_end:]
        tokens = normalized_tokens(suffix)
        if tokens:
            return tokens
        return ()
    if quoted_matches:
        tokens = normalized_tokens(quoted_matches[-1].group(1))
        if tokens:
            return tokens
    return normalized_tokens(value)


def token_match_score(
    target_tokens: Iterable[str],
    observed_text: str,
) -> tuple[int, int, int, int]:
    """Return exact, prefix, covered-target, and surplus-token counts."""

    target = tuple(dict.fromkeys(str(token) for token in target_tokens if token))
    observed = normalized_tokens(observed_text)
    exact = sum(token in observed for token in target)
    prefix = sum(
        any(
            min(len(token), len(candidate)) >= 4
            and (candidate.startswith(token) or token.startswith(candidate))
            for candidate in observed
        )
        for token in target
        if token not in observed
    )
    covered = exact + prefix
    surplus = sum(token not in target for token in observed)
    return exact, prefix, covered, surplus


@dataclass(frozen=True)
class TextCommitBinding:
    point: tuple[float, float]
    bbox_xyxy: tuple[int, int, int, int]
    text: str
    target_tokens: tuple[str, ...]
    observed_tokens: tuple[str, ...]
    exact_matches: int
    prefix_matches: int
    confidence: float


def _line_spans(
    boxes: Iterable[WordBox],
    maximum_words: int,
) -> list[WordBox]:
    groups: dict[tuple[int, int, int], list[WordBox]] = {}
    for box in boxes:
        groups.setdefault((box.block, box.paragraph, box.line), []).append(box)
    spans = []
    for group in groups.values():
        ordered = sorted(group, key=lambda row: (row.bbox_xyxy[0], row.bbox_xyxy[1]))
        for start in range(len(ordered)):
            for length in range(1, min(maximum_words, len(ordered) - start) + 1):
                window = ordered[start : start + length]
                spans.append(
                    WordBox(
                        text=" ".join(row.text for row in window),
                        bbox_xyxy=(
                            min(row.bbox_xyxy[0] for row in window),
                            min(row.bbox_xyxy[1] for row in window),
                            max(row.bbox_xyxy[2] for row in window),
                            max(row.bbox_xyxy[3] for row in window),
                        ),
                        confidence=sum(row.confidence for row in window) / len(window),
                        block=window[0].block,
                        paragraph=window[0].paragraph,
                        line=window[0].line,
                    )
                )
    return spans


def _bbox_iou(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    intersection = max(0, x1 - x0) * max(0, y1 - y0)
    left_area = max(0, left[2] - left[0]) * max(0, left[3] - left[1])
    right_area = max(0, right[2] - right[0]) * max(0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def bind_unique_visible_text(
    *,
    instruction: str,
    word_boxes: Iterable[WordBox],
    maximum_words_per_span: int = 4,
) -> TextCommitBinding | None:
    """Bind the requested final quoted target to one visible OCR span."""

    if maximum_words_per_span <= 0:
        raise ValueError("maximum_words_per_span must be positive")
    target = instruction_target_tokens(instruction)
    if not target:
        return None
    candidates = []
    for span in _line_spans(word_boxes, maximum_words_per_span):
        exact, prefix, _covered, surplus = token_match_score(target, span.text)
        if exact < len(target):
            continue
        observed = normalized_tokens(span.text)
        area = max(1, span.bbox_xyxy[2] - span.bbox_xyxy[0]) * max(
            1,
            span.bbox_xyxy[3] - span.bbox_xyxy[1],
        )
        semantic_key = (-exact, -prefix, surplus, len(observed))
        total_key = semantic_key + (
            area,
            -float(span.confidence),
            span.bbox_xyxy[1],
            span.bbox_xyxy[0],
            span.text.lower(),
        )
        candidates.append((total_key, semantic_key, span, observed, exact, prefix))
    if not candidates:
        return None
    selected = min(candidates, key=lambda row: row[0])
    _, selected_semantics, span, observed, exact, prefix = selected
    if any(
        semantics == selected_semantics and _bbox_iou(other.bbox_xyxy, span.bbox_xyxy) < 0.5
        for _, semantics, other, _, _, _ in candidates
        if other is not span
    ):
        return None
    left, top, right, bottom = span.bbox_xyxy
    return TextCommitBinding(
        point=((left + right) / 2.0, (top + bottom) / 2.0),
        bbox_xyxy=span.bbox_xyxy,
        text=span.text,
        target_tokens=target,
        observed_tokens=observed,
        exact_matches=exact,
        prefix_matches=prefix,
        confidence=float(span.confidence),
    )


def hover_relevance(instruction: str, candidate_text: str) -> tuple[int, int, int]:
    """Rank non-click hover probes without using task state or reward."""

    target = instruction_target_tokens(instruction)
    exact, prefix, covered, surplus = token_match_score(target, candidate_text)
    if covered <= 0:
        exact, prefix, covered, surplus = token_match_score(
            normalized_tokens(instruction),
            candidate_text,
        )
    return (covered, exact + prefix, -surplus)


def image_png_sha256(image: Any) -> str:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return hashlib.sha256(buffer.getvalue()).hexdigest()
