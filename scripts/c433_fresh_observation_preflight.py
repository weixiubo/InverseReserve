#!/usr/bin/env python3
"""Outcome-free public-observation preflight for fresh MiniWoB families.

The runner resets only preregistered schema seeds.  It never calls
``environment.step`` and never records reset ``info``, reward, termination,
evaluator state, or source-generated targets.  Task IDs are environment
configuration only and are not supplied to the method functions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c427_pact_live_development as c427  # noqa: E402
from rcrps.pact_controller_v3 import certify_commit  # noqa: E402
from rcrps.structured_planner import action_candidates  # noqa: E402
from rcrps.structured_planner_v3 import successor_action_inventory  # noqa: E402
from rcrps.typed_contracts_v3 import infer_sequence_contract  # noqa: E402


DEFAULT_PROTOCOL = (
    ROOT / "validation" / "c433_fresh_observation_preflight_protocol.json"
)
RUN_DIRECTORY = ROOT / "runs" / "c433_fresh_observation_preflight"
CELL_DIRECTORY = RUN_DIRECTORY / "cells"
OUTPUT_PATH = ROOT / "validation" / "c433_fresh_observation_preflight.json"
HTML_ROOT = ROOT / "external" / "miniwob-plusplus" / "miniwob" / "html"
C432_RESULT = ROOT / "validation" / "c432_pact_matched_development.json"
C432_RESULT_SHA256 = (
    "d5f67f2ca85773d54fec86671b09bd09ea4b3621c232d9576aef7ebbe7bf1734"
)
C432_PROTOCOL = ROOT / "validation" / "c432_pact_matched_development_protocol.json"
C432_PROTOCOL_SHA256 = (
    "17dfd794daeda4442911ec78b29e3a03eb207f6f8d5d0da8f32aa786e2199e88"
)
SOURCE_INVENTORY = (
    ROOT
    / "paper"
    / "aaai27"
    / "notes"
    / "2026-07-12_pact_fresh_family_source_inventory.md"
)
SOURCE_INVENTORY_SHA256 = (
    "558ba5193eb56ff248b1f71c2216729a09d8810cb379fa9c051f09980445c075"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def verify_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"C433 protocol changed: {actual}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("candidate") != "C433-fresh-observation-preflight-protocol":
        raise ValueError("unexpected C433 protocol candidate")
    if protocol["repositories"] != {
        "browsergym": "0a785fbed075224ae81ca9c1fe924f66050696fe",
        "miniwob_plusplus": "7fd85d71a4b60325c6585396ec4f48377d049838",
    }:
        raise ValueError("C433 repository pins changed")
    if sha256(C432_RESULT) != C432_RESULT_SHA256:
        raise ValueError("frozen C432 result changed")
    if sha256(C432_PROTOCOL) != C432_PROTOCOL_SHA256:
        raise ValueError("frozen C432 protocol changed")
    parent = json.loads(C432_RESULT.read_text(encoding="utf-8"))
    if parent.get("passed") is not True:
        raise ValueError("C432 did not authorize the fresh preflight")
    if protocol["activation"] != {
        "parent_result": str(C432_RESULT.relative_to(ROOT)),
        "parent_result_sha256": C432_RESULT_SHA256,
        "parent_protocol": str(C432_PROTOCOL.relative_to(ROOT)),
        "parent_protocol_sha256": C432_PROTOCOL_SHA256,
        "parent_passed": True,
    }:
        raise ValueError("unexpected C433 activation binding")
    if sha256(SOURCE_INVENTORY) != SOURCE_INVENTORY_SHA256:
        raise ValueError("fresh-family source inventory changed")
    if protocol["source_inventory"] != {
        "path": str(SOURCE_INVENTORY.relative_to(ROOT)),
        "sha256": SOURCE_INVENTORY_SHA256,
    }:
        raise ValueError("unexpected source inventory binding")
    for relative, expected in protocol["source_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"C433 method source changed: {relative}")
    for task in protocol["task_candidates"]:
        source = ROOT / task["source_path"]
        if sha256(source) != task["source_sha256"]:
            raise ValueError(f"C433 task source changed: {task['task_id']}")
    preflight = tuple(protocol["seed_partitions"]["observation_preflight"])
    development = tuple(protocol["seed_partitions"]["contract_development"])
    confirmation = tuple(protocol["seed_partitions"]["confirmation_embargoed"])
    if not preflight or set(preflight) & set(development) or set(preflight) & set(
        confirmation
    ) or set(development) & set(confirmation):
        raise ValueError("C433 seed partitions are empty or overlap")
    return protocol, actual


def cell_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    seeds = tuple(protocol["seed_partitions"]["observation_preflight"])
    rows = []
    for task_index, task in enumerate(protocol["task_candidates"]):
        for seed_index, seed in enumerate(seeds):
            rows.append(
                {
                    "cell_index": len(rows),
                    "task_index": task_index,
                    "seed_index": seed_index,
                    "task": task["task_id"],
                    "family_group": task["family_group"],
                    "expected_role": task["expected_role"],
                    "seed": int(seed),
                    "cell_id": f"{task['task_id']}__seed{int(seed)}",
                }
            )
    return rows


def _role_counts(snapshot: Any) -> dict[str, int]:
    counts = Counter(
        element.role.casefold() or "none"
        for element in snapshot.elements
        if snapshot.is_effectively_visible(element.bid)
    )
    return dict(sorted(counts.items()))


def inspect_observation(observation: dict[str, Any], cell: dict[str, Any]) -> dict:
    goal = str(observation["goal"])
    snapshot = c427.snapshot(observation)
    base = action_candidates(snapshot)
    inventory = successor_action_inventory(snapshot, goal)
    typed_rows = [
        candidate
        for candidate in inventory.candidates
        if candidate.preview_kind is not None
    ]
    recompilations = []
    for candidate in typed_rows:
        decision = infer_sequence_contract(
            snapshot,
            candidate.bid,
            query=inventory.query,
        )
        matches = bool(
            decision.allowed
            and decision.contract is not None
            and decision.contract.kind == candidate.preview_kind
            and decision.contract.action.operation == candidate.operation
            and decision.contract.action.bid == candidate.bid
        )
        recompilations.append(
            {
                "bid": candidate.bid,
                "preview_kind": candidate.preview_kind,
                "allowed": decision.allowed,
                "reason": decision.reason,
                "matches_inventory": matches,
            }
        )

    direct_certificates = []
    for candidate in inventory.candidates:
        certificate = certify_commit(
            goal=goal,
            current=snapshot,
            candidate=candidate,
            inventory=inventory.candidates,
            active_transactions=(),
        )
        if certificate.allowed:
            direct_certificates.append(
                {
                    "bid": candidate.bid,
                    "role": candidate.role,
                    "label": candidate.label,
                    "reason": certificate.reason,
                    "competing_bids": list(certificate.competing_bids),
                }
            )

    return {
        "candidate": "C433-observation-cell",
        "cell": cell,
        "complete": True,
        "method_input": {
            "goal": goal,
            "goal_sha256": text_sha256(goal),
            "method_received_task_id": False,
            "method_received_evaluator_fields": False,
        },
        "reset_audit": {
            "environment_reset_calls": 1,
            "environment_step_calls": 0,
            "reset_info_ignored": True,
            "reward_observed": False,
            "termination_observed": False,
            "evaluator_observed": False,
        },
        "public_observation": {
            "visible_semantic_elements": sum(
                snapshot.is_effectively_visible(element.bid)
                for element in snapshot.elements
            ),
            "visible_role_counts": _role_counts(snapshot),
            "base_action_candidates": [row.prompt_record() for row in base],
        },
        "successor_inventory": {
            "allowed": inventory.allowed,
            "reason": inventory.reason,
            "constraint": inventory.constraint_record(),
            "query": inventory.query,
            "candidates": [row.prompt_record() for row in inventory.candidates],
            "typed_candidate_count": len(typed_rows),
            "typed_contract_kinds": sorted(
                {row.preview_kind for row in typed_rows if row.preview_kind}
            ),
            "recompilations": recompilations,
            "unique_direct_certificates": direct_certificates,
        },
    }


def run(protocol: dict[str, Any]) -> None:
    CELL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with c427.MiniwobServer(HTML_ROOT) as base_url:
        for index, cell in enumerate(cell_manifest(protocol), start=1):
            path = CELL_DIRECTORY / f"{cell['cell_id']}.json"
            if path.is_file():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("complete") and existing.get("cell") == cell:
                    continue
                raise ValueError(f"incompatible C433 cell file: {path}")
            environment = c427.make_environment(cell["task"], base_url, protocol)
            try:
                observation, _ignored_info = environment.reset(seed=cell["seed"])
                result = inspect_observation(observation, cell)
            finally:
                environment.close()
            c427.atomic_write_json(path, result)
            print(
                json.dumps(
                    {
                        "complete": index,
                        "total": len(cell_manifest(protocol)),
                        "cell_id": cell["cell_id"],
                    }
                ),
                flush=True,
            )


def _aggregate_group(rows: list[dict], rule: dict[str, Any]) -> dict[str, Any]:
    cells = len(rows)
    constraint = sum(row["successor_inventory"]["allowed"] for row in rows)
    typed = sum(
        row["successor_inventory"]["typed_candidate_count"] > 0 for row in rows
    )
    direct = sum(
        len(row["successor_inventory"]["unique_direct_certificates"]) == 1
        for row in rows
    )
    recompilations = [
        item
        for row in rows
        for item in row["successor_inventory"]["recompilations"]
    ]
    kinds = Counter(
        kind
        for row in rows
        for kind in row["successor_inventory"]["typed_contract_kinds"]
    )
    return {
        "cells": cells,
        "constraint_compilations": constraint,
        "constraint_fraction": constraint / cells,
        "cells_with_typed_exploration": typed,
        "typed_exploration_fraction": typed / cells,
        "cells_with_one_unique_direct_commit": direct,
        "unique_direct_fraction": direct / cells,
        "typed_recompilations": len(recompilations),
        "typed_recompilation_matches": sum(
            item["matches_inventory"] for item in recompilations
        ),
        "all_typed_recompilations_match": all(
            item["matches_inventory"] for item in recompilations
        ),
        "typed_contract_kind_coverage": dict(sorted(kinds.items())),
        "thresholds": rule,
    }


def finalize(protocol: dict[str, Any], protocol_sha256: str) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    rows = []
    for cell in cell_manifest(protocol):
        path = CELL_DIRECTORY / f"{cell['cell_id']}.json"
        if not path.is_file():
            raise FileNotFoundError(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("complete") or payload.get("cell") != cell:
            raise ValueError(f"incomplete or mismatched cell: {cell['cell_id']}")
        rows.append(payload)

    groups = {}
    inclusion = protocol["inclusion_rule"]
    for group in sorted({row["cell"]["family_group"] for row in rows}):
        subset = [row for row in rows if row["cell"]["family_group"] == group]
        expected_role = {row["cell"]["expected_role"] for row in subset}
        if len(expected_role) != 1:
            raise ValueError(f"mixed expected roles in family group {group}")
        role = next(iter(expected_role))
        thresholds = (
            inclusion["active_family"]
            if role == "active"
            else inclusion["direct_control"]
        )
        summary = _aggregate_group(subset, thresholds)
        if role == "active":
            eligible = (
                summary["constraint_fraction"]
                >= thresholds["minimum_constraint_fraction"]
                and summary["typed_exploration_fraction"]
                >= thresholds["minimum_typed_exploration_fraction"]
                and summary["all_typed_recompilations_match"]
            )
        else:
            eligible = (
                summary["constraint_fraction"]
                >= thresholds["minimum_constraint_fraction"]
                and summary["unique_direct_fraction"]
                >= thresholds["minimum_unique_direct_fraction"]
                and summary["typed_exploration_fraction"]
                <= thresholds["maximum_typed_exploration_fraction"]
            )
        groups[group] = {
            "expected_role": role,
            "eligible": eligible,
            **summary,
        }

    eligible_active = sorted(
        group
        for group, summary in groups.items()
        if summary["expected_role"] == "active" and summary["eligible"]
    )
    eligible_direct = sorted(
        group
        for group, summary in groups.items()
        if summary["expected_role"] == "direct_control" and summary["eligible"]
    )
    checks = {
        "complete_frozen_grid": len(rows) == len(cell_manifest(protocol)),
        "zero_environment_steps": all(
            row["reset_audit"]["environment_step_calls"] == 0 for row in rows
        ),
        "zero_outcome_or_evaluator_observation": all(
            not row["reset_audit"]["reward_observed"]
            and not row["reset_audit"]["termination_observed"]
            and not row["reset_audit"]["evaluator_observed"]
            and row["method_input"]["method_received_evaluator_fields"] is False
            for row in rows
        ),
        "all_typed_contracts_recompile": all(
            summary["all_typed_recompilations_match"]
            for summary in groups.values()
        ),
        "minimum_active_family_groups": len(eligible_active)
        >= inclusion["minimum_eligible_active_family_groups"],
        "minimum_direct_control_groups": len(eligible_direct)
        >= inclusion["minimum_eligible_direct_control_groups"],
    }
    output = {
        "candidate": "C433-fresh-observation-preflight",
        "created_utc": c427.utc_now(),
        "git_head": c427.git_head(),
        "protocol": str(DEFAULT_PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "status": "outcome_free_observation_preflight",
        "information_boundary": protocol["information_boundary"],
        "cell_rows": rows,
        "family_groups": groups,
        "eligible_active_family_groups": eligible_active,
        "eligible_direct_control_groups": eligible_direct,
        "checks": checks,
        "passed": all(checks.values()),
        "next_step": protocol["decision_rule"][
            "on_pass" if all(checks.values()) else "on_failure"
        ],
    }
    c427.atomic_write_json(OUTPUT_PATH, output)
    print(
        json.dumps(
            {
                "passed": output["passed"],
                "eligible_active_family_groups": eligible_active,
                "eligible_direct_control_groups": eligible_direct,
                "family_groups": groups,
                "checks": checks,
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("run", "finalize"), required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256 = verify_protocol(
        args.protocol,
        args.expected_protocol_sha256,
    )
    if args.stage == "run":
        run(protocol)
    else:
        finalize(protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
