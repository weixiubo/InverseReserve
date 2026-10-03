"""Public viewport geometry and Save/neutral witness evidence, independent of mutation certification."""

from __future__ import annotations

import math
from dataclasses import dataclass

from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import _tokens
from inversereserve.adapters.webarena.webarena_exact_mutation_v2 import _surface_descendant_bids
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import _public_boolean
from inversereserve.observations.typed_observation import SemanticElement, SemanticSnapshot

MAXIMUM_VIEWPORT_SURFACE_DESCENDANTS_V5 = 1024
MAXIMUM_VIEWPORT_SURFACE_AREA_RATIO_V5 = 2.0
NEUTRAL_LABEL_TOKENS_V5 = frozenset({("back",), ("go", "back"), ("cancel",), ("close",), ("discard",)})


def _button_like_v5(element: SemanticElement) -> bool:
    return bool(
        (element.role.casefold() == "button" or element.dom_tag.casefold() == "button")
        and element.clickable
        and (not _public_boolean(element, "disabled"))
    )


def _label_tokens_v5(element: SemanticElement) -> tuple[str, ...]:
    return _tokens(element.name or element.subtree_text)


def _is_exact_save_leaf_v5(element: SemanticElement) -> bool:
    return _button_like_v5(element) and _label_tokens_v5(element) == ("save",)


def _is_neutral_leaf_v5(element: SemanticElement) -> bool:
    return bool(_button_like_v5(element) and _label_tokens_v5(element) in NEUTRAL_LABEL_TOKENS_V5)


def _valid_bbox_v5(bbox: tuple[float, float, float, float] | None) -> bool:
    return bool(
        bbox is not None and all((math.isfinite(value) for value in bbox)) and (bbox[2] > 0) and (bbox[3] > 0)
    )


def _bbox_center_in_viewport_v5(
    element: SemanticElement, *, viewport_width: int, viewport_height: int
) -> bool:
    if not _valid_bbox_v5(element.bbox):
        return False
    assert element.bbox is not None
    x, y, width, height = element.bbox
    return bool(0 <= x + width / 2 <= viewport_width and 0 <= y + height / 2 <= viewport_height)


@dataclass(frozen=True)
class PublicViewportEditorSurfaceEvidenceV5:
    kind: str
    surface_bid: str
    submit_bid: str
    neutral_bids: tuple[str, ...]
    commit_representation_bids: tuple[str, ...]
    canonical_chain_bids: tuple[str, ...]
    ignored_save_option_bids: tuple[str, ...]
    target_depth: int
    submit_depth: int
    descendant_count: int
    viewport_width: int
    viewport_height: int
    surface_bbox: tuple[float, float, float, float]
    target_bbox: tuple[float, float, float, float]
    submit_bbox: tuple[float, float, float, float]
    surface_area_ratio: float

    def record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "surface_bid": self.surface_bid,
            "submit_bid": self.submit_bid,
            "neutral_bids": list(self.neutral_bids),
            "commit_representation_bids": list(self.commit_representation_bids),
            "canonical_chain_bids": list(self.canonical_chain_bids),
            "ignored_save_option_bids": list(self.ignored_save_option_bids),
            "target_depth": self.target_depth,
            "submit_depth": self.submit_depth,
            "descendant_count": self.descendant_count,
            "maximum_descendants": MAXIMUM_VIEWPORT_SURFACE_DESCENDANTS_V5,
            "viewport_width": self.viewport_width,
            "viewport_height": self.viewport_height,
            "surface_bbox": list(self.surface_bbox),
            "target_bbox": list(self.target_bbox),
            "submit_bbox": list(self.submit_bbox),
            "surface_area_ratio": self.surface_area_ratio,
            "maximum_surface_area_ratio": MAXIMUM_VIEWPORT_SURFACE_AREA_RATIO_V5,
            "uses_public_bbox": True,
            "uses_public_dom_ancestry": True,
            "uses_exact_public_action_label": True,
            "uses_public_neutral_witness": True,
            "uses_site_identity": False,
            "uses_site_specific_selector": False,
            "uses_site_specific_route": False,
            "uses_task_id": False,
            "uses_evaluator": False,
            "uses_reward": False,
            "uses_network_log": False,
            "uses_hidden_state": False,
        }


def _viewport_action_sets_v5(
    snapshot: SemanticSnapshot, surface_bid: str, *, viewport_width: int, viewport_height: int
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    surface_bids = _surface_descendant_bids(snapshot, surface_bid)
    exact_leaves = []
    neutral = []
    representations = []
    save_options = []
    for bid in surface_bids:
        element = snapshot.get(bid)
        if (
            element is None
            or not snapshot.is_effectively_visible(bid)
            or (
                not _bbox_center_in_viewport_v5(
                    element, viewport_width=viewport_width, viewport_height=viewport_height
                )
            )
        ):
            continue
        tokens = _label_tokens_v5(element)
        if _is_exact_save_leaf_v5(element):
            exact_leaves.append(bid)
        if _is_neutral_leaf_v5(element):
            neutral.append(bid)
        if element.clickable and tokens == ("save",):
            representations.append(bid)
        if _button_like_v5(element) and tokens == ("save", "options"):
            save_options.append(bid)
    return (
        tuple(sorted(set(exact_leaves))),
        tuple(sorted(set(neutral))),
        tuple(sorted(set(representations))),
        tuple(sorted(set(save_options))),
    )
