"""Quotient-space reversible preview search (Q-RPS).

The controller groups restoration-certified preview actions by normalized OCR
evidence and adapts its traversal to an observed zero-, one-, or two-dimensional
response topology. This module imports no evaluator world or task type.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from statistics import median

WHITESPACE = re.compile("\\s+")


def normalize_evidence(evidence: str) -> str:
    return WHITESPACE.sub(" ", evidence.lower()).strip()


def evidence_signature(evidence: str) -> str | None:
    normalized = normalize_evidence(evidence)
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def axis_point(anchor: tuple[float, float], axis: str, signed_distance: float) -> tuple[float, float]:
    if axis == "horizontal":
        return (anchor[0] + signed_distance, anchor[1])
    return (anchor[0], anchor[1] + signed_distance)


def axis_coordinate(point: tuple[float, float], axis: str) -> float:
    return point[0] if axis == "horizontal" else point[1]


def noncontiguous_signature_repeat(observations: list[tuple[float, str | None]]) -> bool:
    ordered = [signature for _, signature in sorted(observations) if signature is not None]
    compressed = []
    for signature in ordered:
        if not compressed or compressed[-1] != signature:
            compressed.append(signature)
    return len(compressed) != len(set(compressed))


def signature_representatives(observations: list[tuple[float, str | None]]) -> list[tuple[float, str]]:
    coordinates: dict[str, list[float]] = defaultdict(list)
    for coordinate, signature in observations:
        if signature is not None:
            coordinates[signature].append(coordinate)
    return sorted(((float(median(values)), signature) for signature, values in coordinates.items()))


def farthest_cartesian_frontier(
    horizontal: list[tuple[float, str]], vertical: list[tuple[float, str]], anchor: tuple[float, float]
) -> list[tuple[float, float]]:
    """Order off-axis Cartesian representatives by normalized farthest distance."""
    return [
        point
        for _, point in farthest_cartesian_frontier_entries(horizontal, vertical, anchor, covered_pairs=set())
    ]


def farthest_cartesian_frontier_entries(
    horizontal: list[tuple[float, str]],
    vertical: list[tuple[float, str]],
    anchor: tuple[float, float],
    *,
    covered_pairs: set[tuple[str, str]],
) -> list[tuple[tuple[str, str], tuple[float, float]]]:
    """Return pair-keyed farthest entries for a current Cartesian frontier."""
    nx = len(horizontal)
    ny = len(vertical)
    selected, remaining = _partition_frontier(horizontal, vertical, anchor, covered_pairs)

    def normalized_distance(left: tuple[int, int], right: tuple[int, int]) -> float:
        dx = (left[0] - right[0]) / max(nx - 1, 1)
        dy = (left[1] - right[1]) / max(ny - 1, 1)
        return dx * dx + dy * dy

    minimum_distance = {
        candidate: min((normalized_distance(candidate, point) for point in selected))
        for candidate in remaining
    }
    order: list[tuple[tuple[str, str], tuple[float, float]]] = []
    while remaining:
        best_value = max((minimum_distance[candidate] for candidate in remaining))
        chosen = min(
            (candidate for candidate in remaining if abs(minimum_distance[candidate] - best_value) <= 1e-12)
        )
        remaining.remove(chosen)
        pair = (horizontal[chosen[0]][1], vertical[chosen[1]][1])
        order.append((pair, (horizontal[chosen[0]][0], vertical[chosen[1]][0])))
        for candidate in remaining:
            minimum_distance[candidate] = min(
                minimum_distance[candidate], normalized_distance(candidate, chosen)
            )
    return order


def _partition_frontier(horizontal, vertical, anchor, covered_pairs):
    nx, ny = (len(horizontal), len(vertical))
    anchor_x = min(range(nx), key=lambda index: abs(horizontal[index][0] - anchor[0]))
    anchor_y = min(range(ny), key=lambda index: abs(vertical[index][0] - anchor[1]))
    selected = {(index, anchor_y) for index in range(nx)} | {(anchor_x, index) for index in range(ny)}
    for x_index in range(nx):
        for y_index in range(ny):
            pair = (horizontal[x_index][1], vertical[y_index][1])
            if pair in covered_pairs:
                selected.add((x_index, y_index))
    remaining = [
        (x_index, y_index)
        for x_index in range(nx)
        for y_index in range(ny)
        if x_index != anchor_x
        and y_index != anchor_y
        and ((horizontal[x_index][1], vertical[y_index][1]) not in covered_pairs)
    ]
    return (selected, remaining)
