#!/usr/bin/env python3
"""Outcome-free live development gate for PACT v4 public contracts.

The gate uses only the consumed C433 observation and contract-development
partitions.  It never opens a confirmation seed and never records reward,
reset info, evaluator state, or a final task action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "src", ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import c427_pact_live_development as c427  # noqa: E402
import c433_fresh_observation_preflight as c433  # noqa: E402
from rcrps.pact_controller_v4 import (  # noqa: E402
    ActionExecutionV4,
    FailClosedTransactionRuntimeV4,
)
from rcrps.pact_grounding_v4 import (  # noqa: E402
    certify_commit_v4,
    verify_goal_state,
)
from rcrps.structured_planner_v4 import (  # noqa: E402
    ActionCandidateV4,
    V4ActionInventory,
    compile_v4_inventory,
)
from rcrps.transaction_actions_v4 import ContractActionV4  # noqa: E402
from rcrps.typed_contracts_v4 import public_calendar_context  # noqa: E402


DEFAULT_PROTOCOL = ROOT / "validation" / "c434_pact_v4_live_development_protocol.json"
OUTPUT_PATH = ROOT / "validation" / "c434_pact_v4_live_development_gate.json"
RUN_DIRECTORY = ROOT / "runs" / "c434_pact_v4_live_development_gate"
SCHEMA_DIRECTORY = RUN_DIRECTORY / "schema"
LIVE_DIRECTORY = RUN_DIRECTORY / "live"
C433_RESULT = ROOT / "validation" / "c433_fresh_observation_preflight.json"
C433_RESULT_SHA256 = (
    "f58800bf9ecfb1f0d543e4d82b45911f5247b3d69d29b1edd7476a6a38db0b76"
)
C433_PROTOCOL = ROOT / "validation" / "c433_fresh_observation_preflight_protocol.json"
C433_PROTOCOL_SHA256 = (
    "70f7cd945975bd53a88c481236fc716333f0d68441c51798fd58e78552ce1c78"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_protocol(path: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    actual = sha256(path)
    if actual != expected_sha256:
        raise ValueError(f"C434 protocol changed: {actual}")
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("candidate") != "C434-PACT-v4-live-development-protocol":
        raise ValueError("unexpected C434 protocol candidate")
    if sha256(C433_RESULT) != C433_RESULT_SHA256:
        raise ValueError("frozen C433 result changed")
    if sha256(C433_PROTOCOL) != C433_PROTOCOL_SHA256:
        raise ValueError("frozen C433 protocol changed")
    parent_result = json.loads(C433_RESULT.read_text(encoding="utf-8"))
    parent_protocol = json.loads(C433_PROTOCOL.read_text(encoding="utf-8"))
    if parent_result.get("passed") is not False:
        raise ValueError("C433 failure disposition changed")
    if protocol["activation"] != {
        "parent_result": str(C433_RESULT.relative_to(ROOT)),
        "parent_result_sha256": C433_RESULT_SHA256,
        "parent_protocol": str(C433_PROTOCOL.relative_to(ROOT)),
        "parent_protocol_sha256": C433_PROTOCOL_SHA256,
        "parent_passed": False,
        "authorized_failure_disposition": parent_result["next_step"],
    }:
        raise ValueError("unexpected C434 activation binding")
    expected_tasks = [
        {
            "task_id": row["task_id"],
            "family_group": row["family_group"],
            "expected_role": row["expected_role"],
        }
        for row in parent_protocol["task_candidates"]
    ]
    if protocol["task_candidates"] != expected_tasks:
        raise ValueError("C434 task candidates differ from frozen C433")
    for relative, expected in protocol["source_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"C434 source changed: {relative}")
    note = protocol["design_note"]
    if sha256(ROOT / note["path"]) != note["sha256"]:
        raise ValueError("C434 design note changed")
    partitions = protocol["seed_partitions"]
    observation = set(partitions["observation_preflight_consumed"])
    development = set(partitions["contract_development_consumed"])
    confirmation = set(partitions["confirmation_embargoed"])
    if not observation or observation & development or observation & confirmation or development & confirmation:
        raise ValueError("C434 seed partitions are empty or overlap")
    return protocol, actual


def schema_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seeds = protocol["seed_partitions"]["observation_preflight_consumed"]
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


def live_manifest(protocol: dict[str, Any]) -> list[dict[str, Any]]:
    observation = protocol["seed_partitions"]["observation_preflight_consumed"]
    development = protocol["seed_partitions"]["contract_development_consumed"]
    definitions = (
        ("autocomplete_restore", "use-autocomplete-nodelay", development),
        ("autocomplete_preterminal", "use-autocomplete-nodelay", development),
        ("date_restore", "choose-date-nodelay", development),
        ("date_preterminal", "choose-date-nodelay", development),
        ("scroll_restore_and_certificate", "click-scroll-list", development),
        ("login_preterminal_restore", "login-user-popup", observation + development),
        ("flight_preterminal", "book-flight-nodelay", development),
        ("direct_certificate", "click-widget", development),
    )
    rows = []
    for workflow_index, (workflow, task, seeds) in enumerate(definitions):
        for seed_index, seed in enumerate(seeds):
            rows.append(
                {
                    "trial_index": len(rows),
                    "workflow_index": workflow_index,
                    "seed_index": seed_index,
                    "workflow": workflow,
                    "task": task,
                    "seed": int(seed),
                    "trial_id": f"{workflow}__{task}__seed{int(seed)}",
                }
            )
    return rows


def _contract_record(contract: Any) -> dict[str, Any]:
    row = asdict(contract)
    if row.get("legacy_contract") is not None:
        row["legacy_contract"] = asdict(contract.legacy_contract)
    return row


def _certificate_record(certificate: Any) -> dict[str, Any]:
    return {
        "allowed": certificate.allowed,
        "reason": certificate.reason,
        "grounding": asdict(certificate.grounding),
        "certified_action": (
            asdict(certificate.certified_action)
            if certificate.certified_action is not None
            else None
        ),
        "observation_fingerprint_sha256": object_sha256(
            certificate.observation_fingerprint
        ),
        "active_stack_signature": certificate.active_stack_signature,
    }


def _restoration_record(outcome: Any) -> dict[str, Any]:
    return {
        "attempted": outcome.attempted,
        "passed": outcome.passed,
        "reason": outcome.reason,
        "check": asdict(outcome.check) if outcome.check is not None else None,
        "final_snapshot_fingerprint_sha256": (
            object_sha256(outcome.final_snapshot.semantic_fingerprint())
            if outcome.final_snapshot is not None
            else None
        ),
    }


def _compact_delta(delta: dict[str, Any]) -> dict[str, Any]:
    return {
        "added_visible_count": len(delta.get("added_visible_bids", ())),
        "removed_visible_count": len(delta.get("removed_visible_bids", ())),
        "changed_visible_count": len(delta.get("changed_visible_bids", ())),
        "newly_visible_text_count": len(delta.get("newly_visible_text", ())),
        "sha256": object_sha256(delta),
    }


def _event_record(event: dict[str, Any]) -> dict[str, Any]:
    row = dict(event)
    for key in ("delta", "global_delta"):
        if isinstance(row.get(key), dict):
            row[key] = _compact_delta(row[key])
    return row


def _unique_certificate(
    *,
    snapshot: Any,
    inventory: V4ActionInventory,
    runtime: FailClosedTransactionRuntimeV4,
    predicate: Callable[[ActionCandidateV4], bool] | None = None,
) -> tuple[ActionCandidateV4, Any, list[dict[str, Any]]]:
    records = []
    admitted = []
    for candidate in inventory.candidates:
        if predicate is not None and not predicate(candidate):
            continue
        certificate = certify_commit_v4(
            current=snapshot,
            goal=inventory.goal_contract,
            candidate=candidate,
            inventory=inventory.candidates,
            active_transactions=tuple(runtime.active),
        )
        records.append(
            {
                "candidate": candidate.prompt_record(),
                "certificate": _certificate_record(certificate),
            }
        )
        if certificate.allowed:
            admitted.append((candidate, certificate))
    if len(admitted) != 1:
        raise RuntimeError(
            f"expected one commit certificate, got {len(admitted)}: {records}"
        )
    return admitted[0][0], admitted[0][1], records


class LiveExecutor:
    def __init__(self, environment: Any, observation: dict[str, Any]) -> None:
        self.environment = environment
        self.observation = observation
        self.actions: list[dict[str, Any]] = []

    @property
    def snapshot(self) -> Any:
        return c427.snapshot(self.observation)

    def __call__(self, action: ContractActionV4, role: str) -> ActionExecutionV4:
        height, width = self.observation["screenshot"].shape[:2]
        code = action.browsergym_code(
            viewport_width=int(width),
            viewport_height=int(height),
        )
        (
            next_observation,
            _discarded_reward,
            terminated,
            truncated,
            _discarded_info,
        ) = self.environment.step(code)
        self.observation = next_observation
        audit = {
            "action_index": len(self.actions),
            "role": role,
            "code": code,
            "terminated": bool(terminated),
            "truncated": bool(truncated),
            "action_error": str(next_observation.get("last_action_error", "")),
        }
        self.actions.append(audit)
        return ActionExecutionV4(
            self.snapshot,
            bool(terminated),
            bool(truncated),
            audit["action_error"],
        )


def _transact(
    *,
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
    predicate: Callable[[ActionCandidateV4], bool],
) -> tuple[Any, ActionCandidateV4]:
    before = executor.snapshot
    inventory = compile_v4_inventory(
        before,
        goal,
        goal_contract=goal_contract,
    )
    matches = [
        row
        for row in inventory.candidates
        if row.transaction_kind is not None and predicate(row)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one transaction row, got {matches}")
    candidate = matches[0]
    contract = inventory.contract_by_bid[candidate.bid]
    outcome = runtime.transact(
        before=before,
        contract=contract,
        candidate_label=candidate.label,
    )
    if not outcome.admitted or outcome.halted:
        raise RuntimeError(f"transaction failed: {outcome}")
    return outcome, candidate


def _commit_unique(
    *,
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
    predicate: Callable[[ActionCandidateV4], bool] | None = None,
) -> tuple[Any, ActionCandidateV4, list[dict[str, Any]]]:
    current = executor.snapshot
    inventory = compile_v4_inventory(
        current,
        goal,
        goal_contract=goal_contract,
    )
    candidate, certificate, records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
        predicate=predicate,
    )
    outcome = runtime.commit(
        current=current,
        action=candidate.action,
        certificate=certificate,
    )
    if not outcome.executed or outcome.halted or outcome.result is None:
        raise RuntimeError(f"certified commit failed: {outcome}")
    if outcome.result.terminal:
        raise RuntimeError("preterminal development commit became terminal")
    return outcome, candidate, records


def inspect_schema(observation: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    goal = str(observation["goal"])
    snapshot = c427.snapshot(observation)
    inventory = compile_v4_inventory(snapshot, goal)
    runtime = FailClosedTransactionRuntimeV4(lambda _action, _role: None)  # never called
    direct_rows = []
    for candidate in inventory.candidates:
        certificate = certify_commit_v4(
            current=snapshot,
            goal=inventory.goal_contract,
            candidate=candidate,
            inventory=inventory.candidates,
            active_transactions=tuple(runtime.active),
        )
        if certificate.allowed:
            direct_rows.append(
                {
                    "candidate": candidate.prompt_record(),
                    "certificate": _certificate_record(certificate),
                }
            )
    return {
        "candidate": "C434-schema-cell",
        "cell": cell,
        "complete": True,
        "method_input": {
            "goal": goal,
            "goal_sha256": hashlib.sha256(goal.encode("utf-8")).hexdigest(),
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
        "goal_contract": inventory.goal_contract.record(),
        "inventory": [row.prompt_record() for row in inventory.candidates],
        "typed_contracts": {
            bid: _contract_record(contract)
            for bid, contract in inventory.contracts
        },
        "unique_direct_certificates": direct_rows,
    }


def run_schema(protocol: dict[str, Any]) -> None:
    SCHEMA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    parent_protocol = json.loads(C433_PROTOCOL.read_text(encoding="utf-8"))
    with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
        for index, cell in enumerate(schema_manifest(protocol), start=1):
            path = SCHEMA_DIRECTORY / f"{cell['cell_id']}.json"
            if path.is_file():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("complete") and existing.get("cell") == cell:
                    continue
                raise ValueError(f"incompatible C434 schema cell: {path}")
            environment = c427.make_environment(cell["task"], base_url, parent_protocol)
            try:
                observation, _discarded_reset_info = environment.reset(seed=cell["seed"])
                result = inspect_schema(observation, cell)
            finally:
                environment.close()
            c427.atomic_write_json(path, result)
            print(json.dumps({"schema": index, "total": 45, "cell": cell["cell_id"]}), flush=True)


def _workflow_autocomplete_restore(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    outcome, row = _transact(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
        predicate=lambda candidate: candidate.transaction_kind == "autocomplete_query",
    )
    restorations = runtime.restore_all("autocomplete restoration gate")
    return {
        "transaction": row.prompt_record(),
        "interrupt_repairs": outcome.interrupt_repairs,
        "restorations": [_restoration_record(item) for item in restorations],
        "certificate_records": [],
    }


def _workflow_autocomplete_preterminal(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    outcome, row = _transact(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
        predicate=lambda candidate: candidate.transaction_kind == "autocomplete_query",
    )
    _commit, choice, choice_records = _commit_unique(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
    )
    current = executor.snapshot
    inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
    _submit, _certificate, submit_records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
    )
    state = verify_goal_state(current, goal_contract)
    if not state.allowed:
        raise RuntimeError(f"autocomplete goal state incomplete: {state}")
    restorations = runtime.restore_all("autocomplete post-choice restoration gate")
    return {
        "transaction": row.prompt_record(),
        "choice": choice.prompt_record(),
        "interrupt_repairs": outcome.interrupt_repairs,
        "goal_state": asdict(state),
        "restorations": [_restoration_record(item) for item in restorations],
        "certificate_records": choice_records + submit_records,
    }


def _open_and_navigate_date(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
    *,
    maximum_shifts: int,
) -> list[dict[str, Any]]:
    rows = []
    _outcome, opener = _transact(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
        predicate=lambda candidate: candidate.transaction_kind == "datepicker_open",
    )
    rows.append(opener.prompt_record())
    for _index in range(maximum_shifts):
        current = executor.snapshot
        inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
        shifts = [
            row
            for row in inventory.candidates
            if row.transaction_kind == "calendar_month_shift"
        ]
        if not shifts:
            break
        if len(shifts) != 1:
            raise RuntimeError(f"ambiguous calendar shifts: {shifts}")
        outcome = runtime.transact(
            before=current,
            contract=inventory.contract_by_bid[shifts[0].bid],
            candidate_label=shifts[0].label,
        )
        if not outcome.admitted or outcome.halted:
            raise RuntimeError(f"calendar shift failed: {outcome}")
        rows.append(shifts[0].prompt_record())
    return rows


def _workflow_date_restore(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    transactions = _open_and_navigate_date(
        executor,
        runtime,
        goal,
        goal_contract,
        maximum_shifts=1,
    )
    restorations = runtime.restore_all("date restoration gate")
    return {
        "transactions": transactions,
        "restorations": [_restoration_record(item) for item in restorations],
        "certificate_records": [],
        "interrupt_repairs": 0,
    }


def _workflow_date_preterminal(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    transactions = _open_and_navigate_date(
        executor,
        runtime,
        goal,
        goal_contract,
        maximum_shifts=12,
    )
    if public_calendar_context(executor.snapshot) != (
        goal_contract.date_anchor.month,
        goal_contract.date_anchor.year,
    ):
        raise RuntimeError("calendar did not reach the goal month")
    _day, day_row, day_records = _commit_unique(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
        predicate=lambda candidate: candidate.label == str(goal_contract.date_anchor.day),
    )
    current = executor.snapshot
    state = verify_goal_state(current, goal_contract)
    if not state.allowed:
        raise RuntimeError(f"date goal state incomplete: {state}")
    inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
    _submit, _certificate, submit_records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
    )
    return {
        "transactions": transactions,
        "date_choice": day_row.prompt_record(),
        "goal_state": asdict(state),
        "restorations": [],
        "certificate_records": day_records + submit_records,
        "interrupt_repairs": 0,
    }


def _workflow_scroll(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    outcome, row = _transact(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
        predicate=lambda candidate: candidate.transaction_kind == "native_select_update",
    )
    current = executor.snapshot
    state = verify_goal_state(current, goal_contract)
    if not state.allowed:
        raise RuntimeError(f"selection goal state incomplete: {state}")
    inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
    _submit, _certificate, records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
    )
    restorations = runtime.restore_all("native selection restoration gate")
    return {
        "transaction": row.prompt_record(),
        "goal_state": asdict(state),
        "interrupt_repairs": outcome.interrupt_repairs,
        "restorations": [_restoration_record(item) for item in restorations],
        "certificate_records": records,
    }


def _workflow_login(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    completed = []
    repairs = 0
    for assignment in goal_contract.field_assignments:
        outcome, row = _transact(
            executor=executor,
            runtime=runtime,
            goal=goal,
            goal_contract=goal_contract,
            predicate=lambda candidate, bid=assignment.bid: candidate.bid == bid,
        )
        completed.append(row.prompt_record())
        repairs += outcome.interrupt_repairs
    current = executor.snapshot
    state = verify_goal_state(current, goal_contract)
    if not state.allowed:
        raise RuntimeError(f"login goal state incomplete: {state}")
    inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
    _submit, _certificate, records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
    )
    restorations = runtime.restore_all("login restoration gate")
    return {
        "transactions": completed,
        "goal_state": asdict(state),
        "interrupt_repairs": repairs,
        "restorations": [_restoration_record(item) for item in restorations],
        "certificate_records": records,
    }


def _workflow_flight(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    transactions = []
    certificate_records = []
    for assignment in goal_contract.field_assignments:
        outcome, row = _transact(
            executor=executor,
            runtime=runtime,
            goal=goal,
            goal_contract=goal_contract,
            predicate=lambda candidate, bid=assignment.bid: candidate.bid == bid,
        )
        if outcome.interrupt_repairs:
            raise RuntimeError("unexpected interrupt repair in flight autocomplete")
        transactions.append(row.prompt_record())
        _choice, choice, records = _commit_unique(
            executor=executor,
            runtime=runtime,
            goal=goal,
            goal_contract=goal_contract,
        )
        certificate_records.extend(records)
        transactions.append(choice.prompt_record())

    transactions.extend(
        _open_and_navigate_date(
            executor,
            runtime,
            goal,
            goal_contract,
            maximum_shifts=12,
        )
    )
    _day, day_row, day_records = _commit_unique(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
        predicate=lambda candidate: candidate.label == str(goal_contract.date_anchor.day),
    )
    certificate_records.extend(day_records)
    transactions.append(day_row.prompt_record())

    current = executor.snapshot
    state = verify_goal_state(current, goal_contract)
    if not state.allowed:
        raise RuntimeError(f"flight form state incomplete: {state}")
    _search, search_row, search_records = _commit_unique(
        executor=executor,
        runtime=runtime,
        goal=goal,
        goal_contract=goal_contract,
    )
    certificate_records.extend(search_records)
    current = executor.snapshot
    inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
    objective, _certificate, objective_records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
        predicate=lambda candidate: dict(candidate.state).get("objective_kind")
        == goal_contract.objective_anchor.kind,
    )
    certificate_records.extend(objective_records)
    return {
        "transactions": transactions,
        "search_action": search_row.prompt_record(),
        "objective_choice": objective.prompt_record(),
        "goal_state_before_search": asdict(state),
        "interrupt_repairs": 0,
        "restorations": [],
        "certificate_records": certificate_records,
    }


def _workflow_direct(
    executor: LiveExecutor,
    runtime: FailClosedTransactionRuntimeV4,
    goal: str,
    goal_contract: Any,
) -> dict[str, Any]:
    current = executor.snapshot
    inventory = compile_v4_inventory(current, goal, goal_contract=goal_contract)
    target, _certificate, records = _unique_certificate(
        snapshot=current,
        inventory=inventory,
        runtime=runtime,
    )
    if inventory.contracts:
        raise RuntimeError("direct control unexpectedly exposed a transaction")
    return {
        "direct_target": target.prompt_record(),
        "interrupt_repairs": 0,
        "restorations": [],
        "certificate_records": records,
    }


WORKFLOWS: dict[str, Callable[..., dict[str, Any]]] = {
    "autocomplete_restore": _workflow_autocomplete_restore,
    "autocomplete_preterminal": _workflow_autocomplete_preterminal,
    "date_restore": _workflow_date_restore,
    "date_preterminal": _workflow_date_preterminal,
    "scroll_restore_and_certificate": _workflow_scroll,
    "login_preterminal_restore": _workflow_login,
    "flight_preterminal": _workflow_flight,
    "direct_certificate": _workflow_direct,
}


def run_live(protocol: dict[str, Any]) -> None:
    LIVE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    parent_protocol = json.loads(C433_PROTOCOL.read_text(encoding="utf-8"))
    with c427.MiniwobServer(c433.HTML_ROOT) as base_url:
        for index, trial in enumerate(live_manifest(protocol), start=1):
            path = LIVE_DIRECTORY / f"{trial['trial_id']}.json"
            if path.is_file():
                existing = json.loads(path.read_text(encoding="utf-8"))
                if existing.get("complete") and existing.get("trial") == trial:
                    continue
                raise ValueError(f"incompatible C434 live trial: {path}")
            environment = c427.make_environment(trial["task"], base_url, parent_protocol)
            try:
                observation, _discarded_reset_info = environment.reset(seed=trial["seed"])
                goal = str(observation["goal"])
                initial = c427.snapshot(observation)
                initial_inventory = compile_v4_inventory(initial, goal)
                executor = LiveExecutor(environment, observation)
                runtime = FailClosedTransactionRuntimeV4(executor)
                details = WORKFLOWS[trial["workflow"]](
                    executor,
                    runtime,
                    goal,
                    initial_inventory.goal_contract,
                )
                action_safety = {
                    "actions": len(executor.actions),
                    "terminal_actions": sum(
                        row["terminated"] or row["truncated"]
                        for row in executor.actions
                    ),
                    "action_errors": sum(
                        bool(row["action_error"]) for row in executor.actions
                    ),
                }
                restorations = details["restorations"]
                passed = bool(
                    not runtime.halted
                    and action_safety["terminal_actions"] == 0
                    and action_safety["action_errors"] == 0
                    and all(row["passed"] for row in restorations)
                )
                result = {
                    "candidate": "C434-live-workflow",
                    "trial": trial,
                    "complete": True,
                    "passed": passed,
                    "method_input": {
                        "goal": goal,
                        "goal_sha256": hashlib.sha256(goal.encode("utf-8")).hexdigest(),
                        "method_received_task_id": False,
                        "method_received_evaluator_fields": False,
                    },
                    "information_audit": {
                        "environment_reset_calls": 1,
                        "reset_info_ignored": True,
                        "reward_observed": False,
                        "evaluator_observed": False,
                        "final_task_action_executed": False,
                    },
                    "goal_contract": initial_inventory.goal_contract.record(),
                    "details": details,
                    "runtime_events": [_event_record(row) for row in runtime.events],
                    "executor_actions": executor.actions,
                    "action_safety": action_safety,
                    "runtime_halted": runtime.halted,
                    "runtime_halt_reason": runtime.halt_reason,
                    "active_transactions_at_stop": [
                        row.planner_record() for row in runtime.active
                    ],
                }
            finally:
                environment.close()
            if not result["passed"]:
                raise RuntimeError(f"C434 live workflow failed: {result}")
            c427.atomic_write_json(path, result)
            print(json.dumps({"live": index, "total": 45, "trial": trial["trial_id"]}), flush=True)


def _schema_groups(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {}
    for group in sorted({row["cell"]["family_group"] for row in rows}):
        subset = [row for row in rows if row["cell"]["family_group"] == group]
        kinds = Counter(
            contract["kind"]
            for row in subset
            for contract in row["typed_contracts"].values()
        )
        groups[group] = {
            "cells": len(subset),
            "goal_contract_cells": sum(row["goal_contract"]["allowed"] for row in subset),
            "typed_cells": sum(bool(row["typed_contracts"]) for row in subset),
            "typed_fraction": sum(bool(row["typed_contracts"]) for row in subset)
            / len(subset),
            "typed_contract_kinds": dict(sorted(kinds.items())),
            "unique_direct_certificate_cells": sum(
                len(row["unique_direct_certificates"]) == 1 for row in subset
            ),
            "unique_direct_fraction": sum(
                len(row["unique_direct_certificates"]) == 1 for row in subset
            )
            / len(subset),
        }
    return groups


def finalize(protocol: dict[str, Any], protocol_sha256: str) -> None:
    if OUTPUT_PATH.exists():
        raise FileExistsError(OUTPUT_PATH)
    schema_rows = []
    for cell in schema_manifest(protocol):
        path = SCHEMA_DIRECTORY / f"{cell['cell_id']}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("complete") or payload.get("cell") != cell:
            raise ValueError(f"invalid C434 schema cell: {cell['cell_id']}")
        schema_rows.append(payload)
    live_rows = []
    for trial in live_manifest(protocol):
        path = LIVE_DIRECTORY / f"{trial['trial_id']}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not payload.get("complete") or payload.get("trial") != trial:
            raise ValueError(f"invalid C434 live trial: {trial['trial_id']}")
        live_rows.append(payload)

    groups = _schema_groups(schema_rows)
    required_active = set(protocol["gates"]["required_active_groups"])
    required_direct = set(protocol["gates"]["required_direct_groups"])
    forbidden_typed = set(protocol["gates"]["forbidden_typed_groups"])
    workflow_counts = Counter(row["trial"]["workflow"] for row in live_rows)
    expected_workflow_counts = Counter(protocol["expected_live_workflow_counts"])
    checks = {
        "complete_schema_grid": len(schema_rows) == protocol["expected_schema_cells"],
        "complete_live_grid": len(live_rows) == protocol["expected_live_trials"],
        "exact_live_workflow_counts": workflow_counts == expected_workflow_counts,
        "required_active_groups_full_coverage": all(
            groups[group]["typed_fraction"] == 1.0 for group in required_active
        ),
        "required_direct_groups_full_coverage": all(
            groups[group]["unique_direct_fraction"] == 1.0
            and groups[group]["typed_fraction"] == 0.0
            for group in required_direct
        ),
        "forbidden_groups_remain_untyped": all(
            groups[group]["typed_fraction"] == 0.0 for group in forbidden_typed
        ),
        "all_goal_spans_validate": all(
            row["goal_contract"]["allowed"]
            or row["cell"]["family_group"] in forbidden_typed
            for row in schema_rows
        ),
        "all_live_workflows_pass": all(row["passed"] for row in live_rows),
        "zero_terminal_development_actions": all(
            row["action_safety"]["terminal_actions"] == 0 for row in live_rows
        ),
        "zero_action_errors": all(
            row["action_safety"]["action_errors"] == 0 for row in live_rows
        ),
        "zero_reward_or_evaluator_observation": all(
            not row["information_audit"]["reward_observed"]
            and not row["information_audit"]["evaluator_observed"]
            and not row["method_input"]["method_received_evaluator_fields"]
            for row in live_rows
        ),
        "zero_final_task_actions": all(
            not row["information_audit"]["final_task_action_executed"]
            for row in live_rows
        ),
        "all_attempted_restorations_pass": all(
            item["passed"]
            for row in live_rows
            for item in row["details"]["restorations"]
        ),
    }
    metrics = {
        "schema_cells": len(schema_rows),
        "live_trials": len(live_rows),
        "gui_actions": sum(row["action_safety"]["actions"] for row in live_rows),
        "terminal_actions": sum(
            row["action_safety"]["terminal_actions"] for row in live_rows
        ),
        "action_errors": sum(
            row["action_safety"]["action_errors"] for row in live_rows
        ),
        "interrupt_repairs": sum(
            row["details"]["interrupt_repairs"] for row in live_rows
        ),
        "restoration_attempts": sum(
            len(row["details"]["restorations"]) for row in live_rows
        ),
        "restoration_passes": sum(
            item["passed"]
            for row in live_rows
            for item in row["details"]["restorations"]
        ),
        "certificate_records": sum(
            len(row["details"]["certificate_records"]) for row in live_rows
        ),
    }
    output = {
        "candidate": "C434-PACT-v4-live-development-gate",
        "created_utc": c427.utc_now(),
        "git_head": c427.git_head(),
        "protocol": str(DEFAULT_PROTOCOL.relative_to(ROOT)),
        "protocol_sha256": protocol_sha256,
        "status": "outcome_free_consumed_seed_development",
        "information_boundary": protocol["information_boundary"],
        "schema_rows": schema_rows,
        "live_rows": live_rows,
        "schema_groups": groups,
        "workflow_counts": dict(sorted(workflow_counts.items())),
        "metrics": metrics,
        "checks": checks,
        "passed": all(checks.values()),
        "next_step": protocol["decision_rule"][
            "on_pass" if all(checks.values()) else "on_failure"
        ],
    }
    c427.atomic_write_json(OUTPUT_PATH, output)
    print(json.dumps({"passed": output["passed"], "checks": checks, "metrics": metrics}, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("schema", "live", "finalize"), required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--expected-protocol-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    protocol, protocol_sha256 = verify_protocol(
        args.protocol,
        args.expected_protocol_sha256,
    )
    if args.stage == "schema":
        run_schema(protocol)
    elif args.stage == "live":
        run_live(protocol)
    else:
        finalize(protocol, protocol_sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
