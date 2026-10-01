"""Black-box legacy response simulator for RC-RPS development.

Ground-truth boxes and task targets remain evaluator-only. The controller is
given :meth:`LegacyWorld.observe`, whose return type contains only a coordinate,
binary rendered-response label, and OCR evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence import retain_instruction_tokens, tokenize
from .interface import PreviewObservation


@dataclass(frozen=True)
class TaskSpec:
    """Evaluator task; target labels must never be passed to the controller."""

    task_id: str
    instruction: str
    target_candidate_index: int
    retained_instruction_tokens: tuple[str, ...]


@dataclass
class LegacyWorld:
    """Legacy screen plus simulator-only labels and a public observation oracle."""

    state_id: str
    family: str
    width: int
    height: int
    pool: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    evidence_by_candidate: dict[int, str]
    initial_tokens: set[str]
    tasks: list[TaskSpec]
    descriptor_cache_path: Path
    descriptor_cache_sha256: str

    @property
    def positive_candidate_indices(self) -> set[int]:
        """Evaluator-only response-object identifiers."""

        return set(self.evidence_by_candidate)

    @property
    def structural_support_count(self) -> int:
        return sum(row["source"] in {"corner", "component"} for row in self.pool)

    @staticmethod
    def _point_in_candidate(
        point: tuple[float, float], candidate: dict[str, Any]
    ) -> bool:
        x, y = point
        box = candidate["bbox_xywh"]
        return (
            box["x"] <= x <= box["x"] + box["w"]
            and box["y"] <= y <= box["y"] + box["h"]
        )

    def scoring_candidate_index_at(self, point: tuple[float, float]) -> int | None:
        """Map a coordinate to a label for the separate evaluator only."""

        hits = [
            candidate
            for candidate in self.candidates
            if self._point_in_candidate(point, candidate)
        ]
        if not hits:
            return None
        hits.sort(
            key=lambda candidate: (
                math.hypot(
                    point[0] - candidate["center"][0],
                    point[1] - candidate["center"][1],
                ),
                int(candidate["candidate_index"]),
            )
        )
        return int(hits[0]["candidate_index"])

    def observe(self, point: tuple[float, float]) -> PreviewObservation:
        """Return the complete controller-visible observation."""

        candidate_index = self.scoring_candidate_index_at(point)
        evidence = (
            self.evidence_by_candidate.get(candidate_index, "")
            if candidate_index is not None
            else ""
        )
        return PreviewObservation(
            point=point,
            positive=bool(evidence.strip()),
            evidence=evidence,
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def chart_evidence(root: Path) -> dict[str, dict[int, str]]:
    artifact = load_json(root / "validation" / "c314_randomized_component_stress_audit.json")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in artifact["chartjs"]["tasks"]:
        groups[row["scenario"]].append(row)
    output = {}
    for scenario, rows in groups.items():
        for ordinal, row in enumerate(rows):
            state_id = f"test_{scenario}_task_{ordinal:02d}"
            output[state_id] = {
                int(preview["candidate_index"]): str(preview["tooltip_text"])
                for preview in row["result"]["previews"]
                if str(preview["tooltip_text"]).strip()
            }
    return output


def fullcalendar_evidence(root: Path) -> dict[str, dict[int, str]]:
    artifact = load_json(
        root / "validation" / "c318_fullcalendar_heldout_hover_detail_audit.json"
    )
    first_by_scenario: dict[str, dict[str, Any]] = {}
    for task in artifact["hidden_preview_tasks"]:
        first_by_scenario.setdefault(task["scenario"], task)
    return {
        f"test_{scenario}": {
            int(preview["candidate_index"]): str(preview["tooltip_ocr"])
            for preview in task["previews"]
            if str(preview["tooltip_ocr"]).strip()
        }
        for scenario, task in first_by_scenario.items()
    }


def dense_evidence(root: Path) -> dict[str, dict[int, str]]:
    artifact = load_json(root / "validation" / "c326_dense_preview_grid_stress_audit.json")
    return {
        f"test_{scenario['scenario']}": {
            int(preview["candidate_index"]): str(preview["ocr_text"])
            for preview in scenario["previews"]
            if str(preview["ocr_text"]).strip()
        }
        for scenario in artifact["scenarios"]
    }


def vega_evidence(root: Path) -> dict[str, dict[int, str]]:
    artifact = load_json(root / "validation" / "c322_external_vegalite_tooltip_replay.json")
    return {
        "boundary_vegalite_stocks": {
            int(preview["candidate_index"]): str(preview["ocr_tooltip_text"])
            for preview in artifact["previews"]
            if str(preview["dom_tooltip_text"]).strip()
            and str(preview["ocr_tooltip_text"]).strip()
        }
    }


def build_evidence_index(root: Path) -> dict[str, dict[int, str]]:
    output: dict[str, dict[int, str]] = {}
    for source in (
        chart_evidence(root),
        fullcalendar_evidence(root),
        dense_evidence(root),
        vega_evidence(root),
    ):
        overlap = set(output) & set(source)
        if overlap:
            raise ValueError(f"duplicate evidence states: {sorted(overlap)}")
        output.update(source)
    return output


def load_legacy_worlds(
    root: Path,
    *,
    support_path: Path,
    descriptor_manifest_path: Path,
    protocol_path: Path,
    boundary_protocol_path: Path,
) -> list[LegacyWorld]:
    """Load the sealed B1 simulator without deriving controller state from labels."""

    support = load_json(support_path)
    descriptor_manifest = load_json(descriptor_manifest_path)
    protocol = load_json(protocol_path)
    boundary_protocol = load_json(boundary_protocol_path)
    dataset = load_json(
        root / "validation" / "c333_learned_candidate_proposer_dataset_manifest.json"
    )
    c334 = load_json(root / "validation" / "c334_omniparser_candidate_proposer_screen.json")
    evidence_index = build_evidence_index(root)
    eligible = set(protocol["development_simulator"]["eligible_families"])
    stopwords = set(protocol["evidence_scoring"]["stopwords"])
    stopwords.update(
        boundary_protocol["online_evidence_scoring"]["additional_generic_stopwords"]
    )

    dataset_states = {row["state_id"]: row for row in dataset["states"]}
    c334_states = {row["state_id"]: row for row in c334["state_outputs"]}
    cache_rows = {row["state_id"]: row for row in descriptor_manifest["state_caches"]}
    worlds = []
    for support_state in support["states"]:
        if support_state["family"] not in eligible:
            continue
        state_id = support_state["state_id"]
        state = dataset_states[state_id]
        evidence_by_candidate = evidence_index[state_id]
        initial_tokens = set()
        for proposal in c334_states[state_id]["proposals"]["ocr_only"]:
            initial_tokens.update(tokenize(str(proposal.get("text", ""))))
        tasks = [
            TaskSpec(
                task_id=str(task["task_id"]),
                instruction=str(task["instruction"]),
                target_candidate_index=int(task["target_candidate_index"]),
                retained_instruction_tokens=retain_instruction_tokens(
                    str(task["instruction"]), stopwords
                ),
            )
            for task in state["tasks"]
        ]
        cache = cache_rows[state_id]
        cache_path = root / cache["cache_path"]
        if sha256(cache_path) != cache["cache_sha256"]:
            raise ValueError(f"descriptor cache hash mismatch: {state_id}")
        worlds.append(
            LegacyWorld(
                state_id=state_id,
                family=state["family"],
                width=int(state["image"]["width"]),
                height=int(state["image"]["height"]),
                pool=support_state["pool"],
                candidates=state["candidates"],
                evidence_by_candidate=evidence_by_candidate,
                initial_tokens=initial_tokens,
                tasks=tasks,
                descriptor_cache_path=cache_path,
                descriptor_cache_sha256=cache["cache_sha256"],
            )
        )
    expected_tasks = int(protocol["development_simulator"]["tasks"])
    task_count = sum(len(world.tasks) for world in worlds)
    if task_count != expected_tasks:
        raise ValueError(f"B1 task count {task_count} != {expected_tasks}")
    if len(worlds) != 41:
        raise ValueError(f"B1 state count {len(worlds)} != 41")
    return worlds
